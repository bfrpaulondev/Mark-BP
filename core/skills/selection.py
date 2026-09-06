"""Dynamic skill selection (ANT-277 E15).

Deterministic, bounded selection of ACTIVE skills for an intent. The
whole catalogue is NEVER sent to the LLM: only relevant top-k winners
with minimal metadata. Skills whose permissions are not granted or whose
deterministic relevance is zero are excluded with a reason.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from core.skills.runner import explain_skill

MAX_SELECTED_SKILLS = 8


# -.-.-.-
def _tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", str(text or "").casefold())
    ascii_like = "".join(char for char in normalized if not unicodedata.combining(char))
    return {
        token
        for token in "".join(
            char if char.isalnum() else " " for char in ascii_like
        ).split()
        if token
    }


# -.-.-.-
def _metadata_tokens(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return _tokens(value)
    if isinstance(value, Mapping):
        tokens: set[str] = set()
        for key, item in value.items():
            tokens |= _tokens(str(key))
            tokens |= _metadata_tokens(item)
        return tokens
    if isinstance(value, Iterable):
        tokens: set[str] = set()
        for item in value:
            tokens |= _metadata_tokens(item)
        return tokens
    return _tokens(str(value))


@dataclass(frozen=True)
class SkillSelection:
    ranked: list[dict] = field(default_factory=list)
    excluded: list[dict] = field(default_factory=list)


# -.-.-.-
def select_skills(
    registry,
    *,
    intent_text: str = "",
    granted_permissions: set[str] | None = None,
    top_k: int = 3,
    metadata_by_slug: Mapping[str, object] | None = None,
) -> SkillSelection:
    """Rank active skills for an intent under granted permissions.

    Relevance is deterministic token overlap. Callers may supply bounded
    non-secret metadata per slug (for example manifest name/description/
    trigger terms), which allows multilingual product labels without
    sending the catalogue to a model. Zero-overlap skills are not selected.
    """
    granted = set(granted_permissions or set())
    intent_tokens = _tokens(intent_text)
    metadata = metadata_by_slug or {}
    ranked: list[dict] = []
    excluded: list[dict] = []

    for record in registry.active_skills():
        missing_permissions = sorted(
            permission for permission in record.permissions if permission not in granted
        )
        if missing_permissions:
            excluded.append(
                {
                    "slug": record.slug,
                    "reason": "permissions not granted: " + ", ".join(missing_permissions),
                }
            )
            continue

        skill_tokens = _tokens(record.slug) | _metadata_tokens(metadata.get(record.slug))
        overlap = len(intent_tokens & skill_tokens)
        if overlap <= 0:
            excluded.append(
                {
                    "slug": record.slug,
                    "reason": "no deterministic relevance match",
                }
            )
            continue

        ranked.append(
            {
                "slug": record.slug,
                "version": record.version,
                "score": overlap,
                "permissions": sorted(record.permissions),
            }
        )

    ranked.sort(key=lambda item: (-item["score"], item["slug"]))
    try:
        requested_limit = int(top_k)
    except (TypeError, ValueError):
        requested_limit = 0
    limit = max(0, min(MAX_SELECTED_SKILLS, requested_limit))
    return SkillSelection(ranked=ranked[:limit], excluded=excluded)


# -.-.-.-
def excluded_diagnostics(registry, selection: SkillSelection) -> list[str]:
    """E16: human-readable reason per excluded skill."""
    lines: list[str] = []
    for item in selection.excluded:
        lines.append(f"{item['slug']}: {item['reason']}")
        lines.append("  " + "; ".join(explain_skill(registry, item["slug"])))
    return lines
