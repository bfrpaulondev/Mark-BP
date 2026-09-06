"""Skill bootstrap executed INSIDE the isolated subprocess (ANT-277 E8).

Reads a JSON payload from stdin:
    {"skill_path": "...", "entrypoint": "run",
     "working_dir": "...", "permissions": [...],
     "secrets": {...}, "args": {...}}

Imports the skill module, builds a minimal context (no UI, no DB, no
global env access) and prints the JSON result. Any crash becomes a
non-zero exit with the traceback on stderr.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    skill_path = Path(payload["skill_path"])
    spec = importlib.util.spec_from_file_location("antonella_skill_module", skill_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    context = {
        "working_dir": payload["working_dir"],
        "permissions": list(payload.get("permissions") or []),
        "secrets": dict(payload.get("secrets") or {}),
        "args": dict(payload.get("args") or {}),
    }
    entrypoint = getattr(module, payload["entrypoint"])
    result = entrypoint(context)
    if not isinstance(result, dict):
        raise TypeError("skill entrypoint must return a dict")
    print("__SKILL_RESULT__")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
