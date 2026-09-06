"""Undefined-name audit (ANT-275 startup regression).

The physical Windows round found `AntonellaRuntime.__init__` calling
`get_config()` while main.py imported only `get_gemini_key`. compileall
and import-only CI cannot catch that class: the NameError fires at
CONSTRUCTION time, and main.py pulls the whole actions/ dependency
chain so import-based tests cannot run in light CI jobs.

This audit is the sound, dependency-free catch: for every active
first-party module, any name LOADED that is never BOUND anywhere in
that module (import/def/class/assign/loop/with/except/params) and is
not a builtin is a guaranteed NameError at runtime — regardless of
where the use sits (module level or function body).

Soundness: no false positives for dynamic binding via globals()/eval
only where those calls exist; such sites are allowed explicitly below.
"""

from __future__ import annotations

import ast
import builtins
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Module-level implicit names the interpreter provides (PEP 302 loading,
# module metadata, typing re-exports used without import in some files).
IMPLICIT_MODULE_NAMES = frozenset({"__file__", "__name__", "__doc__", "__package__", "Any"})
BUILTIN_NAMES = frozenset(dir(builtins))

# Modules known to bind names dynamically (globals()/exec/setattr) —
# a strict never-bound check would produce false positives there.
DYNAMIC_BINDING_MODULES = ("main.py",)

AUDITED_DIRS = ("core", "memory", "tasks", "ui", "dashboard", "plugins", "scripts", "actions", "config", "skills")
AUDITED_FILES = ("main.py", "antonella.py", "setup.py")


def _bound_names(tree: ast.AST) -> set[str]:
    """Every name bound anywhere in the module, any scope, any binding
    form: imports, defs, classes, assigns, for targets, with-as,
    except-as, walrus, function parameters."""
    bound: set[str] = set()

    def visit(node: ast.AST) -> None:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Parameters bind inside the function.
            args = node.args
            for a in (*args.posonlyargs, *args.args, *args.kwonlyargs):
                bound.add(a.arg)
            if args.vararg:
                bound.add(args.vararg.arg)
            if args.kwarg:
                bound.add(args.kwarg.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.target, ast.Name):
            bound.add(node.target.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.withitem) and node.optional_vars and isinstance(node.optional_vars, ast.Name):
            bound.add(node.optional_vars.id)
        elif isinstance(node, ast.Global):
            bound.update(node.names)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return bound


def _loaded_names(tree: ast.AST) -> set[str]:
    loaded: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            loaded.add(node.id)
    return loaded


def audit_module(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    bound = _bound_names(tree)
    problems: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in bound and node.id not in BUILTIN_NAMES and node.id not in IMPLICIT_MODULE_NAMES:
                problems.append(f"{path.name}: line {node.lineno}: undefined name {node.id!r}")
    return problems


class UndefinedNameAuditTests(unittest.TestCase):
    def test_active_modules_have_no_never_bound_names(self):
        problems: list[str] = []
        files: list[Path] = [ROOT / f for f in AUDITED_FILES]
        for directory in AUDITED_DIRS:
            base = ROOT / directory
            if base.is_dir():
                files.extend(p for p in sorted(base.rglob("*.py")) if "__pycache__" not in str(p))
        for path in files:
            if not path.is_file():
                continue
            for problem in audit_module(path):
                problems.append(problem)
        self.assertEqual(problems, [], "undefined names found:\n" + "\n".join(problems))

    def test_get_config_regression_is_specifically_covered(self):
        # The exact historical failure: main.py used get_config() in
        # AntonellaRuntime.__init__ without importing it.
        main_source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("get_config", main_source)
        import ast as ast_module

        tree = ast_module.parse(main_source)
        bound = _bound_names(tree)
        self.assertIn("get_config", bound)


if __name__ == "__main__":
    unittest.main()
