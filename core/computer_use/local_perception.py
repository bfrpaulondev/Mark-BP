from __future__ import annotations

import hashlib
import json
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from core.computer_use.contracts import ComputerAction, FrameSnapshot


_ALLOWED_CONTROL_TYPES = {
    "button",
    "hyperlink",
    "menuitem",
    "tabitem",
    "listitem",
}
_CLICK_VERBS = (
    "click",
    "click on",
    "clique",
    "clique em",
    "clicar",
    "clicar em",
    "carrega",
    "carrega em",
    "carregar",
    "carregar em",
    "pressiona",
    "pressiona em",
    "pressionar",
    "pressionar em",
)
_RISKY_TERMS = {
    "delete",
    "remove",
    "erase",
    "send",
    "submit",
    "publish",
    "post",
    "upload",
    "download",
    "buy",
    "purchase",
    "pay",
    "transfer",
    "confirm",
    "approve",
    "save",
    "apply",
    "accept",
    "allow",
    "install",
    "uninstall",
    "login",
    "signin",
    "run",
    "execute",
    "shutdown",
    "restart",
    "apagar",
    "eliminar",
    "excluir",
    "remover",
    "enviar",
    "submeter",
    "publicar",
    "carregar",
    "descarregar",
    "comprar",
    "pagar",
    "transferir",
    "confirmar",
    "aprovar",
    "guardar",
    "salvar",
    "aplicar",
    "aceitar",
    "permitir",
    "instalar",
    "desinstalar",
    "entrar",
    "autenticar",
    "executar",
    "desligar",
    "reiniciar",
}
_RISKY_PHRASES = {
    "sign in",
    "log in",
    "place order",
    "grant access",
    "revoke access",
    "save changes",
    "confirm changes",
    "alterar permissões",
    "conceder acesso",
    "revogar acesso",
    "guardar alterações",
    "confirmar alterações",
}
_GENERIC_COMMIT_LABELS = {
    "ok",
    "yes",
    "sim",
    "continue",
    "continuar",
    "next",
    "seguinte",
    "finish",
    "concluir",
    "done",
    "feito",
}


@dataclass(frozen=True)
class LocalPerceptionSuggestion:
    action: ComputerAction
    source: str
    cache_hit: bool = False


@dataclass(frozen=True)
class _CachedSuggestion:
    expires_at: float
    x: int
    y: int
    control_type: str


class LocalPerceptionPlanner:
    """Fail-closed local semantic perception before visual-model escalation.

    This slice deliberately supports only explicit, unique, low-risk UIA clicks
    in a named target window. Everything else falls through to the VLM.
    Cached entries store coordinates and control type only; control labels,
    objectives and UI text are never retained.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        max_entries: int = 32,
        ttl_seconds: float = 1.5,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._enabled = bool(enabled)
        self._max_entries = max(4, min(256, int(max_entries)))
        self._ttl_seconds = max(0.1, min(10.0, float(ttl_seconds)))
        self._clock = monotonic_clock
        self._cache: OrderedDict[str, _CachedSuggestion] = OrderedDict()

    # -.-.-.-
    def suggest(
        self,
        *,
        objective: str,
        frame: FrameSnapshot,
        target_window: str,
    ) -> LocalPerceptionSuggestion | None:
        if not self._enabled:
            return None

        title = str(target_window or "").strip()
        if not title:
            return None

        target = _extract_explicit_click_target(objective)
        if not target or not _is_locally_safe_target(target):
            return None
        if _contains_risky_term(objective):
            return None

        cache_key = _request_digest(
            objective=objective,
            target_window=title,
            frame=frame,
        )
        cached = self._get_cached(cache_key)
        if cached is not None:
            return LocalPerceptionSuggestion(
                action=_action_for_point(
                    cached.x,
                    cached.y,
                    cached.control_type,
                    safety_context=target,
                ),
                source="uia_cache",
                cache_hit=True,
            )

        controls = _inspect_controls(title)
        if controls is None:
            return None

        normalized_target = _normalize_label(target)
        matches: list[Mapping[str, Any]] = []
        for control in controls:
            if not isinstance(control, Mapping):
                continue
            if not bool(control.get("enabled", False)) or not bool(control.get("visible", False)):
                continue
            control_type = str(control.get("control_type") or "").strip().casefold()
            if control_type not in _ALLOWED_CONTROL_TYPES:
                continue
            name = _normalize_label(control.get("name"))
            if not name or name != normalized_target:
                continue
            rectangle = control.get("rectangle")
            if not _valid_rectangle(rectangle):
                continue
            matches.append(control)

        if len(matches) != 1:
            return None

        selected = matches[0]
        rectangle = selected.get("rectangle")
        if not isinstance(rectangle, list):
            return None
        screen_x = (int(rectangle[0]) + int(rectangle[2])) // 2
        screen_y = (int(rectangle[1]) + int(rectangle[3])) // 2
        image_point = _screen_to_image(frame, screen_x, screen_y)
        if image_point is None:
            return None

        image_x, image_y = image_point
        control_type = str(selected.get("control_type") or "control")[:48]
        self._put_cached(
            cache_key,
            _CachedSuggestion(
                expires_at=float(self._clock()) + self._ttl_seconds,
                x=image_x,
                y=image_y,
                control_type=control_type,
            ),
        )
        return LocalPerceptionSuggestion(
            action=_action_for_point(
                image_x,
                image_y,
                control_type,
                safety_context=target,
            ),
            source="uia",
            cache_hit=False,
        )

    # -.-.-.-
    def clear(self) -> None:
        self._cache.clear()

    # -.-.-.-
    def _get_cached(self, key: str) -> _CachedSuggestion | None:
        now = float(self._clock())
        expired = [cache_key for cache_key, value in self._cache.items() if value.expires_at <= now]
        for cache_key in expired:
            self._cache.pop(cache_key, None)
        value = self._cache.get(key)
        if value is not None:
            self._cache.move_to_end(key)
        return value

    # -.-.-.-
    def _put_cached(self, key: str, value: _CachedSuggestion) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_entries:
            self._cache.popitem(last=False)


# -.-.-.-
def _inspect_controls(target_window: str) -> list[Mapping[str, Any]] | None:
    try:
        from actions.windows_ui_automation import windows_ui_automation

        raw = windows_ui_automation(
            {
                "action": "inspect",
                "window": target_window,
                "limit": 160,
            }
        )
        payload = json.loads(raw)
    except Exception:
        return None
    if not isinstance(payload, Mapping) or not bool(payload.get("ok", False)):
        return None
    controls = payload.get("controls")
    if not isinstance(controls, list):
        return None
    return [item for item in controls if isinstance(item, Mapping)]


# -.-.-.-
def _extract_explicit_click_target(objective: str) -> str:
    raw = str(objective or "").strip()
    if not raw or len(raw) > 240:
        return ""

    quoted = re.findall(r"[\"“”']([^\"“”']{2,80})[\"“”']", raw)
    if len(quoted) == 1:
        prefix = raw[: raw.find(quoted[0])].casefold()
        if any(verb in prefix for verb in _CLICK_VERBS):
            return quoted[0].strip()

    normalized = re.sub(r"\s+", " ", raw).strip()
    for verb in sorted(_CLICK_VERBS, key=len, reverse=True):
        match = re.fullmatch(
            rf"(?i){re.escape(verb)}\s+(?:(?:em|no|na|o|a|the)\s+)?(.{{2,80}}?)\s*[.!]?",
            normalized,
        )
        if match:
            return str(match.group(1) or "").strip()
    return ""


# -.-.-.-
def _normalize_label(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .:;!?\t\r\n")


# -.-.-.-
def _is_locally_safe_target(value: Any) -> bool:
    normalized = _normalize_label(value)
    if not normalized or normalized in _GENERIC_COMMIT_LABELS:
        return False
    return not _contains_risky_term(normalized)


# -.-.-.-
def _contains_risky_term(value: Any) -> bool:
    normalized = _normalize_label(value)
    if not normalized:
        return False
    if any(phrase in normalized for phrase in _RISKY_PHRASES):
        return True
    tokens = set(re.findall(r"[\wÀ-ÿ]+", normalized, flags=re.UNICODE))
    return any(term in tokens for term in _RISKY_TERMS)


# -.-.-.-
def _valid_rectangle(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    try:
        left, top, right, bottom = (int(item) for item in value)
    except (TypeError, ValueError):
        return False
    return right > left and bottom > top


# -.-.-.-
def _screen_to_image(frame: FrameSnapshot, x: int, y: int) -> tuple[int, int] | None:
    if frame.monitor_width <= 0 or frame.monitor_height <= 0:
        return None
    max_x = frame.left + frame.monitor_width
    max_y = frame.top + frame.monitor_height
    if not (frame.left <= x < max_x and frame.top <= y < max_y):
        return None
    image_x = round(((x - frame.left) / frame.monitor_width) * frame.image_width)
    image_y = round(((y - frame.top) / frame.monitor_height) * frame.image_height)
    image_x = min(max(0, image_x), max(0, frame.image_width - 1))
    image_y = min(max(0, image_y), max(0, frame.image_height - 1))
    return image_x, image_y


# -.-.-.-
def _action_for_point(
    x: int,
    y: int,
    control_type: str,
    *,
    safety_context: str,
) -> ComputerAction:
    return ComputerAction(
        action="click",
        description=f"Activate unique local UIA {str(control_type or 'control')[:48]}",
        x=int(x),
        y=int(y),
        confidence=1.0,
        risk="low",
        reobserve=True,
        safety_context=str(safety_context or "")[:160],
    )


# -.-.-.-
def _request_digest(
    *,
    objective: str,
    target_window: str,
    frame: FrameSnapshot,
) -> str:
    material = "|".join(
        (
            _normalize_label(objective),
            hashlib.sha256(str(target_window).encode("utf-8")).hexdigest()[:16],
            str(frame.perception_digest or ""),
            str(frame.sequence),
            str(frame.monitor_index),
            str(frame.left),
            str(frame.top),
            str(frame.monitor_width),
            str(frame.monitor_height),
            str(frame.topology_token or ""),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
