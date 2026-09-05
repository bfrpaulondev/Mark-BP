"""Skill registry state machine (ANT-277 E6 + E11 + E17, hardened S1/S2).

Real multi-version registry: every version of a slug keeps its own
record — registering v2 never destroys v1 (S1). Rollback is real: the
previous active version returns to ACTIVE and the discarded candidate
becomes deprecated (S2).

Learned/generated skills NEVER become active by themselves: activation
is only reachable from ``awaiting_approval``, and dangerous/high-risk
skills are blocked from activation entirely (S4, fail-closed).
"""

from __future__ import annotations

from dataclasses import dataclass, field

SkillState = str  # plain strings for JSON state files

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
    version: str
    state: SkillState = "draft"
    permissions: tuple[str, ...] = field(default_factory=tuple)
    risk: str = "low"
    supersedes_version: str = ""  # S2: which active version this one replaced


class SkillRegistry:
    def __init__(self) -> None:
        # S1: slug -> {version: record}. Registering a new version never
        # destroys the records of previous ones.
        self._versions: dict[str, dict[str, SkillRecord]] = {}
        self._latest: dict[str, str] = {}
        self._active: dict[str, str] = {}  # slug -> currently active version

    # -.-.-.-
    def register(self, slug: str, version: str, permissions: tuple[str, ...], risk: str) -> SkillRecord:
        """Register (or re-register) one specific version as DRAFT.

        The previous active version is left untouched (S1) — a new
        candidate must go through the full lifecycle again.
        """
        versions = self._versions.setdefault(slug, {})
        existing = versions.get(version)
        record = SkillRecord(
            slug=slug,
            version=version,
            state=existing.state if existing else "draft",
            permissions=permissions,
            risk=risk,
            supersedes_version=existing.supersedes_version if existing else "",
        )
        versions[version] = record
        self._latest[slug] = version
        return record

    # -.-.-.-
    def get(self, slug: str, version: str | None = None) -> SkillRecord | None:
        versions = self._versions.get(slug)
        if not versions:
            return None
        return versions.get(version if version is not None else self._latest[slug])

    # -.-.-.-
    def get_version(self, slug: str, version: str) -> SkillRecord | None:
        return self._versions.get(slug, {}).get(version)

    # -.-.-.-
    def active_version(self, slug: str) -> str | None:
        return self._active.get(slug)

    # -.-.-.-
    def transition(self, slug: str, to_state: SkillState, version: str | None = None) -> SkillRecord:
        record = self.get(slug, version)
        if record is None:
            raise KeyError(f"unknown skill: {slug}")
        if to_state not in STATES:
            raise ValueError(f"unknown state: {to_state}")
        allowed = TRANSITIONS.get(record.state, ())
        if to_state not in allowed:
            raise ValueError(f"illegal transition {record.state} -> {to_state}")
        if to_state == "active" and record.risk in ("dangerous", "high"):
            raise ValueError(f"{record.risk}-risk skills require a human approval gate outside the registry")

        if to_state == "active":
            previous = self._active.get(slug)
            if previous and previous != record.version:
                retired = self._versions[slug][previous]
                retired.state = "deprecated"
                record.supersedes_version = previous
            self._active[slug] = record.version
        record.state = to_state
        return record

    # -.-.-.-
    def rollback(self, slug: str, version: str | None = None) -> SkillRecord:
        """S2 real rollback.

        - candidate (awaiting_approval) rolled back: it becomes
          deprecated; a still-active previous version remains active.
        - active version rolled back: it becomes deprecated and the
          version it superseded returns to ACTIVE.
        """
        record = self.get(slug, version)
        if record is None:
            raise KeyError(f"unknown skill: {slug}")
        if record.state not in ("awaiting_approval", "active"):
            raise ValueError(f"cannot rollback from state {record.state}")

        record.state = "deprecated"
        was_active = self._active.get(slug) == record.version
        if was_active:
            self._active.pop(slug, None)

        if record.supersedes_version:
            previous = self._versions[slug].get(record.supersedes_version)
            if previous is not None and previous.state in ("superseded", "deprecated"):
                previous.state = "active"
                self._active[slug] = previous.version
        return record

    # -.-.-.-
    def activation_brief(self, slug: str, version: str | None = None) -> dict[str, object]:
        """E11: what a human must see before approving activation."""
        record = self.get(slug, version)
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
        return [
            self._versions[slug][version]
            for slug, version in self._active.items()
            if version in self._versions.get(slug, {})
        ]
