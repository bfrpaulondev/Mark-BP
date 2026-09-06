"""Learnable skills runtime contracts (ANT-277).

Additive package only: no existing core module is modified. The runtime
loader/runner lands in a later slice; this package holds the package
schema, context, result, registry state machine and the static validator.
"""
from core.skills.context import SkillContext
from core.skills.manifest import SkillManifest, parse_manifest_text
from core.skills.registry import SkillRegistry, SkillState
from core.skills.result import SkillResult

__all__ = [
    "SkillContext",
    "SkillManifest",
    "SkillRegistry",
    "SkillResult",
    "SkillState",
    "parse_manifest_text",
]
