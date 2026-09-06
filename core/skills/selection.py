"""Dynamic skill selection (ANT-277 E15).

Deterministic, bounded selection of ACTIVE skills for an intent. The
whole catalogue is NEVER sent to the LLM: only the ranked top_k winners
with minimal metadata. Skills whose permissions are not granted are
excluded with a diagnostic (E16 tie-in), never silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.skills.runner import explain_skill


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in "".join(c if c.isalnum() else " " for c in (text or "").lower()).split()
        if token
    }


@dataclass(frozen=True)
class SkillSelection:
    ranked: list[dict] = field(default_factory=list)
    excluded: list[dict] = field(default_factory=list)


def select_skills(
    registry,
    *,
    intent_text: str = "",
    granted_permissions: set[str] | None = None,
    top_k: int = 3,
) -> SkillSelection:
    """Rank active skills for an intent under the granted permissions.

    Scoring is honest and deterministic: token overlap between the intent
    and the skill slug (semantic ranking is a future concern).
    """
    granted = granted_permissions or set()
    intent_tokens = _tokens(intent_text)
    ranked: list[dict] = []
    excluded: list[dict] = []

    for record in registry.active_skills():
        missing_permissions = [p for p in record.permissions if p not in granted]
        if missing_permissions:
            excluded.append({
                "slug": record.slug,
                "reason": "permissions not granted: " + ", ".join(missing_permissions),
            })
            continue
        overlap = len(intent_tokens & _tokens(record.slug))
        ranked.append({
            "slug": record.slug,
            "version": record.version,
            "score": overlap,
            "permissions": sorted(record.permissions),
        })

    ranked.sort(key=lambda item: (-item["score"], item["slug"]))
    return SkillSelection(
        ranked=ranked[: max(0, top_k)],
        excluded=excluded,
    )


def excluded_diagnostics(registry, selection: SkillSelection) -> list[str]:
    """E16: human-readable reason per excluded skill."""
    lines: list[str] = []
    for item in selection.excluded:
        lines.append(f"{item['slug']}: {item['reason']}")
        lines.append("  " + "; ".join(explain_skill(registry, item["slug"])))
    return lines
