"""Deterministic Qt offscreen screenshots for ANT-270 visual regression.

Renders the main window in every operational state plus the Agent Control
Center (empty/approval/failed/done) and the settings dialog, saving PNGs to
an output folder. Synthetic content only — never prompts, keys, clipboard
or private user content.

OFFSCREEN RENDERING IS NOT PHYSICAL WINDOWS E2E: it validates structure,
layout sanity and state wiring, not real DPI/monitor rendering.

Usage: python scripts/ui_visual_states.py [--out visual_states]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONUTF8", "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _ui_state_values() -> list[str]:
    """Load the Qt-free runtime state module without importing the ui package."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "antonella_runtime_state", ROOT / "ui" / "runtime_state.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return [state.value for state in module.UiState]


WINDOW_STATES = _ui_state_values()
DIALOG_CASES = ("empty", "awaiting_approval", "failed", "done")


def _grab(widget, out_dir: Path, name: str) -> Path:
    widget.repaint()
    path = out_dir / f"{name}.png"
    widget.grab().save(str(path), "PNG")
    return path


def render_all(out_dir: Path) -> list[Path]:
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from ui import AntonellaWindow
    from ui.agent_control import AgentControlDialog

    # The one-shot config dialog (QTimer.singleShot in __init__) captures the
    # bound method at construction time, so the guard must be class-level
    # BEFORE instantiation — a modal QInputDialog during processEvents would
    # block the offscreen run forever.
    AntonellaWindow._configure_api_key = lambda self: None

    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    window = AntonellaWindow()
    window.show()
    app.processEvents()

    for line in (
        "SYS: sessão de demonstração",
        "TU: exemplo sintético",
        "Antonella: resposta sintética",
    ):
        window._log.append_event(line)
    app.processEvents()

    for state in WINDOW_STATES:
        window._apply_state(state)
        app.processEvents()
        saved.append(_grab(window, out_dir, f"window_{state.lower()}"))

    host = window

    class _Log:
        append_event = staticmethod(lambda text: None)

    host._log = _Log()

    session_states = {
        "empty": {"state": "idle"},
        "awaiting_approval": {
            "state": "awaiting_approval",
            "objective": "Tarefa de demonstração sintética",
            "last_action": "apagar ficheiro de demonstração",
            "step": 3,
            "model_calls": 2,
            "saved_model_calls": 1,
        },
        "failed": {
            "state": "failed",
            "objective": "Tarefa de demonstração sintética",
            "last_error": "Não consegui confirmar que a janela mudou.",
            "step": 4,
        },
        "done": {
            "state": "done",
            "objective": "Tarefa de demonstração sintética",
            "result": "Tarefa de demonstração concluída.",
            "step": 5,
        },
    }

    for case in DIALOG_CASES:
        dialog = AgentControlDialog(host)

        class _Stub:
            def __init__(self, payload: dict) -> None:
                self._payload = payload

            def status(self) -> dict:
                return dict(self._payload)

            def approve_once(self) -> dict:
                return {"ok": True}

            def stop(self) -> dict:
                return {"ok": True}

        dialog._session = _Stub(session_states[case])
        dialog.show()
        app.processEvents()
        saved.append(_grab(dialog, out_dir, f"agent_{case}"))
        dialog.close()
        dialog.deleteLater()

    from ui.settings_dialog import AntonellaSettingsDialog

    settings = AntonellaSettingsDialog(host)
    # Privacy: provider keys are rendered only as readiness booleans; force
    # the only user-configurable visible string to synthetic content.
    if getattr(settings, "_voice", None) is not None:
        settings._voice.setText("Voz de demonstração")
    settings.show()
    app.processEvents()
    saved.append(_grab(settings, out_dir, "settings"))
    settings.close()
    settings.deleteLater()

    window.hide()
    window.close()
    window.deleteLater()
    app.processEvents()
    return saved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="visual_states", help="output folder for PNGs")
    args = parser.parse_args()

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    saved = render_all(out_dir)
    for path in saved:
        print(f"saved {path.relative_to(ROOT)}")
    print(f"visual states: {len(saved)} screenshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
