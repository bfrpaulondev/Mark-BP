"""Safe local fixture window for Windows physical E2E (ANT-275 C5).

A controllable PyQt6 window: stable title, a button that changes the
title, a textbox and a checkbox — enough surface for focus/UIA/mouse/
keyboard cases without touching real applications.

Usage (physical machine only):
    python scripts/windows_e2e/fixtures/fixture_app.py --duration 30
"""

from __future__ import annotations

import argparse
import os

os.environ.setdefault("QT_QPA_PLATFORM", "windows")

BASE_TITLE = "Antonella E2E Fixture"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=int, default=60, help="auto-close seconds")
    args = parser.parse_args()

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import (
        QApplication,
        QCheckBox,
        QLineEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    app = QApplication.instance() or QApplication([])
    window = QWidget()
    window.setWindowTitle(BASE_TITLE)
    window.resize(480, 240)

    layout = QVBoxLayout(window)

    textbox = QLineEdit(window)
    textbox.setPlaceholderText("E2E textbox")
    layout.addWidget(textbox)

    checkbox = QCheckBox("E2E checkbox", window)
    layout.addWidget(checkbox)

    def _change_title() -> None:
        window.setWindowTitle(BASE_TITLE + " [CHANGED]")

    button = QPushButton("Mudar título", window)
    button.clicked.connect(_change_title)
    layout.addWidget(button)

    QTimer.singleShot(max(1, args.duration) * 1000, app.quit)
    window.show()
    app.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
