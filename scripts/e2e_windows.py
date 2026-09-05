from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


SCHEMA_VERSION = 1
_STATUS_PASS = "pass"
_STATUS_FAIL = "fail"
_STATUS_SKIP = "skip"
_STATUS_NOT_RUN = "not_run"
_ALLOWED_STATUSES = {_STATUS_PASS, _STATUS_FAIL, _STATUS_SKIP, _STATUS_NOT_RUN}
_SAFE_TOKEN_RE = re.compile(r"^[a-z0-9_.:-]{1,96}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class MatrixCase:
    case_id: str
    title: str
    category: str
    mode: str
    description: str
    instructions: tuple[str, ...] = ()
    requires_windows: bool = True
    requires_fixture: bool = False

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.case_id,
            "title": self.title,
            "category": self.category,
            "mode": self.mode,
            "description": self.description,
            "requires_windows": self.requires_windows,
            "requires_fixture": self.requires_fixture,
            "instructions": list(self.instructions),
        }


@dataclass(frozen=True)
class ProbeOutcome:
    status: str
    reason_code: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def public_dict(self, *, case_id: str) -> dict[str, Any]:
        status = self.status if self.status in _ALLOWED_STATUSES else _STATUS_FAIL
        return {
            "id": case_id,
            "status": status,
            "reason_code": _safe_token(self.reason_code, fallback="invalid_reason"),
            "details": _safe_details(self.details),
        }


Probe = Callable[[], ProbeOutcome]


# -.-.-.-
def build_matrix() -> tuple[MatrixCase, ...]:
    """Return the canonical ANT-275 physical Windows validation matrix."""
    return (
        MatrixCase(
            "env.windows",
            "Windows desktop session",
            "environment",
            "automatic",
            "Confirm the harness is running in a Windows desktop session.",
        ),
        MatrixCase(
            "env.python",
            "Supported Python runtime",
            "environment",
            "automatic",
            "Confirm Python is within Antonella's supported 3.11/3.12 range.",
            requires_windows=False,
        ),
        MatrixCase(
            "deps.windows_control",
            "Windows control dependencies",
            "environment",
            "automatic",
            "Check the locked runtime exposes Win32, UIA and capture dependencies.",
        ),
        MatrixCase(
            "deps.ui",
            "PyQt6 runtime",
            "environment",
            "automatic",
            "Check the Antonella desktop UI dependency is installed.",
            requires_windows=False,
        ),
        MatrixCase(
            "deps.audio",
            "Audio devices visible",
            "voice",
            "automatic",
            "Enumerate audio capabilities without recording or playing audio.",
        ),
        MatrixCase(
            "deps.browser",
            "Playwright Chromium installed",
            "browser",
            "automatic",
            "Verify the managed-browser executable exists without launching a browser window.",
        ),
        MatrixCase(
            "display.topology",
            "Physical display topology readable",
            "display",
            "automatic",
            "Read display count/DPI/topology metadata without storing device names.",
        ),
        MatrixCase(
            "windows.foreground",
            "Foreground window observable",
            "windows",
            "automatic",
            "Verify Win32 can observe a foreground HWND without storing its title.",
        ),
        MatrixCase(
            "voice.roundtrip",
            "Voice round-trip and barge-in",
            "voice",
            "manual",
            "Validate real microphone → Gemini Live → audio response and interruption.",
            instructions=(
                "Start Antonella with `uv run python antonella.py`.",
                "Say a short harmless request and confirm the transcript and spoken response match.",
                "Interrupt Antonella while she is speaking and confirm barge-in stops the old turn.",
                "Confirm no success statement is spoken before a verified tool effect when a tool is involved.",
            ),
        ),
        MatrixCase(
            "browser.real_tabs",
            "Real browser tab verification",
            "browser",
            "manual",
            "Validate verified tab navigation against a normal user browser.",
            instructions=(
                "Open Chrome or Edge normally with at least two harmless tabs.",
                "Ask Antonella to list tabs, move to the next tab, return, then switch by title.",
                "Pass only if the real selected tab changes and the result is verified; ambiguity must fail closed.",
            ),
        ),
        MatrixCase(
            "uia.fixture_navigation",
            "UIA navigation on local fixture",
            "uia",
            "manual",
            "Validate the structured UIA path before Computer Use.",
            requires_fixture=True,
            instructions=(
                "Start `uv run python scripts/e2e_fixture.py`.",
                "Ask Antonella to inspect the fixture and activate `Open local panel` without Computer Use.",
                "Pass only if UIA/structured control is used and the fixture state changes as expected.",
            ),
        ),
        MatrixCase(
            "display.multi_monitor_dpi",
            "Multi-monitor and DPI physical mapping",
            "display",
            "manual",
            "Validate explicit monitor selection and physical coordinates across the real desktop.",
            instructions=(
                "If two or more monitors exist, place the fixture on a secondary monitor and make it foreground.",
                "Ask Antonella which displays exist and explicitly select the fixture monitor.",
                "Move the fixture between monitors with different scaling when available and repeat a safe target action.",
                "Pass only if monitor identity/coordinates stay correct; disconnected or ambiguous targets must fail closed.",
            ),
        ),
        MatrixCase(
            "computer_use.recovery",
            "Computer Use stale-plan recovery",
            "computer_use",
            "manual",
            "Validate replanning on a controlled local window without external effects.",
            requires_fixture=True,
            instructions=(
                "Start the local fixture and explicitly request Computer Use against its window.",
                "Use `Move visual target` while Antonella is planning a harmless click.",
                "Pass only if a stale visual action is discarded/replanned rather than clicking old coordinates.",
                "Repeat with `Animate harmless indicator` enabled while testing scroll; recovery must remain bounded.",
            ),
        ),
        MatrixCase(
            "computer_use.pause_resume_stop",
            "Computer Use pause/resume/stop",
            "computer_use",
            "manual",
            "Validate human interruption controls at safe boundaries.",
            requires_fixture=True,
            instructions=(
                "Run a multi-step fixture task through Computer Use.",
                "Pause it, confirm no new action dispatch occurs, then resume.",
                "Stop it before completion and pass only if the Antonella process remains open and the task stops.",
            ),
        ),
        MatrixCase(
            "approval.one_use",
            "One-use approval and anti-self-approval",
            "approval",
            "manual",
            "Validate a sensitive-looking but locally simulated action without real external/destructive effects.",
            requires_fixture=True,
            instructions=(
                "Use the fixture button `Simulated send — local only`; it performs no network or file operation.",
                "Ask Antonella to activate it and confirm execution pauses for explicit local human approval.",
                "Do not use any real send/delete/payment target for this test.",
                "Approve one step and pass only if one pending action executes once; a second sensitive action must require a new approval.",
                "Confirm model/tool arguments cannot approve the action and Enter/Return does not trigger the approval control.",
            ),
        ),
    )


# -.-.-.-
def _safe_token(value: str, *, fallback: str) -> str:
    candidate = str(value or "").strip().lower().replace(" ", "_")
    return candidate if _SAFE_TOKEN_RE.fullmatch(candidate) else fallback


# -.-.-.-
def _safe_details(details: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep reports content-free: details may contain only scalar measurements."""
    if not isinstance(details, Mapping):
        return {}
    output: dict[str, Any] = {}
    for key, value in list(details.items())[:32]:
        safe_key = _safe_token(str(key), fallback="")
        if not safe_key:
            continue
        if isinstance(value, bool) or value is None:
            output[safe_key] = value
        elif isinstance(value, int):
            output[safe_key] = value
        elif isinstance(value, float) and math.isfinite(value):
            output[safe_key] = round(value, 4)
    return output


# -.-.-.-
def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


# -.-.-.-
def _windows_guard() -> ProbeOutcome | None:
    if platform.system() != "Windows":
        return ProbeOutcome(_STATUS_SKIP, "requires_windows")
    return None


# -.-.-.-
def _probe_windows() -> ProbeOutcome:
    is_windows = platform.system() == "Windows"
    return ProbeOutcome(
        _STATUS_PASS if is_windows else _STATUS_FAIL,
        "windows_detected" if is_windows else "not_windows",
        {"windows": is_windows},
    )


# -.-.-.-
def _probe_python() -> ProbeOutcome:
    major, minor = sys.version_info[:2]
    supported = major == 3 and minor in {11, 12}
    return ProbeOutcome(
        _STATUS_PASS if supported else _STATUS_FAIL,
        "python_supported" if supported else "python_unsupported",
        {"python_major": major, "python_minor": minor},
    )


# -.-.-.-
def _probe_windows_control_dependencies() -> ProbeOutcome:
    guarded = _windows_guard()
    if guarded is not None:
        return guarded
    modules = ("win32gui", "pywinauto", "mss", "pyautogui")
    available = [_module_available(name) for name in modules]
    complete = all(available)
    return ProbeOutcome(
        _STATUS_PASS if complete else _STATUS_FAIL,
        "windows_control_ready" if complete else "windows_control_dependency_missing",
        {"dependency_count": len(modules), "available_count": sum(available)},
    )


# -.-.-.-
def _probe_ui_dependency() -> ProbeOutcome:
    ready = _module_available("PyQt6")
    return ProbeOutcome(
        _STATUS_PASS if ready else _STATUS_FAIL,
        "pyqt_ready" if ready else "pyqt_missing",
        {"pyqt_available": ready},
    )


# -.-.-.-
def _probe_audio_devices() -> ProbeOutcome:
    guarded = _windows_guard()
    if guarded is not None:
        return guarded
    if not _module_available("sounddevice"):
        return ProbeOutcome(_STATUS_FAIL, "sounddevice_missing")
    try:
        import sounddevice as sd

        devices = list(sd.query_devices())
        inputs = sum(1 for item in devices if float(item.get("max_input_channels", 0)) > 0)
        outputs = sum(1 for item in devices if float(item.get("max_output_channels", 0)) > 0)
        ready = inputs > 0 and outputs > 0
        return ProbeOutcome(
            _STATUS_PASS if ready else _STATUS_FAIL,
            "audio_ready" if ready else "audio_direction_missing",
            {"device_count": len(devices), "input_count": inputs, "output_count": outputs},
        )
    except Exception as exc:
        return ProbeOutcome(
            _STATUS_FAIL,
            "audio_probe_failed",
            {"error": True, "error_type_code": _error_type_code(exc)},
        )


# -.-.-.-
def _probe_browser_runtime() -> ProbeOutcome:
    guarded = _windows_guard()
    if guarded is not None:
        return guarded
    if not _module_available("playwright.sync_api"):
        return ProbeOutcome(_STATUS_FAIL, "playwright_missing")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as runtime:
            executable = Path(runtime.chromium.executable_path)
            installed = executable.is_file()
        return ProbeOutcome(
            _STATUS_PASS if installed else _STATUS_FAIL,
            "chromium_ready" if installed else "chromium_not_installed",
            {"chromium_installed": installed},
        )
    except Exception as exc:
        return ProbeOutcome(
            _STATUS_FAIL,
            "playwright_probe_failed",
            {"error": True, "error_type_code": _error_type_code(exc)},
        )


# -.-.-.-
def _probe_display_topology() -> ProbeOutcome:
    guarded = _windows_guard()
    if guarded is not None:
        return guarded
    try:
        from actions.display_manager import display_manager

        payload = json.loads(display_manager({"action": "list"}))
        if not payload.get("ok"):
            return ProbeOutcome(_STATUS_FAIL, "display_probe_failed")
        displays = payload.get("displays") if isinstance(payload.get("displays"), list) else []
        dpis = []
        negative_origin = False
        primary_count = 0
        dpi_complete = True
        for item in displays:
            if not isinstance(item, Mapping):
                dpi_complete = False
                continue
            try:
                dpi_x = int(item.get("dpi_x") or 0)
                dpi_y = int(item.get("dpi_y") or 0)
                left = int(item.get("left") or 0)
                top = int(item.get("top") or 0)
            except (TypeError, ValueError):
                dpi_complete = False
                continue
            if dpi_x <= 0 or dpi_y <= 0:
                dpi_complete = False
            else:
                dpis.append((dpi_x, dpi_y))
            negative_origin = negative_origin or left < 0 or top < 0
            primary_count += int(bool(item.get("primary", False)))
        ready = bool(displays) and bool(payload.get("topology_token")) and dpi_complete
        return ProbeOutcome(
            _STATUS_PASS if ready else _STATUS_FAIL,
            "display_topology_ready" if ready else "display_topology_incomplete",
            {
                "display_count": len(displays),
                "dpi_complete": dpi_complete,
                "mixed_dpi": len(set(dpis)) > 1,
                "negative_origin": negative_origin,
                "primary_count": primary_count,
                "topology_present": bool(payload.get("topology_token")),
            },
        )
    except Exception as exc:
        return ProbeOutcome(
            _STATUS_FAIL,
            "display_probe_failed",
            {"error": True, "error_type_code": _error_type_code(exc)},
        )


# -.-.-.-
def _probe_foreground_window() -> ProbeOutcome:
    guarded = _windows_guard()
    if guarded is not None:
        return guarded
    try:
        import win32gui

        available = int(win32gui.GetForegroundWindow() or 0) != 0
        return ProbeOutcome(
            _STATUS_PASS if available else _STATUS_FAIL,
            "foreground_ready" if available else "foreground_unavailable",
            {"foreground_available": available},
        )
    except Exception as exc:
        return ProbeOutcome(
            _STATUS_FAIL,
            "foreground_probe_failed",
            {"error": True, "error_type_code": _error_type_code(exc)},
        )


# -.-.-.-
def _error_type_code(exc: BaseException) -> int:
    """Return a stable non-content error classifier for reports."""
    name = type(exc).__name__.encode("utf-8", errors="replace")
    value = 0
    for byte in name:
        value = ((value * 33) + byte) & 0xFFFF
    return value


_DEFAULT_PROBES: dict[str, Probe] = {
    "env.windows": _probe_windows,
    "env.python": _probe_python,
    "deps.windows_control": _probe_windows_control_dependencies,
    "deps.ui": _probe_ui_dependency,
    "deps.audio": _probe_audio_devices,
    "deps.browser": _probe_browser_runtime,
    "display.topology": _probe_display_topology,
    "windows.foreground": _probe_foreground_window,
}


# -.-.-.-
def run_safe(
    *,
    case_ids: Sequence[str] | None = None,
    probes: Mapping[str, Probe] | None = None,
) -> dict[str, Any]:
    matrix = build_matrix()
    selected = set(case_ids or ())
    handlers = dict(_DEFAULT_PROBES)
    if probes:
        handlers.update(probes)

    results: list[dict[str, Any]] = []
    for case in matrix:
        if case.mode != "automatic":
            continue
        if selected and case.case_id not in selected:
            continue
        probe = handlers.get(case.case_id)
        if probe is None:
            outcome = ProbeOutcome(_STATUS_NOT_RUN, "probe_not_registered")
        else:
            try:
                outcome = probe()
            except Exception as exc:
                outcome = ProbeOutcome(
                    _STATUS_FAIL,
                    "probe_exception",
                    {"error": True, "error_type_code": _error_type_code(exc)},
                )
        results.append(outcome.public_dict(case_id=case.case_id))
    return build_report("safe", results)


# -.-.-.-
def build_report(mode: str, results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(item) for item in results]
    counts = {status: 0 for status in sorted(_ALLOWED_STATUSES)}
    for item in rows:
        status = str(item.get("status") or _STATUS_NOT_RUN)
        if status not in counts:
            status = _STATUS_FAIL
        counts[status] += 1

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": _safe_token(mode, fallback="unknown"),
        "source_revision": _source_revision(),
        "runtime": {
            "windows": platform.system() == "Windows",
            "python_major": int(sys.version_info.major),
            "python_minor": int(sys.version_info.minor),
        },
        "summary": counts,
        "results": rows,
    }
    return report


# -.-.-.-
def _source_revision() -> str | None:
    root = Path(__file__).resolve().parents[1]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        candidate = result.stdout.strip().lower()
        return candidate if result.returncode == 0 and _GIT_SHA_RE.fullmatch(candidate) else None
    except Exception:
        return None


# -.-.-.-
def _matrix_selection(case_ids: Sequence[str] | None) -> list[MatrixCase]:
    selected = set(case_ids or ())
    matrix = list(build_matrix())
    if not selected:
        return matrix
    known = {case.case_id for case in matrix}
    unknown = selected - known
    if unknown:
        raise ValueError("Unknown E2E case id.")
    return [case for case in matrix if case.case_id in selected]


# -.-.-.-
def guided_run(
    *,
    case_ids: Sequence[str] | None = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> dict[str, Any]:
    cases = _matrix_selection(case_ids)
    automatic_ids = [case.case_id for case in cases if case.mode == "automatic"]
    automatic = run_safe(case_ids=automatic_ids)
    results = list(automatic["results"])

    for case in cases:
        if case.mode != "manual":
            continue
        output_fn("")
        output_fn(f"[{case.case_id}] {case.title}")
        output_fn(case.description)
        for index, instruction in enumerate(case.instructions, start=1):
            output_fn(f"  {index}. {instruction}")
        while True:
            answer = input_fn("Resultado [p=pass, f=fail, s=skip, q=quit]: ").strip().lower()
            if answer in {"p", "f", "s", "q"}:
                break
        if answer == "q":
            results.append(
                ProbeOutcome(_STATUS_NOT_RUN, "guided_run_stopped").public_dict(
                    case_id=case.case_id
                )
            )
            break
        status = {"p": _STATUS_PASS, "f": _STATUS_FAIL, "s": _STATUS_SKIP}[answer]
        reason = {
            "p": "human_verified",
            "f": "human_observed_failure",
            "s": "human_skipped",
        }[answer]
        results.append(ProbeOutcome(status, reason).public_dict(case_id=case.case_id))

    return build_report("guided", results)


# -.-.-.-
def write_report(report: Mapping[str, Any], path: str, *, force: bool = False) -> Path:
    target = Path(path).expanduser().resolve()
    if target.exists() and not force:
        raise FileExistsError("Report already exists. Use --force to replace it.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(dict(report), ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


# -.-.-.-
def _print_matrix(cases: Sequence[MatrixCase], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps([case.public_dict() for case in cases], ensure_ascii=False, indent=2))
        return
    print("Antonella ANT-275 — physical Windows E2E matrix")
    print("Automatic probes are read-only. Manual cases never authorize real destructive/external effects.")
    for case in cases:
        fixture = " · fixture" if case.requires_fixture else ""
        print(f"- {case.case_id:<31} {case.mode:<9} · {case.category}{fixture}")


# -.-.-.-
def _report_exit_code(report: Mapping[str, Any]) -> int:
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    return 1 if int(summary.get(_STATUS_FAIL, 0) or 0) > 0 else 0


# -.-.-.-
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safe harness for Antonella's physical Windows E2E validation.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="List the E2E matrix (default).")
    mode.add_argument("--run-safe", action="store_true", help="Run read-only automatic probes.")
    mode.add_argument("--guided", action="store_true", help="Run probes and guide manual physical checks.")
    parser.add_argument("--case", action="append", dest="case_ids", help="Limit to one case id; repeatable.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--output", help="Optional JSON report path. Existing files are not overwritten by default.")
    parser.add_argument("--force", action="store_true", help="Allow replacing an explicit --output report file.")
    return parser


# -.-.-.-
def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        cases = _matrix_selection(args.case_ids)
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    if not args.run_safe and not args.guided:
        _print_matrix(cases, as_json=args.json)
        return 0

    if args.guided:
        if not sys.stdin.isatty():
            parser.error("--guided requires an interactive terminal.")
            return 2
        report = guided_run(case_ids=args.case_ids)
    else:
        automatic_ids = [case.case_id for case in cases if case.mode == "automatic"]
        report = run_safe(case_ids=automatic_ids)

    if args.output:
        try:
            write_report(report, args.output, force=bool(args.force))
        except (OSError, FileExistsError) as exc:
            print(f"Could not write report: {type(exc).__name__}", file=sys.stderr)
            return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2))
    else:
        summary = report["summary"]
        print(
            "E2E summary · "
            f"pass={summary[_STATUS_PASS]} fail={summary[_STATUS_FAIL]} "
            f"skip={summary[_STATUS_SKIP]} not_run={summary[_STATUS_NOT_RUN]}"
        )
        if args.output:
            print("Machine-readable report written to the explicit output path.")
    return _report_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
