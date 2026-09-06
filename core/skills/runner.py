"""Isolated skill runner (ANT-277 E8) and diagnostics (E16).

Executes a skill OUTSIDE the main runtime process:

- subprocess with a minimal environment (no ANTONELLA keys, no global
  env access) — secrets are injected via stdin JSON, never argv/env;
- hard timeout from the manifest; cancellation via process kill;
- working directory isolated per run;
- resource limits are an interface placeholder — this is NOT a strong
  sandbox, and the docstring says so.

Diagnostics (E16) explain, deterministically, why a skill is not
selected/active or why a run failed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

from core.skills.manifest import SkillManifest
from core.skills.result import SkillResult

_RESULT_MARKER = "__SKILL_RESULT__"
_BOOTSTRAP = Path(__file__).resolve().parent / "_bootstrap.py"

_MINIMAL_ENV_KEYS = ("SystemRoot", "windir", "TEMP", "TMP", "PATH", "COMSPEC")


class SkillRunner:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        cancel_event: threading.Event | None = None,
        base_working_dir: Path | None = None,
    ):
        self._clock = clock
        self._cancel_event = cancel_event or threading.Event()
        self._base = Path(base_working_dir) if base_working_dir else Path(tempfile.gettempdir()) / "antonella-skills"

    # -.-.-.-
    @property
    def cancel_event(self) -> threading.Event:
        return self._cancel_event

    # -.-.-.-
    def run(self, manifest: SkillManifest, package_dir: Path, args: dict[str, Any], secrets: dict[str, str]) -> SkillResult:
        """Run one skill version in an isolated subprocess.

        Delivery means the entrypoint returned a JSON dict with ok=True;
        verification stays False unless the skill itself proves a
        postcondition and reports it.
        """
        started = self._clock()
        working_dir = Path(tempfile.mkdtemp(prefix=f"{manifest.slug}-", dir=str(self._base)))
        working_dir.mkdir(parents=True, exist_ok=True)

        env = {key: os.environ[key] for key in _MINIMAL_ENV_KEYS if key in os.environ}
        env["PYTHONUTF8"] = "1"
        stdin_payload = json.dumps(
            {
                "skill_path": str(package_dir / "skill.py"),
                "entrypoint": manifest.entrypoint.split(":")[-1],
                "working_dir": str(working_dir),
                "permissions": list(manifest.permissions),
                "secrets": dict(secrets),
                "args": dict(args),
            }
        )

        process = subprocess.Popen(
            [sys.executable, "-I", str(_BOOTSTRAP)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=str(working_dir),
            text=True,
        )
        watcher = threading.Thread(target=self._watch_cancel, args=(process,), daemon=True)
        watcher.start()

        timed_out = False
        try:
            stdout, stderr = process.communicate(input=stdin_payload, timeout=manifest.timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            stdout, stderr = process.communicate()

        duration_ms = int((self._clock() - started) * 1000)
        if timed_out:
            return SkillResult(
                skill_slug=manifest.slug, ok=False, delivered=False,
                error="timeout", risk=manifest.risk, duration_ms=duration_ms,
            )
        if self._cancel_event.is_set():
            return SkillResult(
                skill_slug=manifest.slug, ok=False, delivered=False,
                error="cancelled", risk=manifest.risk, duration_ms=duration_ms,
            )
        if process.returncode != 0:
            return SkillResult(
                skill_slug=manifest.slug, ok=False, delivered=False,
                error=(stderr or "skill crashed").strip()[-400:],  # tail holds the real exception
                risk=manifest.risk, duration_ms=duration_ms,
            )

        marker = stdout.find(_RESULT_MARKER)
        if marker == -1:
            return SkillResult(
                skill_slug=manifest.slug, ok=False, delivered=False,
                error="skill produced no parsable result",
                risk=manifest.risk, duration_ms=duration_ms,
            )
        try:
            payload = json.loads(stdout[marker + len(_RESULT_MARKER):].strip())
        except json.JSONDecodeError:
            return SkillResult(
                skill_slug=manifest.slug, ok=False, delivered=False,
                error="skill result was not valid JSON",
                risk=manifest.risk, duration_ms=duration_ms,
            )
        return SkillResult(
            skill_slug=manifest.slug,
            ok=bool(payload.get("ok")),
            delivered=bool(payload.get("ok")),
            output={k: v for k, v in payload.items() if k != "ok"},
            risk=manifest.risk,
            duration_ms=duration_ms,
        )

    # -.-.-.-
    def _watch_cancel(self, process: subprocess.Popen) -> None:
        while process.poll() is None:
            if self._cancel_event.is_set():
                process.kill()
                return
            time.sleep(0.1)


# -.-.-.-
def explain_skill(
    registry,
    slug: str,
    *,
    validator_problems: list[str] | None = None,
    missing_capabilities: list[str] | None = None,
    runner_error: str | None = None,
) -> list[str]:
    """E16: deterministic diagnostics — why is the skill not running?"""
    reasons: list[str] = []
    record = registry.get(slug)
    if record is None:
        return [f"skill '{slug}' is not registered"]
    if validator_problems:
        reasons.extend(f"validation failed: {p}" for p in validator_problems)
    if missing_capabilities:
        reasons.append(
            "missing capabilities: " + ", ".join(missing_capabilities)
        )
    if record.state == "awaiting_approval":
        reasons.append("awaiting human approval (activation brief available)")
    elif record.state != "active":
        reasons.append(f"skill is not active (state: {record.state})")
    if runner_error:
        reasons.append(f"last run failed: {runner_error}")
    if not reasons:
        reasons.append("no known blockers")
    return reasons
