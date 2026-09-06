"""Skill package manifest (ANT-277 E2).

manifest.yaml is parsed with PyYAML when available; otherwise a
restricted deterministic subset (flat keys, indented '- item' lists,
comments) is used — the validator only relies on that subset, so CI
legs without pyyaml behave identically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

REQUIRED_FIELDS = (
    "name",
    "slug",
    "version",
    "description",
    "entrypoint",
    "permissions",
    "risk",
    "timeout_seconds",
)
KNOWN_PERMISSIONS = frozenset(
    {"filesystem.read", "filesystem.write", "network", "subprocess", "os.settings", "ui.automation"}
)
KNOWN_RISKS = frozenset({"low", "medium", "high", "dangerous"})
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


# -.-.-.-
def _restricted_yaml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_list: list[str] | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith((" ", "\t")) and current_list is not None:
            item = line.strip().lstrip("-").strip()
            if item:
                current_list.append(item)
            continue
        current_list = None
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            current_list = []
            data[key] = current_list
        else:
            data[key] = value
    return data


def parse_manifest_text(text: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore[import-not-found]

        loaded = yaml.safe_load(text)
        return loaded if isinstance(loaded, dict) else {}
    except ImportError:
        return _restricted_yaml(text)


@dataclass(frozen=True)
class SkillManifest:
    name: str
    slug: str
    version: str
    description: str
    entrypoint: str
    permissions: tuple[str, ...]
    risk: str
    timeout_seconds: int
    dependencies: tuple[str, ...] = ()
    compatibility: str = ""
    author: str = ""
    integrity: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    _schema_problem_input: bool = field(default=False, repr=False)
    _schema_problem_output: bool = field(default=False, repr=False)

    # -.-.-.-
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillManifest":
        # S3: schemas must be mappings; anything else is coerced to an
        # empty dict and flagged by validate_manifest.
        input_schema = data.get("input_schema")
        output_schema = data.get("output_schema")
        return cls(
            name=str(data.get("name", "")),
            slug=str(data.get("slug", "")),
            version=str(data.get("version", "")),
            description=str(data.get("description", "")),
            entrypoint=str(data.get("entrypoint", "")),
            permissions=tuple(str(p) for p in (data.get("permissions") or [])),
            risk=str(data.get("risk", "")),
            timeout_seconds=int(data.get("timeout_seconds") or 0),
            dependencies=tuple(str(d) for d in (data.get("dependencies") or [])),
            compatibility=str(data.get("compatibility", "")),
            author=str(data.get("author", "")),
            integrity=str(data.get("integrity", "")),
            input_schema=input_schema if isinstance(input_schema, dict) else {},
            output_schema=output_schema if isinstance(output_schema, dict) else {},
            _schema_problem_input=not isinstance(input_schema, (dict, type(None))),
            _schema_problem_output=not isinstance(output_schema, (dict, type(None))),
        )


    # -.-.-.-
    def to_dict(self) -> dict[str, Any]:
        """Round-trip companion of from_dict (S3)."""
        return {
            "name": self.name,
            "slug": self.slug,
            "version": self.version,
            "description": self.description,
            "entrypoint": self.entrypoint,
            "permissions": list(self.permissions),
            "risk": self.risk,
            "timeout_seconds": self.timeout_seconds,
            "dependencies": list(self.dependencies),
            "compatibility": self.compatibility,
            "author": self.author,
            "integrity": self.integrity,
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
        }


def validate_manifest(manifest: SkillManifest) -> list[str]:
    """E2/E7: structural validation. Returns a list of problems (empty = valid)."""
    problems: list[str] = []
    for field_name in REQUIRED_FIELDS:
        if not getattr(manifest, field_name if field_name != "timeout_seconds" else "timeout_seconds"):
            problems.append(f"missing required field: {field_name}")
    if not _SLUG_RE.match(manifest.slug):
        problems.append("slug must be lowercase kebab-case")
    if not _VERSION_RE.match(manifest.version):
        problems.append("version must be semver x.y.z")
    if manifest.risk not in KNOWN_RISKS:
        problems.append(f"unknown risk: {manifest.risk}")
    unknown_permissions = [p for p in manifest.permissions if p not in KNOWN_PERMISSIONS]
    if unknown_permissions:
        problems.append(f"excessive/unknown permissions: {', '.join(unknown_permissions)}")
    if manifest.timeout_seconds <= 0 or manifest.timeout_seconds > 600:
        problems.append("timeout_seconds must be within 1..600")
    if manifest._schema_problem_input:
        problems.append("input_schema must be a mapping")
    if manifest._schema_problem_output:
        problems.append("output_schema must be a mapping")
    return problems
