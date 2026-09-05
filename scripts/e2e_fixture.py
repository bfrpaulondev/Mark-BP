from __future__ import annotations

import sys

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class AntonellaE2EFixture(QMainWindow):
    """Deterministic local UI fixture with no network/file/destructive effects."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Antonella E2E Fixture")
        self.resize(820, 640)
        self.setMinimumSize(680, 520)
        self._target_at_bottom = False
        self._pulse = 0
        self._simulated_send_count = 0

        root = QWidget()
        root.setObjectName("fixtureRoot")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        title = QLabel("ANTONELLA E2E FIXTURE")
        title.setObjectName("fixtureTitle")
        title.setAccessibleName("Antonella E2E Fixture title")
        title.setStyleSheet("font-size:22px;font-weight:700;")
        layout.addWidget(title)

        warning = QLabel(
            "Local simulation only · no network · no files · no payments · no destructive effects"
        )
        warning.setObjectName("fixtureSafetyNotice")
        warning.setAccessibleName("Local simulation safety notice")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        self._state = QLabel("STATE: READY")
        self._state.setObjectName("fixtureState")
        self._state.setAccessibleName("Fixture state")
        self._state.setStyleSheet("font-size:16px;font-weight:600;")
        layout.addWidget(self._state)

        self._input = QLineEdit()
        self._input.setObjectName("fixtureInput")
        self._input.setAccessibleName("Safe local text field")
        self._input.setPlaceholderText("Type a safe local value")
        layout.addWidget(self._input)

        row = QHBoxLayout()
        self._panel_button = QPushButton("Open local panel")
        self._panel_button.setObjectName("fixtureOpenPanel")
        self._panel_button.setAccessibleName("Open local panel")
        self._panel_button.clicked.connect(self._open_panel)
        row.addWidget(self._panel_button)

        self._move_button = QPushButton("Move visual target")
        self._move_button.setObjectName("fixtureMoveTarget")
        self._move_button.setAccessibleName("Move visual target")
        self._move_button.clicked.connect(self._move_target)
        row.addWidget(self._move_button)

        self._reset_button = QPushButton("Reset fixture")
        self._reset_button.setObjectName("fixtureReset")
        self._reset_button.setAccessibleName("Reset fixture")
        self._reset_button.clicked.connect(self._reset)
        row.addWidget(self._reset_button)
        layout.addLayout(row)

        self._animate = QCheckBox("Animate harmless indicator")
        self._animate.setObjectName("fixtureAnimate")
        self._animate.setAccessibleName("Animate harmless indicator")
        layout.addWidget(self._animate)

        self._pulse_label = QLabel("PULSE: 0")
        self._pulse_label.setObjectName("fixturePulse")
        self._pulse_label.setAccessibleName("Harmless animation counter")
        layout.addWidget(self._pulse_label)

        self._top_target_host = QFrame()
        self._top_target_layout = QHBoxLayout(self._top_target_host)
        self._top_target_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._top_target_host)

        self._target_button = QPushButton("Visual target")
        self._target_button.setObjectName("fixtureVisualTarget")
        self._target_button.setAccessibleName("Visual target")
        self._target_button.clicked.connect(self._target_clicked)
        self._top_target_layout.addWidget(self._target_button)

        scroll = QScrollArea()
        scroll.setObjectName("fixtureScroll")
        scroll.setAccessibleName("Fixture scroll area")
        scroll.setWidgetResizable(True)
        scroll_host = QWidget()
        self._scroll_layout = QVBoxLayout(scroll_host)
        for index in range(1, 31):
            label = QLabel(f"Harmless row {index:02d}")
            label.setObjectName(f"fixtureRow{index:02d}")
            self._scroll_layout.addWidget(label)
        self._scroll_target = QLabel("SCROLL TARGET")
        self._scroll_target.setObjectName("fixtureScrollTarget")
        self._scroll_target.setAccessibleName("Scroll target")
        self._scroll_target.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll_target.setStyleSheet("font-size:18px;font-weight:700;padding:20px;")
        self._scroll_layout.addWidget(self._scroll_target)
        self._bottom_target_host = QFrame()
        self._bottom_target_layout = QHBoxLayout(self._bottom_target_host)
        self._bottom_target_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.addWidget(self._bottom_target_host)
        scroll.setWidget(scroll_host)
        layout.addWidget(scroll, stretch=1)

        self._simulated_send = QPushButton("Simulated send — local only")
        self._simulated_send.setObjectName("fixtureSimulatedSend")
        self._simulated_send.setAccessibleName("Simulated send local only")
        self._simulated_send.setToolTip(
            "Test-only sensitive-looking control. It performs no external operation."
        )
        self._simulated_send.clicked.connect(self._simulate_send)
        layout.addWidget(self._simulated_send)

        self._timer = QTimer(self)
        self._timer.setInterval(650)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self.setStyleSheet(
            "QMainWindow{background:#10111a;color:#f4f1ff;}"
            "QLabel,QCheckBox{color:#f4f1ff;}"
            "QLineEdit{background:#181a27;color:#f4f1ff;border:1px solid #393c55;"
            "border-radius:7px;padding:9px;}"
            "QPushButton{background:#242038;color:#f4f1ff;border:1px solid #5f4b83;"
            "border-radius:7px;padding:9px 12px;}"
            "QPushButton:hover{background:#31284a;}"
            "QScrollArea{background:#151621;border:1px solid #303247;border-radius:8px;}"
            "QScrollArea QWidget{background:#151621;}"
        )

    # -.-.-.-
    def _set_state(self, value: str) -> None:
        self._state.setText(f"STATE: {value}")

    # -.-.-.-
    def _open_panel(self) -> None:
        self._set_state("LOCAL_PANEL_OPEN")

    # -.-.-.-
    def _target_clicked(self) -> None:
        self._set_state("VISUAL_TARGET_CLICKED")

    # -.-.-.-
    def _move_target(self) -> None:
        self._top_target_layout.removeWidget(self._target_button)
        self._bottom_target_layout.removeWidget(self._target_button)
        self._target_at_bottom = not self._target_at_bottom
        if self._target_at_bottom:
            self._bottom_target_layout.addWidget(self._target_button)
            self._set_state("TARGET_MOVED_BOTTOM")
        else:
            self._top_target_layout.addWidget(self._target_button)
            self._set_state("TARGET_MOVED_TOP")
        self._target_button.show()

    # -.-.-.-
    def _simulate_send(self) -> None:
        self._simulated_send_count += 1
        self._set_state(f"SIMULATED_SEND_{self._simulated_send_count}")

    # -.-.-.-
    def _reset(self) -> None:
        self._input.clear()
        self._animate.setChecked(False)
        self._pulse = 0
        self._pulse_label.setText("PULSE: 0")
        self._simulated_send_count = 0
        if self._target_at_bottom:
            self._move_target()
        self._set_state("READY")

    # -.-.-.-
    def _tick(self) -> None:
        if not self._animate.isChecked():
            return
        self._pulse = (self._pulse + 1) % 1000
        self._pulse_label.setText(f"PULSE: {self._pulse}")


# -.-.-.-
def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = AntonellaE2EFixture()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
