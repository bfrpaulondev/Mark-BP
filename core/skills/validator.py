"""Static skill validator (ANT-277 E7 + E10).

Deterministic AST-level checks over ``skill.py`` plus package structure.
This is NOT a sandbox: it is a gate that rejects obvious violations
before a human ever reviews the skill.

Checks:
- manifest structure (fields, slug/version/risk/permissions/timeout);
- forbidden imports always rejected (subprocess, ctypes, shutil...);
- network imports require the ``network`` permission;
- filesystem writes require ``filesystem.write``; reads require
  ``filesystem.read``;
- ``os.environ`` access requires granted secrets instead;
- dependencies require a non-empty ``requirements.lock`` (E9: pinned
  policy is enforced at review, silent installation never happens);
- tests/ with at least one test file is mandatory (E10) before the
  skill can leave ``tested``.
"""

from __future__ import annotations

import ast
from pathlib import Path

from core.skills.manifest import SkillManifest, validate_manifest

ALWAYS_FORBIDDEN_MODULES = frozenset({"subprocess", "ctypes", "shutil", "pickle", "socketserver"})
NETWORK_MODULES = frozenset({"socket", "requests", "httpx", "urllib", "http.client", "aiohttp"})
FILESYSTEM_WRITE_HINTS = frozenset({"open", "write_text", "write_bytes", "mkdir", "unlink", "rmtree"})
FILESYSTEM_READ_HINTS = frozenset({"open", "read_text", "read_bytes", "listdir", "scandir"})


def _imports(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def validate_skill_package(package_dir: Path, manifest: SkillManifest) -> list[str]:
    problems = list(validate_manifest(manifest))
    package_dir = Path(package_dir)

    skill_py = package_dir / "skill.py"
    if not skill_py.exists():
        problems.append("missing skill.py")
        return problems

    entry_module, _, entry_function = manifest.entrypoint.partition(":")
    if entry_module.strip("/") not in {"skill", "skill.py"} or not entry_function:
        problems.append("entrypoint must be 'skill:<function>'")
    else:
        tree = ast.parse(skill_py.read_text(encoding="utf-8"), filename=str(skill_py))
        function_names = {
            node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if entry_function not in function_names:
            problems.append(f"entrypoint function not found: {entry_function}")

        imports = _imports(tree)
        for module in sorted(imports):
            root = module.split(".")[0]
            if root in ALWAYS_FORBIDDEN_MODULES or module in ALWAYS_FORBIDDEN_MODULES:
                problems.append(f"forbidden import: {module}")
            elif module in NETWORK_MODULES or root in NETWORK_MODULES:
                if "network" not in manifest.permissions:
                    problems.append(f"network import without permission: {module}")

        called = _called_names(tree)
        environ_access = any(
            isinstance(node, ast.Attribute) and node.attr == "environ"
            for node in ast.walk(tree)
        )
        if environ_access:
            # Environment access bypasses explicit secret injection (E4).
            problems.append("os.environ access is forbidden: declare secrets and use SkillContext.secret()")

        needs_write = "filesystem.write" in manifest.permissions
        needs_read = "filesystem.read" in manifest.permissions
        uses_write = bool(called & FILESYSTEM_WRITE_HINTS)
        uses_read = bool(called & FILESYSTEM_READ_HINTS)
        if uses_write and not needs_write:
            problems.append("filesystem write detected without filesystem.write permission")
        if uses_read and not needs_read and not needs_write:
            problems.append("filesystem read detected without filesystem.read permission")

    if manifest.dependencies:
        lock = package_dir / "requirements.lock"
        if not lock.exists() or not lock.read_text(encoding="utf-8").strip():
            problems.append("dependencies declared without requirements.lock (E9)")

    tests_dir = package_dir / "tests"
    if not tests_dir.is_dir() or not any(tests_dir.glob("test_*.py")):
        problems.append("missing tests/test_*.py (E10: every skill ships tests)")

    md = package_dir / "SKILL.md"
    if not md.exists():
        problems.append("missing SKILL.md (E3)")

    return problems
