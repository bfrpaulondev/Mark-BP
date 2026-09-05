from __future__ import annotations

import html
import json
import math
import os
import platform
import random
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from config import get_config, get_gemini_key
from config.settings import read_legacy_config, write_legacy_config
from ui.runtime_state import STATE_LABELS_PT, UiRuntimeState, UiState, normalize_state
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


ANTONELLA_UI_IMPLEMENTATION = "reference-v2"
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config" / "api_keys.json"
_OS = platform.system()


class Palette:
    BACKGROUND = "#05060b"
    SURFACE = "#080910"
    SURFACE_2 = "#0b0c15"
    BORDER = "#24263a"
    BORDER_HOVER = "#35384f"
    TEXT = "#f5f2ff"
    TEXT_MUTED = "#8f93b8"
    TEXT_FAINT = "#626782"
    VIOLET = "#9b57ff"
    VIOLET_SOFT = "#bd91ff"
    PINK = "#ff5ca8"
    BLUE = "#55b8ff"
    GREEN = "#68e6b2"
    RED = "#ff6688"


def _font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    family = "Segoe UI Variable" if _OS == "Windows" else "Inter"
    return QFont(family, size, weight)


def _icon_button(text: str, *, accent: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFont(_font(12, QFont.Weight.DemiBold))
    button.setFixedHeight(46)
    if accent:
        button.setStyleSheet(
            f"QPushButton{{background:{Palette.VIOLET};color:#09060f;border:0;border-radius:11px;"
            "padding:0 18px;font-weight:700;}"
            f"QPushButton:hover{{background:{Palette.VIOLET_SOFT};}}"
            f"QPushButton:focus{{background:{Palette.VIOLET_SOFT};outline:none;}}"
        )
    else:
        button.setStyleSheet(
            f"QPushButton{{background:{Palette.SURFACE_2};color:{Palette.TEXT_MUTED};"
            f"border:1px solid {Palette.BORDER};border-radius:11px;padding:0 14px;}}"
            f"QPushButton:hover{{color:{Palette.TEXT};border-color:{Palette.BORDER_HOVER};}}"
            f"QPushButton:focus{{color:{Palette.TEXT};border-color:{Palette.VIOLET};outline:none;}}"
        )
    return button


class MetricCard(QFrame):
    def __init__(
        self,
        title: str,
        value: str,
        *,
        accent: str,
        progress: int | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._accent = accent
        self.setObjectName("metricCard")
        self.setStyleSheet(
            f"QFrame#metricCard{{background:{Palette.SURFACE};"
            f"border:1px solid {Palette.BORDER};border-radius:12px;}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title.upper())
        self.title_label.setFont(_font(8, QFont.Weight.Medium))
        self.title_label.setStyleSheet(f"color:{Palette.TEXT_MUTED};letter-spacing:1px;")
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setFont(_font(13, QFont.Weight.DemiBold))
        self.value_label.setStyleSheet(f"color:{accent};")
        layout.addWidget(self.value_label)

        self.progress: QProgressBar | None = None
        if progress is not None:
            self.progress = QProgressBar()
            self.progress.setRange(0, 100)
            self.progress.setValue(progress)
            self.progress.setTextVisible(False)
            self.progress.setFixedHeight(4)
            self.progress.setStyleSheet(
                f"QProgressBar{{background:#1b1d2b;border:0;border-radius:2px;}}"
                f"QProgressBar::chunk{{background:{accent};border-radius:2px;}}"
            )
            layout.addSpacing(2)
            layout.addWidget(self.progress)

    def set_value(self, value: str, progress: int | None = None) -> None:
        self.value_label.setText(value)
        if self.progress is not None and progress is not None:
            self.progress.setValue(max(0, min(100, progress)))


class ParticleOrb(QWidget):
    """Purple neural particle sphere inspired by the approved Antonella reference."""

    PARTICLE_COUNT = 320

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.state = UiState.INITIALISING
        self.muted = False
        self.speaking = False
        self._phase = 0.0
        self._energy = 0.16
        self._target_energy = 0.16
        self._particles = self._make_particles()
        # 320 keeps the declared window minimum (980x650) achievable:
        # 44 margins + 36 gutters + 238 + 310 panels + 320 = 948 <= 980.
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    # -.-.-.-
    def start_animation(self) -> None:
        if not self._timer.isActive():
            self._timer.start(33)

    # -.-.-.-
    def stop_animation(self) -> None:
        self._timer.stop()

    def _make_particles(self) -> list[tuple[float, float, float, float, float]]:
        rng = random.Random(1709)
        particles: list[tuple[float, float, float, float, float]] = []
        for _ in range(self.PARTICLE_COUNT):
            z = rng.uniform(-1.0, 1.0)
            angle = rng.uniform(0.0, math.tau)
            radial = math.sqrt(max(0.0, 1.0 - z * z))
            depth_bias = rng.uniform(0.72, 1.0)
            size = rng.uniform(0.8, 2.4)
            twinkle = rng.uniform(0.0, math.tau)
            particles.append(
                (
                    radial * math.cos(angle) * depth_bias,
                    z * depth_bias,
                    radial * math.sin(angle) * depth_bias,
                    size,
                    twinkle,
                )
            )
        return particles

    # Subtle per-state motion: (rotation speed, target energy). Bounded and
    # event-driven in spirit — no extra timers, same 30 FPS tick as before.
    _STATE_MOTION: dict[UiState, tuple[float, float]] = {
        UiState.IDLE: (0.008, 0.15),
        UiState.LISTENING: (0.010, 0.28),
        UiState.THINKING: (0.014, 0.44),
        UiState.OBSERVING: (0.012, 0.24),
        UiState.EXECUTING: (0.018, 0.50),
        UiState.VERIFYING: (0.012, 0.36),
        UiState.RECOVERING: (0.010, 0.30),
        UiState.WAITING_APPROVAL: (0.006, 0.40),
        UiState.COMPLETED: (0.006, 0.20),
        UiState.FAILED: (0.004, 0.12),
        UiState.CANCELLED: (0.004, 0.10),
        UiState.INITIALISING: (0.010, 0.16),
        UiState.SPEAKING: (0.020, 0.62),
        UiState.SLEEPING: (0.005, 0.10),
        UiState.MUTED: (0.004, 0.05),
    }

    def _tick(self) -> None:
        speed, target_energy = self._STATE_MOTION.get(self.state, (0.008, 0.15))
        self._phase += speed

        if self.muted:
            self._target_energy = 0.05
        elif self.speaking:
            self._target_energy = random.uniform(0.62, 0.92)
        else:
            self._target_energy = target_energy

        self._energy += (self._target_energy - self._energy) * 0.08
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(Palette.BACKGROUND))

        width = self.width()
        height = self.height()
        center = QPointF(width / 2, height / 2 - 12)
        radius = min(width, height) * (0.27 + self._energy * 0.025)

        sin_y = math.sin(self._phase)
        cos_y = math.cos(self._phase)
        sin_x = math.sin(self._phase * 0.43) * 0.18
        cos_x = math.cos(self._phase * 0.43) * 0.18 + 0.98

        projected: list[tuple[float, float, float, float, float]] = []
        for x, y, z, size, twinkle in self._particles:
            xr = x * cos_y - z * sin_y
            zr = x * sin_y + z * cos_y
            yr = y * cos_x - zr * sin_x
            zr2 = y * sin_x + zr * cos_x

            pulse = 1.0 + math.sin(self._phase * 2.4 + twinkle) * (0.02 + self._energy * 0.045)
            perspective = 0.80 + (zr2 + 1.0) * 0.16
            px = center.x() + xr * radius * pulse * perspective
            py = center.y() + yr * radius * pulse * perspective
            projected.append((zr2, px, py, size, twinkle))

        projected.sort(key=lambda item: item[0])

        for depth, px, py, size, twinkle in projected:
            front = (depth + 1.0) / 2.0
            alpha = int(55 + 155 * front)
            alpha += int(math.sin(self._phase * 4.0 + twinkle) * 18)
            alpha = max(30, min(235, alpha))

            if self.muted:
                color = QColor("#695d80")
            elif front > 0.78 and int(twinkle * 10) % 7 == 0:
                color = QColor(Palette.PINK)
            elif front > 0.68 and int(twinkle * 10) % 5 == 0:
                color = QColor(Palette.BLUE)
            else:
                color = QColor(Palette.VIOLET)

            color.setAlpha(alpha)
            point_size = max(0.75, size * (0.72 + front * 0.62) * (1.0 + self._energy * 0.12))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(px, py), point_size, point_size)

        label, color = self._state_label()
        painter.setFont(_font(10, QFont.Weight.DemiBold))
        painter.setPen(QColor(color))
        label_rect = QRectF(0, center.y() + radius + 48, width, 26)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)

    def _state_label(self) -> tuple[str, str]:
        if self.muted:
            return "MICROFONE EM PAUSA", Palette.RED
        colors = {
            UiState.INITIALISING: Palette.TEXT_MUTED,
            UiState.IDLE: Palette.TEXT_MUTED,
            UiState.SLEEPING: Palette.TEXT_FAINT,
            UiState.LISTENING: Palette.VIOLET_SOFT,
            UiState.THINKING: Palette.VIOLET_SOFT,
            UiState.OBSERVING: Palette.VIOLET_SOFT,
            UiState.EXECUTING: Palette.VIOLET_SOFT,
            UiState.VERIFYING: Palette.BLUE,
            UiState.RECOVERING: Palette.BLUE,
            UiState.WAITING_APPROVAL: Palette.PINK,
            UiState.SPEAKING: Palette.PINK,
            UiState.COMPLETED: Palette.GREEN,
            UiState.FAILED: Palette.RED,
            UiState.CANCELLED: Palette.TEXT_FAINT,
            UiState.MUTED: Palette.RED,
        }
        label = STATE_LABELS_PT.get(self.state, str(self.state))
        return label, colors.get(self.state, Palette.VIOLET_SOFT)


class LogView(QTextEdit):
    def __init__(self, assistant_name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.assistant_name = assistant_name
        self.setReadOnly(True)
        self.setFont(_font(9))
        # Bounded history: old entries drop as new ones arrive.
        self.document().setMaximumBlockCount(400)
        self.setStyleSheet(
            f"QTextEdit{{background:transparent;color:{Palette.TEXT_MUTED};border:0;padding:0;}}"
            "QScrollBar:vertical{background:transparent;width:6px;}"
            f"QScrollBar::handle:vertical{{background:{Palette.BORDER};border-radius:3px;min-height:22px;}}"
        )
        self.document().setDefaultStyleSheet(
            "body{font-family:'Segoe UI Variable','Segoe UI',sans-serif;}"
            f".meta{{color:{Palette.TEXT_FAINT};font-size:8pt;letter-spacing:1px;}}"
            f".user{{color:{Palette.TEXT};font-weight:600;}}"
            f".ai{{color:{Palette.VIOLET_SOFT};font-weight:600;}}"
            f".sys{{color:{Palette.TEXT_MUTED};}}"
            f".err{{color:{Palette.RED};}}"
        )

    def append_event(self, text: str) -> None:
        clean = (
            text.replace("J.A.R.V.I.S.", self.assistant_name)
            .replace("JARVIS", self.assistant_name)
            .replace("Jarvis", self.assistant_name)
            # Exact legacy product token only; a bare "Mark" is a common
            # personal name and must never be rewritten.
            .replace("MARK LI", self.assistant_name)
        )
        escaped = html.escape(clean)
        lower = clean.lower()

        if lower.startswith("you:"):
            body = escaped.split(":", 1)[1].strip()
            markup = f'<p><span class="meta">TU</span><br><span class="user">{body}</span></p>'
        elif lower.startswith(self.assistant_name.lower() + ":"):
            body = escaped.split(":", 1)[1].strip()
            markup = f'<p><span class="meta">ANTONELLA</span><br><span class="ai">{body}</span></p>'
        elif lower.startswith("err:"):
            markup = f'<p class="err">{escaped}</p>'
        else:
            if lower.startswith("sys:"):
                escaped = f"<b>SYS:</b>{escaped.split(':', 1)[1]}"
            markup = f'<p class="sys">{escaped}</p>'

        self.append(markup)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class DropZone(QFrame):
    file_dropped = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("dropZone")
        self.setMinimumHeight(90)
        self.setStyleSheet(
            f"QFrame#dropZone{{background:{Palette.SURFACE};border:1px dashed {Palette.BORDER_HOVER};"
            "border-radius:12px;}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(5)

        icon = QLabel("⇧")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(_font(19, QFont.Weight.Medium))
        icon.setStyleSheet(f"color:{Palette.VIOLET};")
        layout.addWidget(icon)

        self.label = QLabel("Largar ficheiro")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(_font(9, QFont.Weight.Medium))
        self.label.setStyleSheet(f"color:{Palette.TEXT_MUTED};")
        layout.addWidget(self.label)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if path:
            self.file_dropped.emit(path)
            event.acceptProposedAction()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.file_dropped.emit("")
        super().mousePressEvent(event)


class AntonellaWindow(QMainWindow):
    _log_signal = pyqtSignal(str)
    _state_signal = pyqtSignal(str)
    _runtime_state_signal = pyqtSignal(object)  # UiRuntimeState snapshot (thread-safe)
    _content_signal = pyqtSignal(str, str)
    _reconfig_signal = pyqtSignal()
    _camera_stream_signal = pyqtSignal(bool)
    _camera_frame_signal = pyqtSignal(bytes)

    def __init__(self, _face_path: str = ""):
        super().__init__()
        config = get_config()
        self._assistant_name = (config.get("assistant_name") or "Antonella").strip() or "Antonella"
        self._voice_name = (config.get("voice_name") or "Kore").strip() or "Kore"
        self._muted = False
        self._current_file: str | None = None
        self._ready = bool(get_gemini_key())
        self.on_text_command: Callable[[str], None] | None = None
        self.on_remote_clicked = None
        self.on_interrupt: Callable[[], None] | None = None
        self.get_plugins = None
        self.request_say = None
        self._cam_stop = threading.Event()
        self._last_net_bytes = 0
        self._last_net_time = time.monotonic()

        self.setWindowTitle("Antonella")
        self.setMinimumSize(980, 650)
        self.resize(1180, 760)
        self.setStyleSheet(
            f"QMainWindow{{background:{Palette.BACKGROUND};}}"
            f"QWidget{{background:{Palette.BACKGROUND};}}"
            "QLabel{background:transparent;}"
        )

        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            self.move(
                geometry.x() + max(0, (geometry.width() - self.width()) // 2),
                geometry.y() + max(0, (geometry.height() - self.height()) // 2),
            )

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 22, 22, 18)
        root.setSpacing(16)

        root.addLayout(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(self._build_metrics_column(), stretch=0)
        body.addLayout(self._build_center_column(), stretch=1)
        body.addWidget(self._build_log_column(), stretch=0)
        root.addLayout(body, stretch=1)

        root.addLayout(self._build_command_bar())

        self._log_signal.connect(self._log.append_event)
        self._state_signal.connect(self._apply_state)
        self._runtime_state_signal.connect(self._apply_runtime_state)
        self._content_signal.connect(self._show_content)
        self._reconfig_signal.connect(self._configure_api_key)
        self._camera_stream_signal.connect(self._set_camera_mode)
        self._camera_frame_signal.connect(self._show_camera_frame)

        mute_shortcut = QShortcut(QKeySequence("F4"), self)
        mute_shortcut.activated.connect(self._toggle_mute)
        interrupt_shortcut = QShortcut(QKeySequence("Escape"), self)
        interrupt_shortcut.activated.connect(self._do_interrupt)
        fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        fullscreen_shortcut.activated.connect(self._toggle_fullscreen)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

        self._metrics_timer = QTimer(self)
        self._metrics_timer.timeout.connect(self._update_metrics)
        self._metrics_timer.start(1600)
        self._update_metrics()

        if self._ready:
            self._log.append_event("SYS: modelos carregados")
            self._log.append_event("SYS: memória de contexto activa")
        else:
            self._log.append_event("SYS: configura a chave Gemini para iniciar")
            QTimer.singleShot(250, self._configure_api_key)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(12)

        identity = QVBoxLayout()
        identity.setSpacing(2)

        name = QLabel("ANTONELLA")
        name.setFont(_font(20, QFont.Weight.Medium))
        name.setStyleSheet(f"color:{Palette.VIOLET_SOFT};letter-spacing:3px;")
        subtitle = QLabel("Adaptive neural companion")
        subtitle.setFont(_font(10))
        subtitle.setStyleSheet(f"color:{Palette.TEXT_MUTED};")
        identity.addWidget(name)
        identity.addWidget(subtitle)
        header.addLayout(identity)
        header.addStretch()

        clock_wrap = QVBoxLayout()
        clock_wrap.setSpacing(0)
        self._clock_label = QLabel("")
        self._clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._clock_label.setFont(_font(14, QFont.Weight.DemiBold))
        self._clock_label.setStyleSheet(f"color:{Palette.VIOLET_SOFT};")
        self._date_label = QLabel("")
        self._date_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._date_label.setFont(_font(9))
        self._date_label.setStyleSheet(f"color:{Palette.TEXT_MUTED};")
        clock_wrap.addWidget(self._clock_label)
        clock_wrap.addWidget(self._date_label)
        header.addLayout(clock_wrap)

        settings_button = QPushButton("•••")
        settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_button.setFixedSize(38, 34)
        settings_button.setFont(_font(11, QFont.Weight.Bold))
        settings_button.setAccessibleName("Abrir definições")
        settings_button.setToolTip("Definições")
        settings_button.setStyleSheet(
            f"QPushButton{{background:{Palette.SURFACE_2};color:{Palette.TEXT_MUTED};"
            f"border:1px solid {Palette.BORDER};border-radius:9px;}}"
            f"QPushButton:hover{{color:{Palette.TEXT};border-color:{Palette.BORDER_HOVER};}}"
            f"QPushButton:focus{{color:{Palette.TEXT};border-color:{Palette.VIOLET};outline:none;}}"
        )
        settings_button.clicked.connect(self._configure_api_key)
        header.addWidget(settings_button)
        return header

    def _build_metrics_column(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(238)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self._cpu_card = MetricCard("CPU", "--", accent=Palette.VIOLET, progress=0)
        self._mem_card = MetricCard("MEM", "--", accent=Palette.PINK, progress=0)
        self._net_card = MetricCard("NET", "--", accent=Palette.BLUE)
        self._core_card = MetricCard("CORE STATUS", "⟐ Sincronizado", accent=Palette.VIOLET)
        layout.addWidget(self._cpu_card)
        layout.addWidget(self._mem_card)
        layout.addWidget(self._net_card)
        layout.addWidget(self._core_card)
        layout.addStretch()
        return panel

    def _build_center_column(self) -> QVBoxLayout:
        center = QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(8)

        self._visual_stack = QStackedWidget()
        self._visual_stack.setStyleSheet("QStackedWidget{border:0;background:transparent;}")
        self.orb = ParticleOrb()
        self._visual_stack.addWidget(self.orb)

        self._camera_label = QLabel("A preparar câmara…")
        self._camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._camera_label.setStyleSheet(
            f"color:{Palette.TEXT_MUTED};background:{Palette.SURFACE};"
            f"border:1px solid {Palette.BORDER};border-radius:14px;"
        )
        self._visual_stack.addWidget(self._camera_label)
        center.addWidget(self._visual_stack, stretch=1)

        self._content_card = QFrame()
        self._content_card.setStyleSheet(
            f"QFrame{{background:{Palette.SURFACE};border:1px solid {Palette.BORDER};border-radius:12px;}}"
        )
        content_layout = QVBoxLayout(self._content_card)
        content_layout.setContentsMargins(14, 10, 14, 10)
        self._content_title = QLabel("CONTEXTO")
        self._content_title.setFont(_font(8, QFont.Weight.Bold))
        self._content_title.setStyleSheet(f"color:{Palette.VIOLET_SOFT};letter-spacing:1px;")
        self._content_text = QTextEdit()
        self._content_text.setReadOnly(True)
        self._content_text.setMaximumHeight(120)
        self._content_text.setFont(_font(9))
        self._content_text.setStyleSheet(
            f"QTextEdit{{background:transparent;color:{Palette.TEXT_MUTED};border:0;}}"
        )
        content_layout.addWidget(self._content_title)
        content_layout.addWidget(self._content_text)
        self._content_card.hide()
        center.addWidget(self._content_card)
        return center

    def _build_log_column(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(310)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        log_card = QFrame()
        log_card.setObjectName("logCard")
        log_card.setStyleSheet(
            f"QFrame#logCard{{background:{Palette.SURFACE};border:1px solid {Palette.BORDER};"
            "border-radius:12px;}}"
        )
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(14, 12, 14, 12)
        log_layout.setSpacing(8)

        header = QLabel("☷  REGISTO")
        header.setFont(_font(8, QFont.Weight.Medium))
        header.setStyleSheet(f"color:{Palette.TEXT_MUTED};letter-spacing:1px;")
        log_layout.addWidget(header)

        self._log = LogView(self._assistant_name)
        log_layout.addWidget(self._log, stretch=1)
        layout.addWidget(log_card, stretch=1)

        self._drop_zone = DropZone()
        self._drop_zone.file_dropped.connect(self._on_drop_zone)
        layout.addWidget(self._drop_zone)
        return panel

    def _build_command_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Diz alguma coisa…")
        self._input.setFont(_font(10))
        self._input.setMinimumHeight(48)
        self._input.setStyleSheet(
            f"QLineEdit{{background:{Palette.SURFACE};color:{Palette.TEXT};"
            f"border:1px solid {Palette.BORDER};border-radius:11px;padding:0 16px;}}"
            f"QLineEdit:focus{{border-color:{Palette.VIOLET};}}"
        )
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input, stretch=1)

        self._interrupt_button = _icon_button("↓")
        self._interrupt_button.setFixedWidth(50)
        self._interrupt_button.setAccessibleName("Interromper resposta")
        self._interrupt_button.setAccessibleDescription("Interrompe a resposta em curso · Esc")
        self._interrupt_button.setToolTip("Interromper resposta · Esc")
        self._interrupt_button.clicked.connect(self._do_interrupt)
        row.addWidget(self._interrupt_button)

        self._mic_button = _icon_button("◉", accent=True)
        self._mic_button.setFixedWidth(64)
        self._mic_button.setAccessibleName("Pausar ou retomar microfone")
        self._mic_button.setAccessibleDescription("Alterna o microfone · F4")
        self._mic_button.setToolTip("Pausar/retomar microfone · F4")
        self._mic_button.clicked.connect(self._toggle_mute)
        row.addWidget(self._mic_button)

        # Keyboard order follows the visual row: command → interrupt → mic.
        QWidget.setTabOrder(self._input, self._interrupt_button)
        QWidget.setTabOrder(self._interrupt_button, self._mic_button)
        return row

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.orb.start_animation()
        handle = self.windowHandle()
        if handle is not None and not getattr(self, "_screen_hooked", False):
            handle.screenChanged.connect(self._on_screen_changed)
            self._screen_hooked = True

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        # A hidden window never paints; the 30 FPS orb timer must not keep
        # burning CPU for nothing.
        self.orb.stop_animation()

    def _on_screen_changed(self, screen) -> None:
        """Keep the window in view when it lands on another monitor.

        Moving between screens with different DPI/geometry can leave the
        window fully or partially off-screen; clamp it back immediately.
        """
        if screen is None:
            return
        geo = screen.availableGeometry()
        frame = self.frameGeometry()
        if geo.contains(frame):
            return
        x = max(geo.left(), min(frame.left(), geo.right() - frame.width()))
        y = max(geo.top(), min(frame.top(), geo.bottom() - frame.height()))
        self.move(x, y)

    def _tick_clock(self) -> None:
        self._clock_label.setText(time.strftime("%H:%M:%S"))
        weekdays = [
            "segunda-feira",
            "terça-feira",
            "quarta-feira",
            "quinta-feira",
            "sexta-feira",
            "sábado",
            "domingo",
        ]
        weekday = weekdays[time.localtime().tm_wday]
        self._date_label.setText(f"{weekday}, {time.strftime('%d/%m')}")

    def _update_metrics(self) -> None:
        try:
            import psutil

            cpu = int(round(psutil.cpu_percent(interval=None)))
            mem = int(round(psutil.virtual_memory().percent))
            net = psutil.net_io_counters()
            now = time.monotonic()
            total = int(net.bytes_sent + net.bytes_recv)

            if self._last_net_bytes and now > self._last_net_time:
                rate = (total - self._last_net_bytes) / (now - self._last_net_time)
            else:
                rate = 0.0

            self._last_net_bytes = total
            self._last_net_time = now

            self._cpu_card.set_value(f"{cpu}%", cpu)
            self._mem_card.set_value(f"{mem}%", mem)
            if rate >= 1024 * 1024:
                net_text = f"{rate / (1024 * 1024):.1f}MB/s"
            elif rate >= 1024:
                net_text = f"{rate / 1024:.1f}KB/s"
            else:
                net_text = f"{rate:.0f}B/s"
            self._net_card.set_value(net_text)
        except Exception:
            self._cpu_card.set_value("--", 0)
            self._mem_card.set_value("--", 0)
            self._net_card.set_value("--")

    def _apply_state(self, state: str) -> None:
        """Legacy string entry point — normalized into the central state model."""
        self._apply_runtime_state(UiRuntimeState(state=normalize_state(state)))

    def _apply_runtime_state(self, snapshot: UiRuntimeState) -> None:
        state = snapshot.state
        self.orb.state = state
        self.orb.speaking = state == UiState.SPEAKING

        if state == UiState.MUTED:
            self._mic_button.setText("×")
            self._mic_button.setStyleSheet(
                f"QPushButton{{background:#24111a;color:{Palette.RED};border:1px solid #4d2635;"
                "border-radius:11px;font-weight:700;}}"
            )
        elif not self._muted:
            self._mic_button.setText("◉")
            self._mic_button.setStyleSheet(
                f"QPushButton{{background:{Palette.VIOLET};color:#09060f;border:0;border-radius:11px;"
                "font-weight:700;}"
                f"QPushButton:hover{{background:{Palette.VIOLET_SOFT};}}"
            )

        # CORE STATUS card mirrors the active task step when one is running.
        if snapshot.current_step or snapshot.task_name:
            detail = " · ".join(
                part for part in (snapshot.task_name, snapshot.current_step) if part
            )
            self._core_card.set_value(f"⟐ {detail[:42]}")
        else:
            self._core_card.set_value("⟐ Sincronizado")

    def _show_content(self, title: str, text: str) -> None:
        self._content_title.setText(title.upper()[:60])
        self._content_text.setPlainText(text[:8000])
        self._content_card.show()

    def _send(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._log.append_event(f"You: {text}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(text,), daemon=True).start()

    def _toggle_mute(self) -> None:
        self._muted = not self._muted
        self.orb.muted = self._muted
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_event("SYS: microfone em pausa")
        else:
            self._apply_state("LISTENING")
            self._log.append_event("SYS: microfone activo")

    def _do_interrupt(self) -> None:
        if self.on_interrupt:
            self.on_interrupt()

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _on_drop_zone(self, path: str) -> None:
        if path:
            self._attach_file(path)
            return
        selected, _selected_filter = QFileDialog.getOpenFileName(self, "Anexar ficheiro")
        if selected:
            self._attach_file(selected)

    def _attach_file(self, path: str) -> None:
        file_path = Path(path)
        if not file_path.exists() or not file_path.is_file():
            return
        self._current_file = str(file_path)
        self._drop_zone.label.setText(file_path.name)
        self._log.append_event(f"SYS: ficheiro anexado · {file_path.name}")
        if self.on_text_command:
            command = (
                f"[FILE_UPLOADED] path={file_path} | name={file_path.name} | "
                "Acknowledge the file briefly and ask what the user wants to do with it."
            )
            threading.Thread(target=self.on_text_command, args=(command,), daemon=True).start()

    def _configure_api_key(self) -> None:
        key, accepted = QInputDialog.getText(
            self,
            "Antonella · Gemini",
            "Gemini API key",
            QLineEdit.EchoMode.Password,
        )
        if not accepted or not key.strip():
            return

        data = read_legacy_config(CONFIG_FILE)
        data["gemini_api_key"] = key.strip()
        data.setdefault("assistant_name", "Antonella")
        data.setdefault("voice_name", "Kore")
        data.setdefault(
            "voice_style",
            "feminine, warm, natural, calm, confident, concise and conversational",
        )
        write_legacy_config(data, CONFIG_FILE)
        self._ready = True
        self._log.append_event("SYS: chave Gemini actualizada")

    def _set_camera_mode(self, enabled: bool) -> None:
        self._visual_stack.setCurrentIndex(1 if enabled else 0)
        if not enabled:
            self._camera_label.clear()

    def _show_camera_frame(self, data: bytes) -> None:
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if pixmap.isNull():
            return

        width = max(320, self._camera_label.width() - 20)
        height = max(240, self._camera_label.height() - 20)
        self._camera_label.setPixmap(
            pixmap.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def start_camera_stream(self) -> None:
        self._cam_stop.clear()
        self._camera_stream_signal.emit(True)
        threading.Thread(target=self._camera_loop, daemon=True, name="antonella-camera").start()

    def _camera_loop(self) -> None:
        try:
            import cv2

            config = get_config()
            camera_index = int(config.get("camera_index", 0) or 0)
            backend = (
                cv2.CAP_DSHOW
                if _OS == "Windows" and hasattr(cv2, "CAP_DSHOW")
                else cv2.CAP_ANY
            )
            capture = cv2.VideoCapture(camera_index, backend)
            if not capture.isOpened():
                capture = cv2.VideoCapture(0)
            if not capture.isOpened():
                self._log_signal.emit("ERR: não foi possível abrir a câmara")
                return

            while not self._cam_stop.wait(0.04) and capture.isOpened():
                ok, frame = capture.read()
                if not ok or frame is None:
                    continue
                encoded, buffer = cv2.imencode(
                    ".jpg",
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 72],
                )
                if encoded:
                    self._camera_frame_signal.emit(buffer.tobytes())
            capture.release()
        except Exception as exc:
            self._log_signal.emit(f"ERR: câmara indisponível · {type(exc).__name__}")
        finally:
            self._camera_stream_signal.emit(False)

    def stop_camera_stream(self) -> None:
        self._cam_stop.set()
        self._camera_stream_signal.emit(False)


class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app

    def mainloop(self) -> None:
        self._app.exec()

    def protocol(self, *_args) -> None:
        return None


class JarvisUI:
    """Compatibility adapter exposing the legacy engine contract through Antonella UI."""

    def __init__(self, face_path: str = "", size=None):
        del size
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = AntonellaWindow(face_path)
        self._win.show()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, value: bool) -> None:
        if bool(value) != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._current_file

    @property
    def assistant_name(self) -> str:
        return self._win._assistant_name

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, callback) -> None:
        self._win.on_text_command = callback

    @property
    def on_remote_clicked(self):
        return self._win.on_remote_clicked

    @on_remote_clicked.setter
    def on_remote_clicked(self, callback) -> None:
        self._win.on_remote_clicked = callback

    @property
    def on_interrupt(self):
        return self._win.on_interrupt

    @on_interrupt.setter
    def on_interrupt(self, callback) -> None:
        self._win.on_interrupt = callback

    @property
    def get_plugins(self):
        return self._win.get_plugins

    @get_plugins.setter
    def get_plugins(self, callback) -> None:
        self._win.get_plugins = callback

    def set_state(self, state: str) -> None:
        self._win._state_signal.emit(state)

    def set_runtime_state(self, state: UiRuntimeState | UiState | str) -> None:
        """Push a structured runtime snapshot to the UI (ANT-268 contract)."""
        if not isinstance(state, UiRuntimeState):
            state = UiRuntimeState(state=normalize_state(state))
        self._win._runtime_state_signal.emit(state)

    def write_log(self, text: str) -> None:
        self._win._log_signal.emit(text)

    def wait_for_api_key(self) -> None:
        while not self._win._ready:
            time.sleep(0.1)

    def show_content(self, title: str, text: str) -> None:
        self._win._content_signal.emit(title[:60], text[:8000])

    def prompt_reconfig(self) -> None:
        self._win._ready = False
        self._win._reconfig_signal.emit()

    def notify_phone_connected(self) -> None:
        self.write_log("SYS: telefone ligado ao painel remoto")

    def show_camera_frame(self, img_bytes: bytes) -> None:
        self._win._camera_frame_signal.emit(img_bytes)

    def start_camera_stream(self) -> None:
        self._win.start_camera_stream()

    def stop_camera_stream(self) -> None:
        self._win.stop_camera_stream()

    def start_speaking(self) -> None:
        self.set_state("SPEAKING")

    def stop_speaking(self) -> None:
        if not self.muted:
            self.set_state("LISTENING")

    def speak(self, text: str) -> None:
        callback = getattr(self, "request_say", None)
        if callback:
            callback(text)

    def log(self, text: str) -> None:
        self.write_log(text)

    def show_response(self, text: str) -> None:
        self.write_log(f"Antonella: {text}")
