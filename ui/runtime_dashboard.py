from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from core.runtime_snapshot import build_runtime_snapshot


_BG = "#080910"
_SURFACE_2 = "#0b0c15"
_BORDER = "#24263a"
_TEXT = "#f5f2ff"
_MUTED = "#8f93b8"
_FAINT = "#626782"
_VIOLET = "#9b57ff"
_PINK = "#ff5ca8"
_BLUE = "#55b8ff"
_GREEN = "#68e6b2"
_RED = "#ff6688"


# -.-.-.-
def _font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    return QFont("Segoe UI Variable", size, weight)


class RuntimeChip(QFrame):
    def __init__(self, title: str, value: str, *, accent: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._accent = accent
        self.setObjectName("runtimeChip")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(50)
        self.setStyleSheet(
            f"QFrame#runtimeChip{{background:{_SURFACE_2};border:1px solid {_BORDER};border-radius:11px;}}"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setFont(_font(8, QFont.Weight.Bold))
        self._dot.setStyleSheet(f"color:{accent};")
        row.addWidget(self._dot)

        stack = QVBoxLayout()
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(0)

        self._title = QLabel(title.upper())
        self._title.setFont(_font(7, QFont.Weight.DemiBold))
        self._title.setStyleSheet(f"color:{_FAINT};letter-spacing:1px;")
        stack.addWidget(self._title)

        self._value = QLabel(value)
        self._value.setFont(_font(9, QFont.Weight.DemiBold))
        self._value.setStyleSheet(f"color:{_TEXT};")
        self._value.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        stack.addWidget(self._value)
        row.addLayout(stack, stretch=1)

    def set_value(self, value: str, *, accent: str | None = None, tooltip: str = "") -> None:
        self._value.setText(value)
        if accent:
            self._dot.setStyleSheet(f"color:{accent};")
        self.setToolTip(tooltip)


class RuntimeDashboard(QWidget):
    """Compact status surface for Antonella's active brains and desktop agent."""

    def __init__(self, host_window: Any):
        super().__init__(host_window)
        self._host = host_window
        self.setObjectName("runtimeDashboard")
        self.setStyleSheet(f"QWidget#runtimeDashboard{{background:{_BG};}}")

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._live = RuntimeChip("Live", "Gemini Live", accent=_VIOLET)
        self._expert = RuntimeChip("Especialista", "Opcional", accent=_FAINT)
        self._cost = RuntimeChip("Custo", "Económico", accent=_GREEN)
        self._display = RuntimeChip("Visão", "Auto", accent=_BLUE)
        self._agent = RuntimeChip("Agente", "Em espera", accent=_FAINT)

        for chip in (self._live, self._expert, self._cost, self._display, self._agent):
            row.addWidget(chip)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(1600)
        self.refresh()

        self._focus_shortcut = QShortcut(QKeySequence("Ctrl+K"), host_window)
        self._focus_shortcut.activated.connect(self._focus_command)

    def _focus_command(self) -> None:
        command = getattr(self._host, "_input", None)
        if command is not None:
            command.setFocus()
            command.selectAll()

    def refresh(self) -> None:
        try:
            snapshot = build_runtime_snapshot()
        except Exception:
            return

        ready = bool(getattr(self._host, "_ready", False))
        state = str(getattr(getattr(self._host, "orb", None), "state", "") or "").upper()
        live_accent = _VIOLET if ready else _RED
        live_value = "Gemini Live" if ready else "Offline"
        if state == "SPEAKING":
            live_value = "A responder"
            live_accent = _PINK
        elif state == "LISTENING" and ready:
            live_value = "A escutar"
        elif state in {"THINKING", "PROCESSING"} and ready:
            live_value = "A processar"
        self._live.set_value(
            live_value,
            accent=live_accent,
            tooltip="Sessão de voz e tool calling em tempo real.",
        )

        expert_ready = bool(snapshot.get("expert_ready"))
        self._expert.set_value(
            str(snapshot.get("expert") or "Opcional"),
            accent=_GREEN if expert_ready else _FAINT,
            tooltip=(
                "OpenAI especialista disponível sob demanda."
                if expert_ready
                else "Configura ANTONELLA_OPENAI_API_KEY para activar o especialista opcional."
            ),
        )

        cost_mode = str(snapshot.get("cost_mode") or "economy")
        cost_accent = _GREEN if cost_mode == "economy" else (_BLUE if cost_mode == "balanced" else _PINK)
        self._cost.set_value(
            str(snapshot.get("cost") or "Económico"),
            accent=cost_accent,
            tooltip="Computer Use só escala custo quando a tarefa realmente exige visão.",
        )

        display_count = int(snapshot.get("display_count") or 0)
        display_value = str(snapshot.get("display") or "Auto")
        self._display.set_value(
            display_value,
            accent=_BLUE,
            tooltip=f"{display_count} ecrã(s) detectado(s). O modo auto segue a janela activa.",
        )

        agent_state = str(snapshot.get("agent_state") or "idle")
        if agent_state == "failed":
            agent_accent = _RED
        elif agent_state == "awaiting_approval":
            agent_accent = _PINK
        elif agent_state in {"observing", "planning", "executing", "starting"}:
            agent_accent = _VIOLET
        elif agent_state == "done":
            agent_accent = _GREEN
        else:
            agent_accent = _FAINT

        self._agent.set_value(
            str(snapshot.get("agent") or "Em espera"),
            accent=agent_accent,
            tooltip=str(snapshot.get("agent_detail") or "Computer Use disponível"),
        )


# -.-.-.-
def attach_runtime_dashboard(ui) -> RuntimeDashboard | None:
    """Attach the runtime HUD to the compatibility UI without modifying legacy layout code."""
    window = getattr(ui, "_win", None)
    if window is None:
        return None

    root = window.centralWidget().layout() if window.centralWidget() else None
    if root is None or not hasattr(root, "insertWidget"):
        return None

    existing = getattr(window, "_runtime_dashboard", None)
    if existing is not None:
        return existing

    dashboard = RuntimeDashboard(window)
    root.insertWidget(1, dashboard)
    window._runtime_dashboard = dashboard

    command = getattr(window, "_input", None)
    if command is not None:
        command.setToolTip("Escreve um comando · Enter envia · Ctrl+K foca esta caixa")

    return dashboard
