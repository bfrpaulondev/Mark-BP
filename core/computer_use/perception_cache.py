from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class FrameSignature:
    """Content-minimised local visual signature.

    Only compact hashes/buckets are retained. No screenshot, JPEG, OCR text or
    pixel buffer is stored by the cache.
    """

    digest: str
    perceptual_hash: int
    luma_bucket: int


@dataclass(frozen=True)
class FrameCacheDecision:
    digest: str
    keyframe: bool
    duplicate: bool
    near_duplicate: bool
    hamming_distance: int | None
    age_ms: int
    reason: str


@dataclass(frozen=True)
class _FrameEntry:
    scope: str
    signature: FrameSignature
    observed_at: float
    keyframe_at: float


class LocalFrameCache:
    """Small process-local cache for frame/keyframe classification.

    The cache is intentionally conservative: exact digest matches may be used
    for duplicate suppression; perceptual similarity is metadata only and must
    not, on its own, hide a frame from the planner.
    """

    def __init__(
        self,
        *,
        max_entries: int = 64,
        ttl_seconds: float = 20.0,
        keyframe_interval_seconds: float = 4.0,
        near_hamming_distance: int = 2,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_entries = max(4, min(1024, int(max_entries)))
        self._ttl_seconds = max(0.25, min(300.0, float(ttl_seconds)))
        self._keyframe_interval = max(
            0.25,
            min(60.0, float(keyframe_interval_seconds)),
        )
        self._near_distance = max(0, min(16, int(near_hamming_distance)))
        self._clock = monotonic_clock
        self._entries: OrderedDict[str, _FrameEntry] = OrderedDict()
        self._latest_by_scope: dict[str, str] = {}

    # -.-.-.-
    def clear(self) -> None:
        self._entries.clear()
        self._latest_by_scope.clear()

    # -.-.-.-
    def observe(
        self,
        signature: FrameSignature,
        *,
        scope: str,
        force_keyframe: bool = False,
    ) -> FrameCacheDecision:
        now = float(self._clock())
        self._evict_expired(now)
        selected_scope = _safe_scope(scope)
        previous_key = self._latest_by_scope.get(selected_scope)
        previous = self._entries.get(previous_key or "")

        if previous is None:
            keyframe = True
            duplicate = False
            near_duplicate = False
            distance = None
            age_ms = 0
            reason = "new_scope"
            keyframe_at = now
        else:
            distance = hamming_distance64(
                previous.signature.perceptual_hash,
                signature.perceptual_hash,
            )
            duplicate = previous.signature.digest == signature.digest
            near_duplicate = bool(
                distance <= self._near_distance
                and abs(previous.signature.luma_bucket - signature.luma_bucket) <= 1
            )
            age_seconds = max(0.0, now - previous.observed_at)
            age_ms = int(round(age_seconds * 1000))
            since_keyframe = max(0.0, now - previous.keyframe_at)
            keyframe = bool(
                force_keyframe
                or not near_duplicate
                or since_keyframe >= self._keyframe_interval
            )
            if force_keyframe:
                reason = "forced"
            elif duplicate and not keyframe:
                reason = "exact_duplicate"
            elif near_duplicate and not keyframe:
                reason = "near_duplicate"
            elif since_keyframe >= self._keyframe_interval:
                reason = "periodic_keyframe"
            else:
                reason = "visual_change"
            keyframe_at = now if keyframe else previous.keyframe_at

        entry_key = _entry_key(selected_scope, signature.digest, now)
        self._entries[entry_key] = _FrameEntry(
            scope=selected_scope,
            signature=signature,
            observed_at=now,
            keyframe_at=keyframe_at,
        )
        self._entries.move_to_end(entry_key)
        self._latest_by_scope[selected_scope] = entry_key
        self._evict_bounded()

        return FrameCacheDecision(
            digest=signature.digest,
            keyframe=keyframe,
            duplicate=duplicate,
            near_duplicate=near_duplicate,
            hamming_distance=distance,
            age_ms=age_ms,
            reason=reason,
        )

    # -.-.-.-
    def stats(self) -> dict[str, int]:
        return {
            "entries": len(self._entries),
            "scopes": len(self._latest_by_scope),
        }

    # -.-.-.-
    def _evict_expired(self, now: float) -> None:
        expired = [
            key
            for key, entry in self._entries.items()
            if (now - entry.observed_at) > self._ttl_seconds
        ]
        for key in expired:
            entry = self._entries.pop(key, None)
            if entry is None:
                continue
            if self._latest_by_scope.get(entry.scope) == key:
                self._latest_by_scope.pop(entry.scope, None)

    # -.-.-.-
    def _evict_bounded(self) -> None:
        while len(self._entries) > self._max_entries:
            key, entry = self._entries.popitem(last=False)
            if self._latest_by_scope.get(entry.scope) == key:
                self._latest_by_scope.pop(entry.scope, None)


# -.-.-.-
def build_frame_signature(
    rgb: Any,
    np: Any,
    *,
    raw_bytes: bytes | bytearray | memoryview | None = None,
) -> FrameSignature:
    """Build an exact digest plus a compact perceptual signature.

    Exact-duplicate suppression is based on a digest of the full captured RGB
    byte stream when available, never on sparse perceptual samples. The latter
    are metadata only. `np` is injected so this module still imports in the
    dependency-light CI environment.
    """

    height, width, _ = rgb.shape
    if height <= 0 or width <= 0:
        return FrameSignature(digest="0" * 24, perceptual_hash=0, luma_bucket=0)

    material = raw_bytes if raw_bytes is not None else rgb.tobytes()
    digest = hashlib.sha256(material).hexdigest()[:24]

    ys = np.linspace(0, height - 1, 8, dtype=np.int32)
    xs = np.linspace(0, width - 1, 9, dtype=np.int32)
    sample = rgb[ys[:, None], xs[None, :], :].astype(np.uint16)
    gray = (
        sample[:, :, 0] * 77
        + sample[:, :, 1] * 150
        + sample[:, :, 2] * 29
    ) >> 8

    comparisons = gray[:, :-1] > gray[:, 1:]
    perceptual_hash = 0
    for bit in comparisons.reshape(-1).tolist():
        perceptual_hash = (perceptual_hash << 1) | int(bool(bit))

    luma_bucket = max(0, min(31, int(float(gray.mean()) // 8)))
    return FrameSignature(
        digest=digest,
        perceptual_hash=perceptual_hash & ((1 << 64) - 1),
        luma_bucket=luma_bucket,
    )


# -.-.-.-
def hamming_distance64(left: int, right: int) -> int:
    return int((int(left) ^ int(right)) & ((1 << 64) - 1)).bit_count()


# -.-.-.-
def _safe_scope(scope: str) -> str:
    raw = str(scope or "default").strip()
    if not raw:
        return "default"
    if len(raw) <= 160:
        return raw
    return "scope-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


# -.-.-.-
def _entry_key(scope: str, digest: str, observed_at: float) -> str:
    seed = f"{scope}|{digest}|{observed_at:.9f}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest()[:32]
