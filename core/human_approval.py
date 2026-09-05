from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any

from core.policy_engine import PolicyDecision


_UNTRUSTED_APPROVAL_KEYS = {
    "approved",
    "approval",
    "approval_id",
    "approval_request_id",
    "approval_token",
    "authorization",
    "confirmed",
    "consent",
    "human_approved",
    "risk",
}

_SENSITIVE_SUMMARY_KEYS = {
    "api_key",
    "code",
    "content",
    "cookie",
    "message",
    "message_text",
    "password",
    "prompt",
    "secret",
    "text",
    "token",
}


# -.-.-.-
def _canonicalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key).strip().lower() not in _UNTRUSTED_APPROVAL_KEYS
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_canonicalize(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


# -.-.-.-
def action_fingerprint(
    tool_name: str,
    args: Mapping[str, Any] | None,
    decision: PolicyDecision,
) -> str:
    """Hash the exact substantive action without retaining raw argument values."""
    payload = {
        "tool": str(tool_name or "").strip().lower(),
        "effect": decision.effect.value,
        "rule_id": decision.rule_id,
        "args": _canonicalize(dict(args or {})),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


# -.-.-.-
def _leaf_name(value: Any) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return ""
    try:
        return PurePath(raw).name[:120]
    except Exception:
        return raw.rsplit("/", 1)[-1][:120]


# -.-.-.-
def _safe_target_summary(tool_name: str, args: Mapping[str, Any] | None) -> str:
    """Build an ephemeral local-UI hint without message/content/secret fields."""
    params = dict(args or {})
    for key in ("receiver", "app_name", "browser", "window", "tab"):
        value = params.get(key)
        if value not in (None, ""):
            return f"{key}: {str(value)[:120]}"

    for key in ("file_path", "path", "name", "destination", "output_path"):
        value = params.get(key)
        if value not in (None, ""):
            leaf = _leaf_name(value)
            return f"{key}: {leaf or 'target'}"

    action = str(params.get("action") or "").strip()
    if action:
        return f"action: {action[:80]}"

    safe_keys = [
        str(key)
        for key in params
        if str(key).strip().lower() not in _SENSITIVE_SUMMARY_KEYS
        and str(key).strip().lower() not in _UNTRUSTED_APPROVAL_KEYS
    ]
    if safe_keys:
        return "fields: " + ", ".join(sorted(safe_keys)[:6])
    return str(tool_name or "action")[:120]


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    fingerprint: str
    tool_name: str
    action: str
    effect: str
    rule_id: str
    target_summary: str
    created_at: float
    expires_at: float

    def to_public_dict(self, *, now: float) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "action": self.action,
            "effect": self.effect,
            "rule_id": self.rule_id,
            "target_summary": self.target_summary,
            "expires_in_seconds": max(0, int(self.expires_at - now)),
        }


@dataclass(frozen=True)
class ApprovalGrant:
    request_id: str
    fingerprint: str
    approved_at: float
    expires_at: float


class HumanApprovalManager:
    """In-memory trusted approval channel independent from model/tool arguments.

    Approval requests are exact-action fingerprints. The manager stores no raw argument
    payload and grants are one-use with a short TTL. Only local application code should
    call `approve`; no model tool or plugin exposes that method.
    """

    def __init__(
        self,
        *,
        request_ttl_seconds: float = 300.0,
        grant_ttl_seconds: float = 90.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._request_ttl = max(10.0, float(request_ttl_seconds))
        self._grant_ttl = max(5.0, float(grant_ttl_seconds))
        self._clock = clock
        self._lock = threading.RLock()
        self._pending_by_id: dict[str, ApprovalRequest] = {}
        self._pending_by_fingerprint: dict[str, str] = {}
        self._grants_by_fingerprint: dict[str, ApprovalGrant] = {}

    # -.-.-.-
    def request(
        self,
        tool_name: str,
        args: Mapping[str, Any] | None,
        decision: PolicyDecision,
    ) -> ApprovalRequest:
        now = self._clock()
        fingerprint = action_fingerprint(tool_name, args, decision)
        with self._lock:
            self._purge_locked(now)
            existing_id = self._pending_by_fingerprint.get(fingerprint)
            if existing_id:
                existing = self._pending_by_id.get(existing_id)
                if existing is not None:
                    return existing

            request_id = "apr_" + secrets.token_urlsafe(12)
            params = dict(args or {})
            request = ApprovalRequest(
                request_id=request_id,
                fingerprint=fingerprint,
                tool_name=str(tool_name or "").strip(),
                action=str(params.get("action") or "").strip(),
                effect=decision.effect.value,
                rule_id=decision.rule_id,
                target_summary=_safe_target_summary(tool_name, params),
                created_at=now,
                expires_at=now + self._request_ttl,
            )
            self._pending_by_id[request_id] = request
            self._pending_by_fingerprint[fingerprint] = request_id
            return request

    # -.-.-.-
    def approve(self, request_id: str) -> bool:
        """Approve one pending request from a trusted local user interaction."""
        now = self._clock()
        with self._lock:
            self._purge_locked(now)
            request = self._pending_by_id.pop(str(request_id or ""), None)
            if request is None:
                return False
            self._pending_by_fingerprint.pop(request.fingerprint, None)
            self._grants_by_fingerprint[request.fingerprint] = ApprovalGrant(
                request_id=request.request_id,
                fingerprint=request.fingerprint,
                approved_at=now,
                expires_at=now + self._grant_ttl,
            )
            return True

    # -.-.-.-
    def deny(self, request_id: str) -> bool:
        now = self._clock()
        with self._lock:
            self._purge_locked(now)
            request = self._pending_by_id.pop(str(request_id or ""), None)
            if request is None:
                return False
            self._pending_by_fingerprint.pop(request.fingerprint, None)
            self._grants_by_fingerprint.pop(request.fingerprint, None)
            return True

    # -.-.-.-
    def consume_if_approved(
        self,
        tool_name: str,
        args: Mapping[str, Any] | None,
        decision: PolicyDecision,
    ) -> bool:
        """Consume a matching grant exactly once. Model-provided flags are irrelevant."""
        now = self._clock()
        fingerprint = action_fingerprint(tool_name, args, decision)
        with self._lock:
            self._purge_locked(now)
            grant = self._grants_by_fingerprint.pop(fingerprint, None)
            return bool(grant is not None and grant.expires_at > now)

    # -.-.-.-
    def public_view(self, request: ApprovalRequest) -> dict[str, Any]:
        return request.to_public_dict(now=self._clock())

    # -.-.-.-
    def pending(self) -> list[dict[str, Any]]:
        now = self._clock()
        with self._lock:
            self._purge_locked(now)
            requests = sorted(self._pending_by_id.values(), key=lambda item: item.created_at)
            return [item.to_public_dict(now=now) for item in requests]

    # -.-.-.-
    def clear(self) -> None:
        with self._lock:
            self._pending_by_id.clear()
            self._pending_by_fingerprint.clear()
            self._grants_by_fingerprint.clear()

    # -.-.-.-
    def _purge_locked(self, now: float) -> None:
        expired_requests = [
            request_id
            for request_id, request in self._pending_by_id.items()
            if request.expires_at <= now
        ]
        for request_id in expired_requests:
            request = self._pending_by_id.pop(request_id, None)
            if request is not None:
                self._pending_by_fingerprint.pop(request.fingerprint, None)

        expired_grants = [
            fingerprint
            for fingerprint, grant in self._grants_by_fingerprint.items()
            if grant.expires_at <= now
        ]
        for fingerprint in expired_grants:
            self._grants_by_fingerprint.pop(fingerprint, None)


_GLOBAL_MANAGER = HumanApprovalManager()


# -.-.-.-
def get_human_approval_manager() -> HumanApprovalManager:
    return _GLOBAL_MANAGER
