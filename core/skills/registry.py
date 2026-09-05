"""Skill registry state machine (ANT-277 E6 + E11 + E17).

Learned/generated skills NEVER become active by themselves: every
transition is explicit, and activation is only reachable from
``awaiting_approval``. Version rollback keeps the previous version
available while a new one is pending.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SkillState = str  # kept as plain strings for JSON state files

STATES = ("draft", "validating", "tested", "awaiting_approval", "active", "deprecated", "revoked")
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("validating", "deprecated"),
    "validating": ("draft", "tested"),
    "tested": ("awaiting_approval", "draft", "deprecated"),
    "awaiting_approval": ("active", "draft", "revoked"),
    "active": ("deprecated", "revoked"),
    "deprecated": ("revoked",),
    "revoked": (),
}


@dataclass
class SkillRecord:
    slug: str
    state: SkillState = "draft"
    version: str = ""
    previous_version: str = ""   # E17: rollback keeps the retired active version
    permissions: tuple[str, ...] = field(default_factory=tuple)
    risk: str = "low"
    review_notes: tuple[str, ...] = field(default_factory=tuple)


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillRecord] = {}

    # -.-.-.-
    def register(self, slug: str, version: str, permissions: tuple[str, ...], risk: str) -> SkillRecord:
        existing = self._skills.get(slug)
        record = SkillRecord(
            slug=slug,
            state="draft",
            version=version,
            previous_version=existing.version if existing else "",
            permissions=permissions,
            risk=risk,
        )
        self._skills[slug] = record
        return record

    # -.-.-.-
    def get(self, slug: str) -> SkillRecord | None:
        return self._skills.get(slug)

    # -.-.-.-
    def transition(self, slug: str, to_state: SkillState) -> SkillRecord:
        record = self._skills.get(slug)
        if record is None:
            raise KeyError(f"unknown skill: {slug}")
        if to_state not in STATES:
            raise ValueError(f"unknown state: {to_state}")
        allowed = TRANSITIONS.get(record.state, ())
        if to_state not in allowed:
            raise ValueError(f"illegal transition {record.state} -> {to_state}")
        if to_state == "active" and record.risk == "dangerous":
            raise ValueError("dangerous skills require a human approval gate outside the registry")
        if to_state == "active":
            record.previous_version = record.previous_version or ""
        record.state = to_state
        return record

    # -.-.-.-
    def rollback(self, slug: str) -> SkillRecord:
        """E17: retire the pending version and restore the previous active one."""
        record = self._skills.get(slug)
        if record is None:
            raise KeyError(f"unknown skill: {slug}")
        if record.state not in ("awaiting_approval", "active"):
            raise ValueError(f"cannot rollback from state {record.state}")
        record.state = "deprecated" if record.previous_version else "revoked"
        return record

    # -.-.-.-
    def activation_brief(self, slug: str) -> dict[str, object]:
        """E11: what a human must see before approving activation."""
        record = self._skills.get(slug)
        if record is None:
            raise KeyError(f"unknown skill: {slug}")
        return {
            "slug": record.slug,
            "version": record.version,
            "permissions": sorted(record.permissions),
            "risk": record.risk,
            "tests_required": True,
            "state": record.state,
        }

    # -.-.-.-
    def active_skills(self) -> list[SkillRecord]:
        return [record for record in self._skills.values() if record.state == "active"]
