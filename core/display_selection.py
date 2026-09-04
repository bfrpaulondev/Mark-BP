from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any


_NUMBER_WORDS = {
    "um": 1,
    "uma": 1,
    "one": 1,
    "primeiro": 1,
    "primeira": 1,
    "first": 1,
    "dois": 2,
    "duas": 2,
    "two": 2,
    "segundo": 2,
    "segunda": 2,
    "second": 2,
    "tres": 3,
    "three": 3,
    "terceiro": 3,
    "terceira": 3,
    "third": 3,
    "quatro": 4,
    "four": 4,
    "quarto": 4,
    "quarta": 4,
    "fourth": 4,
    "cinco": 5,
    "five": 5,
    "quinto": 5,
    "quinta": 5,
    "fifth": 5,
    "seis": 6,
    "six": 6,
    "sexto": 6,
    "sexta": 6,
    "sixth": 6,
}


# -.-.-.-
def _fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().strip()


# -.-.-.-
def monitor_contains_point(monitor: Mapping[str, Any], x: int, y: int) -> bool:
    left = int(monitor.get("left", 0))
    top = int(monitor.get("top", 0))
    width = int(monitor.get("width", 0))
    height = int(monitor.get("height", 0))
    return left <= x < left + width and top <= y < top + height


# -.-.-.-
def normalize_monitor_hint(value: int | str | None) -> int | str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None

    normalized = _fold_text(str(value))
    if not normalized or normalized in {
        "active",
        "foreground",
        "current",
        "auto",
        "ativo",
        "activa",
        "ativa",
        "actual",
        "atual",
    }:
        return None

    if normalized in {
        "all",
        "combined",
        "desktop",
        "todos",
        "todas",
        "todos os monitores",
        "todos os ecra",
        "todos os ecras",
        "todos os displays",
    }:
        return "all"

    prefixes = (
        "monitor ",
        "screen ",
        "display ",
        "ecra ",
        "ecras ",
    )
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized.removeprefix(prefix).strip()
            break

    suffixes = (" monitor", " screen", " display", " ecra")
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
            break

    if normalized.isdigit():
        return int(normalized)

    return _NUMBER_WORDS.get(normalized)


# -.-.-.-
def select_monitor(
    monitors: Sequence[Mapping[str, Any]],
    *,
    point: tuple[int, int] | None = None,
    hint: int | str | None = None,
) -> Mapping[str, Any]:
    if not monitors:
        raise ValueError("No monitors available")

    normalized_hint = normalize_monitor_hint(hint)
    if normalized_hint == "all":
        return monitors[0]
    if isinstance(normalized_hint, int) and 1 <= normalized_hint < len(monitors):
        return monitors[normalized_hint]

    if point is not None:
        x, y = point
        for monitor in monitors[1:]:
            if monitor_contains_point(monitor, x, y):
                return monitor

    return monitors[1] if len(monitors) > 1 else monitors[0]


# -.-.-.-
def selected_monitor_index(
    monitors: Sequence[Mapping[str, Any]],
    monitor: Mapping[str, Any],
) -> int:
    for index, candidate in enumerate(monitors):
        if candidate == monitor:
            return index
    return 0


# -.-.-.-
def describe_monitors(
    monitors: Sequence[Mapping[str, Any]],
    *,
    active_point: tuple[int, int] | None = None,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, monitor in enumerate(monitors):
        if index == 0:
            continue
        left = int(monitor.get("left", 0))
        top = int(monitor.get("top", 0))
        width = int(monitor.get("width", 0))
        height = int(monitor.get("height", 0))
        is_active = bool(
            active_point
            and monitor_contains_point(monitor, active_point[0], active_point[1])
        )
        output.append(
            {
                "index": index,
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "right": left + width,
                "bottom": top + height,
                "active": is_active,
            }
        )
    return output
