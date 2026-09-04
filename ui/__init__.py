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
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QKeySequence, QLinearGradient, QPainter, QPen, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


ANTONELLA_UI_IMPLEMENTATION = "v1"
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config" / "api_keys.json"
_OS = platform.system()


class Palette:
    BACKGROUND = "#09090f"
    SURFACE = "#11111a"
    SURFACE_2 = "#171725"
    SURFACE_3 = "#1d1d2e"
    BORDER = "#2a2a3d"
    BORDER_SOFT = "#202032"
    TEXT = "#f5f2ff"
    TEXT_MUTED = "#9b97ae"
    TEXT_FAINT = "#6c687d"
    VIOLET = "#9b7bff"
    VIOLET_2 = "#7458e8"
    ROSE = "#ff79ad"
    BLUE = "#67b7ff"
    GREEN = "#65e6b4"
    AMBER = "#f4c96b"
    RED = "#ff7385"


# -.-.-.-
def _font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    preferred = "Segoe UI Variable" if _OS == "Windows" else "Inter"
    return QFont(preferred, size, weight)


# -.-.-.-
def _button(text: str, *, primary: bool = False, danger: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFont(_font(9, QFont.Weight.DemiBold))
    button.setMinimumHeight(38)
    if danger:
        button.setStyleSheet(
            f"QPushButton {{background:#21131b;color:{Palette.RED};border:1px solid #4b2633;"
            "border-radius:10px;padding:0 14px;}"
            f"QPushButton:hover {{background:#2b1721;border-color:{Palette.RED};}}"
        )
    elif primary:
        button.setStyleSheet(
            f"QPushButton {{background:{Palette.VIOLET};color:#0b0811;border:0;border-radius:10px;"
            "padding:0 16px;font-weight:700;}"
            f"QPushButton:hover {{background:#ad93ff;}}"
        )
    else:
        button.setStyleSheet(
            f"QPushButton {{background:{Palette.SURFACE_2};color:{Palette.TEXT};border:1px solid {Palette.BORDER};"
            "border-radius:10px;padding:0 14px;}"
            f"QPushButton:hover {{background:{Palette.SURFACE_3};border-color:#45415e;}}"
        )
    return button


class AuroraOrb(QWidget):
    """Organic voice-state visualization with no inherited JARVIS/HUD geometry."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.state = "INITIALISING"
        self.muted = False
        self.speaking = False
        self._phase = 0.0
        self._energy = 0.22
        self._target_energy = 0.22
        self.setMinimumSize(360, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    # -.-.-.-
    def _tick(self) -> None:
        self._phase += 0.022 if self.speaking else 0.009
        if self.muted:
            self._target_energy = 0.06
        elif self.speaking:
            self._target_energy = random.uniform(0.68, 1.0)
        elif self.state == "THINKING":
            self._target_energy = 0.5
        elif self.state == "LISTENING":
            self._target_energy = 0.34
        else:
            self._target_energy = 0.2
        self._energy += (self._target_energy - self._energy) * 0.08
        self.update()

    # -.-.-.-
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(Palette.BACKGROUND))

        width = self.width()
        height = self.height()
        center = QPointF(width / 2, height / 2 - 12)
        base = min(width, height) * (0.20 + self._energy * 0.035)

        glow_colors = [Palette.VIOLET, Palette.ROSE, Palette.BLUE]
        for index, color in enumerate(glow_colors):
            offset = math.sin(self._phase * (1.0 + index * 0.15) + index * 2.1)
            radius = base * (1.72 - index * 0.14) + offset * 10
            alpha = max(8, int(42 * self._energy) - index * 7)
            brush = QColor(color)
            brush.setAlpha(alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(brush))
            painter.drawEllipse(center, radius, radius)

        for index in range(7):
            angle = self._phase * (0.8 + index * 0.07) + index * 0.92
            wave = math.sin(angle * 1.7) * (10 + self._energy * 17)
            rx = base * (0.72 + index * 0.045) + wave
            ry = base * (0.55 + index * 0.04) - wave * 0.22
            color = QColor(Palette.VIOLET if index % 2 == 0 else Palette.ROSE)
            color.setAlpha(55 + int(self._energy * 80) - index * 5)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(color, 2 if index < 3 else 1))
            painter.save()
            painter.translate(center)
            painter.rotate(math.degrees(angle) * 0.32)
            painter.drawEllipse(QRectF(-rx, -ry, rx * 2, ry * 2))
            painter.restore()

        core_gradient = QLinearGradient(
            center.x() - base,
            center.y() - base,
            center.x() + base,
            center.y() + base,
        )
        core_gradient.setColorAt(0.0, QColor("#c5b5ff"))
        core_gradient.setColorAt(0.46, QColor(Palette.VIOLET))
        core_gradient.setColorAt(1.0, QColor(Palette.ROSE))
        painter.setBrush(QBrush(core_gradient))
        painter.setPen(QPen(QColor("#e2d9ff"), 1))
        painter.drawEllipse(center, base * 0.63, base * 0.63)

        state, color = self._state_label()
        painter.setFont(_font(11, QFont.Weight.DemiBold))
        painter.setPen(QColor(color))
        painter.drawText(
            QRectF(0, center.y() + base * 1.45, width, 30),
            Qt.AlignmentFlag.AlignCenter,
            state,
        )

    # -.-.-.-
    def _state_label(self) -> tuple[str, str]:
        if self.muted:
            return "Microfone em pausa", Palette.RED
        labels = {
            "INITIALISING": ("A iniciar", Palette.TEXT_MUTED),
            "THINKING": ("A pensar", Palette.AMBER),
            "PROCESSING": ("A executar", Palette.AMBER),
            "LISTENING": ("A ouvir", Palette.GREEN),
            "SPEAKING": ("A falar", Palette.ROSE),
            "SLEEPING": ("Em espera", Palette.TEXT_FAINT),
            "MUTED": ("Microfone em pausa", Palette.RED),
        }
        return labels.get(self.state, (self.state.title(), Palette.VIOLET))


class ConversationView(QTextEdit):
    def __init__(self, assistant_name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.assistant_name = assistant_name
        self.setReadOnly(True)
        self.setFont(_font(10))
        self.setStyleSheet(
            f"QTextEdit {{background:{Palette.SURFACE};color:{Palette.TEXT};border:1px solid {Palette.BORDER_SOFT};"
            "border-radius:14px;padding:16px;}"
            f"QScrollBar:vertical {{background:transparent;width:7px;}}"
            f"QScrollBar::handle:vertical {{background:{Palette.BORDER};border-radius:3px;min-height:24px;}}"
        )
        self.document().setDefaultStyleSheet(
            f"body{{font-family:'Segoe UI Variable','Segoe UI',sans-serif;color:{Palette.TEXT};}}"
            f".meta{{color:{Palette.TEXT_FAINT};font-size:9pt;}}"
            f".user{{color:{Palette.TEXT};font-weight:600;}}"
            f".ai{{color:#e5dcff;font-weight:600;}}"
            f".sys{{color:{Palette.TEXT_MUTED};}}"
            f".err{{color:{Palette.RED};}}"
        )

    # -.-.-.-
    def append_event(self, text: str) -> None:
        clean = text.replace("J.A.R.V.I.S.", self.assistant_name).replace("JARVIS", self.assistant_name)
        escaped = html.escape(clean)
        lower = clean.lower()
        if lower.startswith("you:"):
            body = escaped.split(":", 1)[1].strip() if ":" in escaped else escaped
            markup = f'<p><span class="meta">TU</span><br><span class="user">{body}</span></p>'
        elif lower.startswith(self.assistant_name.lower() + ":"):
            body = escaped.split(":", 1)[1].strip() if ":" in escaped else escaped
            markup = f'<p><span class="meta">ANTONELLA</span><br><span class="ai">{body}</span></p>'
        elif lower.startswith("err:"):
            markup = f'<p class="err">{escaped}</p>'
        else:
            markup = f'<p class="sys">{escaped}</p>'
        self.append(markup)
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())


class StatusCard(QFrame):
    def __init__(self, title: str, value: str, detail: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("statusCard")
        self.setStyleSheet(
            f"QFrame#statusCard{{background:{Palette.SURFACE_2};border:1px solid {Palette.BORDER_SOFT};border-radius:12px;}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(13, 11, 13, 11)
        layout.setSpacing(3)
        title_label = QLabel(title.upper())
        title_label.setFont(_font(7, QFont.Weight.DemiBold))
        title_label.setStyleSheet(f"color:{Palette.TEXT_FAINT};letter-spacing:1px;")
        self.value_label = QLabel(value)
        self.value_label.setFont(_font(10, QFont.Weight.DemiBold))
        self.value_label.setStyleSheet(f"color:{Palette.TEXT};")
        self.detail_label = QLabel(detail)
        self.detail_label.setWordWrap(True)
        self.detail_label.setFont(_font(8))
        self.detail_label.setStyleSheet(f"color:{Palette.TEXT_MUTED};")
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)
        if detail:
            layout.addWidget(self.detail_label)


class AntonellaWindow(QMainWindow):
    _log_signal = pyqtSignal(str)
    _state_signal = pyqtSignal(str)
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

        self.setWindowTitle("Antonella — Personal AI")
        self.setMinimumSize(1050, 690)
        self.resize(1280, 820)
        self.setStyleSheet(f"QMainWindow{{background:{Palette.BACKGROUND};}} QLabel{{background:transparent;}}")

        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            self.move(
                geometry.x() + max(0, (geometry.width() - self.width()) // 2),
                geometry.y() + max(0, (geometry.height() - self.height()) // 2),
            )

        central = QWidget()
        central.setStyleSheet(f"background:{Palette.BACKGROUND};")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(14)
        root.addWidget(self._build_topbar())

        body = QHBoxLayout()
        body.setSpacing(14)

        center = QVBoxLayout()
        center.setSpacing(12)
        self._visual_stack = QStackedWidget()
        self._visual_stack.setStyleSheet(
            f"QStackedWidget{{background:{Palette.SURFACE};border:1px solid {Palette.BORDER_SOFT};border-radius:16px;}}"
        )
        self.orb = AuroraOrb()
        self._visual_stack.addWidget(self.orb)
        self._camera_label = QLabel("A preparar câmara…")
        self._camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._camera_label.setStyleSheet(f"color:{Palette.TEXT_MUTED};background:#050509;border-radius:16px;")
        self._visual_stack.addWidget(self._camera_label)
        center.addWidget(self._visual_stack, stretch=5)

        self._content_card = self._build_content_card()
        self._content_card.hide()
        center.addWidget(self._content_card, stretch=2)

        self._conversation = ConversationView(self._assistant_name)
        center.addWidget(self._conversation, stretch=4)
        center.addLayout(self._build_command_row())
        body.addLayout(center, stretch=8)

        body.addWidget(self._build_side_panel(), stretch=3)
        root.addLayout(body, stretch=1)

        self._log_signal.connect(self._conversation.append_event)
        self._state_signal.connect(self._apply_state)
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

        if self._ready:
            self._conversation.append_event("SYS: Antonella pronta para ligar ao motor de voz.")
        else:
            self._conversation.append_event("SYS: Configura a chave Gemini para iniciar.")
            QTimer.singleShot(250, self._configure_api_key)

    # -.-.-.-
    def _build_topbar(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet(
            f"QFrame{{background:{Palette.SURFACE};border:1px solid {Palette.BORDER_SOFT};border-radius:14px;}}"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        mark = QLabel("A")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(38, 38)
        mark.setFont(_font(17, QFont.Weight.Bold))
        mark.setStyleSheet(
            f"color:#0a0710;background:{Palette.VIOLET};border-radius:11px;font-weight:800;"
        )
        layout.addWidget(mark)

        name_wrap = QVBoxLayout()
        name_wrap.setSpacing(0)
        name = QLabel("ANTONELLA")
        name.setFont(_font(12, QFont.Weight.Bold))
        name.setStyleSheet(f"color:{Palette.TEXT};letter-spacing:1px;")
        subtitle = QLabel("personal intelligence layer")
        subtitle.setFont(_font(8))
        subtitle.setStyleSheet(f"color:{Palette.TEXT_FAINT};")
        name_wrap.addWidget(name)
        name_wrap.addWidget(subtitle)
        layout.addLayout(name_wrap)
        layout.addStretch()

        self._state_pill = QLabel("A INICIAR")
        self._state_pill.setFont(_font(8, QFont.Weight.DemiBold))
        self._state_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_pill.setMinimumWidth(105)
        self._state_pill.setFixedHeight(30)
        layout.addWidget(self._state_pill)

        self._clock_label = QLabel("")
        self._clock_label.setFont(_font(9, QFont.Weight.DemiBold))
        self._clock_label.setStyleSheet(f"color:{Palette.TEXT_MUTED};padding-left:8px;")
        layout.addWidget(self._clock_label)
        return bar

    # -.-.-.-
    def _build_side_panel(self) -> QWidget:
        side = QFrame()
        side.setMinimumWidth(280)
        side.setMaximumWidth(340)
        side.setStyleSheet(
            f"QFrame{{background:{Palette.SURFACE};border:1px solid {Palette.BORDER_SOFT};border-radius:16px;}}"
        )
        layout = QVBoxLayout(side)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        title = QLabel("SESSÃO")
        title.setFont(_font(8, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{Palette.TEXT_FAINT};letter-spacing:1px;")
        layout.addWidget(title)

        self._voice_card = StatusCard("Voz", self._voice_name, "Perfil feminino · Gemini Live")
        self._mic_card = StatusCard("Microfone", "Activo", "F4 para pausar")
        self._provider_card = StatusCard("Motor", "Gemini Live", "Áudio nativo em streaming")
        self._file_card = StatusCard("Ficheiro", "Nenhum", "Anexa contexto quando precisares")
        layout.addWidget(self._voice_card)
        layout.addWidget(self._mic_card)
        layout.addWidget(self._provider_card)
        layout.addWidget(self._file_card)

        file_button = _button("Anexar ficheiro")
        file_button.clicked.connect(self._select_file)
        layout.addWidget(file_button)

        camera_button = _button("Fechar câmara")
        camera_button.clicked.connect(self.stop_camera_stream)
        layout.addWidget(camera_button)

        layout.addStretch()

        self._mute_button = _button("Pausar microfone")
        self._mute_button.clicked.connect(self._toggle_mute)
        layout.addWidget(self._mute_button)

        interrupt = _button("Interromper resposta  ·  Esc", danger=True)
        interrupt.clicked.connect(self._do_interrupt)
        layout.addWidget(interrupt)

        settings = _button("Configurar chave Gemini")
        settings.clicked.connect(self._configure_api_key)
        layout.addWidget(settings)
        return side

    # -.-.-.-
    def _build_command_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(9)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Escreve ou fala com a Antonella…")
        self._input.setFont(_font(10))
        self._input.setMinimumHeight(44)
        self._input.setStyleSheet(
            f"QLineEdit{{background:{Palette.SURFACE_2};color:{Palette.TEXT};border:1px solid {Palette.BORDER};"
            "border-radius:12px;padding:0 14px;}"
            f"QLineEdit:focus{{border-color:{Palette.VIOLET};background:{Palette.SURFACE_3};}}"
        )
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input, stretch=1)
        send = _button("Enviar", primary=True)
        send.setMinimumWidth(96)
        send.clicked.connect(self._send)
        row.addWidget(send)
        return row

    # -.-.-.-
    def _build_content_card(self) -> QWidget:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame{{background:{Palette.SURFACE_2};border:1px solid {Palette.BORDER};border-radius:14px;}}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        header = QHBoxLayout()
        self._content_title = QLabel("CONTEXTO")
        self._content_title.setFont(_font(8, QFont.Weight.Bold))
        self._content_title.setStyleSheet(f"color:{Palette.VIOLET};letter-spacing:1px;")
        header.addWidget(self._content_title)
        header.addStretch()
        close = _button("Fechar")
        close.setMaximumWidth(76)
        close.setMaximumHeight(30)
        close.clicked.connect(card.hide)
        header.addWidget(close)
        layout.addLayout(header)
        self._content_text = QTextEdit()
        self._content_text.setReadOnly(True)
        self._content_text.setFont(_font(9))
        self._content_text.setStyleSheet(
            f"QTextEdit{{background:{Palette.BACKGROUND};color:{Palette.TEXT};border:0;border-radius:10px;padding:10px;}}"
        )
        layout.addWidget(self._content_text)
        return card

    # -.-.-.-
    def _tick_clock(self) -> None:
        self._clock_label.setText(time.strftime("%H:%M  ·  %d %b"))

    # -.-.-.-
    def _apply_state(self, state: str) -> None:
        state = state.upper()
        self.orb.state = state
        self.orb.speaking = state == "SPEAKING"
        labels = {
            "INITIALISING": ("A INICIAR", Palette.TEXT_MUTED),
            "THINKING": ("A PENSAR", Palette.AMBER),
            "PROCESSING": ("A EXECUTAR", Palette.AMBER),
            "LISTENING": ("A OUVIR", Palette.GREEN),
            "SPEAKING": ("A FALAR", Palette.ROSE),
            "SLEEPING": ("EM ESPERA", Palette.TEXT_FAINT),
            "MUTED": ("EM PAUSA", Palette.RED),
        }
        text, color = labels.get(state, (state, Palette.VIOLET))
        self._state_pill.setText(text)
        self._state_pill.setStyleSheet(
            f"color:{color};background:{Palette.SURFACE_2};border:1px solid {color};border-radius:10px;padding:0 10px;"
        )

    # -.-.-.-
    def _show_content(self, title: str, text: str) -> None:
        self._content_title.setText(title.upper()[:60])
        self._content_text.setPlainText(text[:8000])
        self._content_card.show()

    # -.-.-.-
    def _send(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._conversation.append_event(f"You: {text}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(text,), daemon=True).start()

    # -.-.-.-
    def _toggle_mute(self) -> None:
        self._muted = not self._muted
        self.orb.muted = self._muted
        if self._muted:
            self._mute_button.setText("Retomar microfone")
            self._mic_card.value_label.setText("Em pausa")
            self._mic_card.value_label.setStyleSheet(f"color:{Palette.RED};")
            self._apply_state("MUTED")
        else:
            self._mute_button.setText("Pausar microfone")
            self._mic_card.value_label.setText("Activo")
            self._mic_card.value_label.setStyleSheet(f"color:{Palette.GREEN};")
            self._apply_state("LISTENING")

    # -.-.-.-
    def _do_interrupt(self) -> None:
        if self.on_interrupt:
            self.on_interrupt()

    # -.-.-.-
    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # -.-.-.-
    def _select_file(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(self, "Anexar ficheiro")
        if not path:
            return
        self._current_file = path
        file_path = Path(path)
        self._file_card.value_label.setText(file_path.name)
        self._file_card.detail_label.setText(str(file_path.parent))
        self._conversation.append_event(f"SYS: Ficheiro anexado: {file_path.name}")
        if self.on_text_command:
            command = (
                f"[FILE_UPLOADED] path={path} | name={file_path.name} | "
                "Acknowledge the file briefly and ask what the user wants to do with it."
            )
            threading.Thread(target=self.on_text_command, args=(command,), daemon=True).start()

    # -.-.-.-
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
        write_legacy_config(data, CONFIG_FILE)
        self._ready = True
        self._conversation.append_event("SYS: Chave Gemini actualizada. A ligação será refeita automaticamente.")

    # -.-.-.-
    def _set_camera_mode(self, enabled: bool) -> None:
        self._visual_stack.setCurrentIndex(1 if enabled else 0)
        if not enabled:
            self._camera_label.clear()

    # -.-.-.-
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

    # -.-.-.-
    def start_camera_stream(self) -> None:
        self._cam_stop.clear()
        self._camera_stream_signal.emit(True)
        threading.Thread(target=self._camera_loop, daemon=True, name="antonella-camera").start()

    # -.-.-.-
    def _camera_loop(self) -> None:
        try:
            import cv2

            config = get_config()
            camera_index = int(config.get("camera_index", 0) or 0)
            backend = cv2.CAP_DSHOW if _OS == "Windows" and hasattr(cv2, "CAP_DSHOW") else cv2.CAP_ANY
            capture = cv2.VideoCapture(camera_index, backend)
            if not capture.isOpened():
                capture = cv2.VideoCapture(0)
            if not capture.isOpened():
                self._log_signal.emit("ERR: Não foi possível abrir a câmara.")
                return
            while not self._cam_stop.wait(0.04) and capture.isOpened():
                ok, frame = capture.read()
                if not ok or frame is None:
                    continue
                encoded, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
                if encoded:
                    self._camera_frame_signal.emit(buffer.tobytes())
            capture.release()
        except Exception as exc:
            self._log_signal.emit(f"ERR: Câmara indisponível: {type(exc).__name__}")
        finally:
            self._camera_stream_signal.emit(False)

    # -.-.-.-
    def stop_camera_stream(self) -> None:
        self._cam_stop.set()
        self._camera_stream_signal.emit(False)


class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app

    # -.-.-.-
    def mainloop(self) -> None:
        self._app.exec()

    # -.-.-.-
    def protocol(self, *_args) -> None:
        return None


class JarvisUI:
    """Compatibility adapter exposing the legacy UI contract with Antonella's implementation."""

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
        self.write_log("SYS: Telefone ligado ao painel remoto.")

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

    # Compatibility aliases used by older actions/plugins.
    def log(self, text: str) -> None:
        self.write_log(text)

    def show_response(self, text: str) -> None:
        self.write_log(f"Antonella: {text}")
