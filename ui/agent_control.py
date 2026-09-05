from __future__ import annotations

import html
from typing import Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.computer_use import get_realtime_computer_use_session


_BG = "#05060b"
_SURFACE = "#080910"
_SURFACE_2 = "#0b0c15"
_BORDER = "#24263a"
_BORDER_HOVER = "#35384f"
_TEXT = "#f5f2ff"
_MUTED = "#8f93b8"
_FAINT = "#626782"
_VIOLET = "#9b57ff"
_VIOLET_SOFT = "#bd91ff"
_PINK = "#ff5ca8"
_BLUE = "#55b8ff"
_GREEN = "#68e6b2"
_RED = "#ff6688"

_ACTIVE_STATES = {"starting", "observing", "planning", "executing", "awaiting_approval", "stopping"}
_LABELS = {
    "idle": "Em espera",
    "starting": "A iniciar",
    "observing": "A observar",
    "planning": "A planear",
    "executing": "A executar",
    "awaiting_approval": "A aguardar aprovação",
    "stopping": "A parar",
    "stopped": "Parado",
    "done": "Concluído",
    "failed": "Falhou",
}
_COST_MODE_LABELS = {
    "economy": "Económico",
    "balanced": "Equilibrado",
    "quality": "Qualidade",
}


# -.-.-.-
def _font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    return QFont("Segoe UI Variable", size, weight)


# -.-.-.-
def _format_cost(status: dict[str, Any]) -> tuple[str, str]:
    mode = str(status.get("cost_mode") or "").lower()
    mode_label = _COST_MODE_LABELS.get(mode, "—")
    estimated = status.get("estimated_cost_usd")
    complete = bool(status.get("cost_complete", False))
    known = status.get("known_cost_usd")

    if complete and estimated is not None:
        try:
            value = max(0.0, float(estimated))
        except (TypeError, ValueError):
            return mode_label, mode
        return f"~US$ {value:.6f}", mode

    try:
        known_value = max(0.0, float(known or 0.0))
    except (TypeError, ValueError):
        known_value = 0.0
    if known_value > 0:
        return f"≥ US$ {known_value:.6f} · parcial", mode

    return mode_label, mode


class StatBox(QFrame):
    def __init__(self, title: str, value: str = "—"):
        super().__init__()
        self.setObjectName("agentStat")
        self.setStyleSheet(
            f"QFrame#agentStat{{background:{_SURFACE_2};border:1px solid {_BORDER};border-radius:10px;}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 9, 11, 9)
        layout.setSpacing(2)

        label = QLabel(title.upper())
        label.setFont(_font(7, QFont.Weight.DemiBold))
        label.setStyleSheet(f"color:{_FAINT};letter-spacing:1px;")
        layout.addWidget(label)

        self.value = QLabel(value)
        self.value.setFont(_font(10, QFont.Weight.DemiBold))
        self.value.setStyleSheet(f"color:{_TEXT};")
        self.value.setWordWrap(True)
        layout.addWidget(self.value)

    def set_value(self, value: str, color: str = _TEXT) -> None:
        self.value.setText(value)
        self.value.setStyleSheet(f"color:{color};")


class AgentControlDialog(QDialog):
    """Local control surface for the running Computer Use agent.

    Consumes only the fields published by the session's ``status()`` dict;
    it never infers state from logs and never invents values. Cost is shown
    only from ANT-264 telemetry or as the selected cost mode fallback.
    """

    def __init__(self, host_window: Any):
        super().__init__(host_window)
        self._host = host_window
        self._session = get_realtime_computer_use_session()
        self._last_history = None

        self.setWindowTitle("Antonella · Agente")
        self.setModal(False)
        self.resize(720, 660)
        self.setMinimumSize(620, 560)
        self.setStyleSheet(
            f"QDialog{{background:{_BG};color:{_TEXT};}}"
            f"QLabel{{background:transparent;color:{_TEXT};}}"
            f"QTextEdit{{background:{_SURFACE_2};color:{_MUTED};border:1px solid {_BORDER};"
            "border-radius:10px;padding:10px;}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(2)
        title = QLabel("AGENTE DE COMPUTADOR")
        title.setFont(_font(14, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color:{_VIOLET_SOFT};letter-spacing:1px;")
        subtitle = QLabel("Estado verificável · controlo local · sem chamada de IA para abrir este painel")
        subtitle.setFont(_font(8))
        subtitle.setStyleSheet(f"color:{_MUTED};")
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addLayout(title_wrap)
        header.addStretch()

        self._state_badge = QLabel("EM ESPERA")
        self._state_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_badge.setFont(_font(8, QFont.Weight.Bold))
        self._state_badge.setMinimumWidth(130)
        self._state_badge.setFixedHeight(32)
        header.addWidget(self._state_badge)
        root.addLayout(header)

        objective_card = QFrame()
        objective_card.setObjectName("objectiveCard")
        objective_card.setStyleSheet(
            f"QFrame#objectiveCard{{background:{_SURFACE};border:1px solid {_BORDER};border-radius:11px;}}"
        )
        objective_layout = QVBoxLayout(objective_card)
        objective_layout.setContentsMargins(14, 11, 14, 11)
        objective_layout.setSpacing(4)
        objective_title = QLabel("OBJECTIVO ACTUAL")
        objective_title.setFont(_font(7, QFont.Weight.DemiBold))
        objective_title.setStyleSheet(f"color:{_FAINT};letter-spacing:1px;")
        self._objective = QLabel("Nenhuma tarefa activa")
        self._objective.setFont(_font(10, QFont.Weight.Medium))
        self._objective.setStyleSheet(f"color:{_TEXT};")
        self._objective.setWordWrap(True)
        objective_layout.addWidget(objective_title)
        objective_layout.addWidget(self._objective)
        root.addWidget(objective_card)

        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:#1b1d2b;border:0;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{_VIOLET};border-radius:2px;}}"
        )
        root.addWidget(self._progress)

        stats = QGridLayout()
        stats.setSpacing(8)
        self._step = StatBox("Passo")
        self._model_calls = StatBox("Chamadas IA")
        self._saved_calls = StatBox("Poupadas")
        self._target_window = StatBox("Janela alvo")
        self._display = StatBox("Ecrã")
        self._cost = StatBox("Custo")
        self._provider = StatBox("Provider")
        self._model = StatBox("Modelo")
        stats.addWidget(self._step, 0, 0)
        stats.addWidget(self._model_calls, 0, 1)
        stats.addWidget(self._saved_calls, 0, 2)
        stats.addWidget(self._target_window, 1, 0)
        stats.addWidget(self._display, 1, 1)
        stats.addWidget(self._cost, 1, 2)
        stats.addWidget(self._provider, 2, 0)
        stats.addWidget(self._model, 2, 1)
        root.addLayout(stats)

        self._details_toggle = QPushButton("▸ Detalhes técnicos")
        self._details_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._details_toggle.setFont(_font(8, QFont.Weight.DemiBold))
        self._details_toggle.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_FAINT};border:0;text-align:left;padding:2px 0;}}"
            f"QPushButton:hover{{color:{_MUTED};}}"
        )
        self._details_toggle.clicked.connect(self._toggle_details)
        root.addWidget(self._details_toggle)

        self._details_row = QWidget()
        details_grid = QGridLayout(self._details_row)
        details_grid.setContentsMargins(0, 0, 0, 0)
        details_grid.setSpacing(8)
        self._capture_scope = StatBox("Âmbito de captura")
        self._capture_savings = StatBox("Poupança de captura")
        self._visual_updates = StatBox("Actualizações visuais")
        self._batched = StatBox("Acções agrupadas")
        details_grid.addWidget(self._capture_scope, 0, 0)
        details_grid.addWidget(self._capture_savings, 0, 1)
        details_grid.addWidget(self._visual_updates, 0, 2)
        details_grid.addWidget(self._batched, 1, 0, 1, 2)
        self._details_visible = False
        self._details_row.setVisible(False)
        root.addWidget(self._details_row)

        history_title = QLabel("EXECUÇÃO RECENTE")
        history_title.setFont(_font(7, QFont.Weight.DemiBold))
        history_title.setStyleSheet(f"color:{_FAINT};letter-spacing:1px;")
        root.addWidget(history_title)

        self._history = QTextEdit()
        self._history.setReadOnly(True)
        self._history.setFont(_font(9))
        root.addWidget(self._history, stretch=1)

        self._notice = QLabel("")
        self._notice.setWordWrap(True)
        self._notice.setFont(_font(8, QFont.Weight.Medium))
        self._notice.setStyleSheet(f"color:{_PINK};")
        root.addWidget(self._notice)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self._approve_button = QPushButton("APROVAR 1 PASSO")
        self._stop_button = QPushButton("PARAR AGENTE")
        close_button = QPushButton("Fechar")

        for button in (self._approve_button, self._stop_button, close_button):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(40)
            button.setFont(_font(9, QFont.Weight.DemiBold))

        self._approve_button.setStyleSheet(
            f"QPushButton{{background:{_VIOLET};color:#09060f;border:0;border-radius:9px;"
            "padding:0 17px;font-weight:700;}"
            f"QPushButton:hover{{background:{_VIOLET_SOFT};}}"
            f"QPushButton:focus{{background:{_VIOLET_SOFT};outline:none;}}"
            "QPushButton:disabled{background:#242331;color:#666378;}"
        )
        self._stop_button.setStyleSheet(
            f"QPushButton{{background:#24111a;color:{_RED};border:1px solid #4d2635;"
            "border-radius:9px;padding:0 15px;}"
            f"QPushButton:focus{{border-color:{_RED};outline:none;}}"
            "QPushButton:disabled{color:#6f4a56;border-color:#2b2025;}"
        )
        close_button.setStyleSheet(
            f"QPushButton{{background:{_SURFACE_2};color:{_MUTED};border:1px solid {_BORDER};"
            "border-radius:9px;padding:0 15px;}"
            f"QPushButton:focus{{color:{_TEXT};border-color:{_BORDER_HOVER};outline:none;}}"
        )

        # A QDialog turns plain QPushButtons into auto-default targets for
        # Return/Enter. Approval must never fire from a keyboard default;
        # only an explicit click (mouse, Space on the focused button) does.
        for button in (self._approve_button, self._stop_button, close_button):
            button.setAutoDefault(False)
            button.setDefault(False)

        self._approve_button.setAccessibleName("Aprovar o passo pendente do agente")
        self._stop_button.setAccessibleName("Parar o agente")
        close_button.setAccessibleName("Fechar painel do agente")

        self._approve_button.clicked.connect(self._approve)
        self._stop_button.clicked.connect(self._stop)
        close_button.clicked.connect(self.close)
        actions.addWidget(self._approve_button)
        actions.addWidget(self._stop_button)
        actions.addStretch()
        actions.addWidget(close_button)
        root.addLayout(actions)

        # Keyboard order follows the risk gradient: approve (explicit) ->
        # stop -> close.
        QWidget.setTabOrder(self._approve_button, self._stop_button)
        QWidget.setTabOrder(self._stop_button, close_button)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(500)
        self.refresh()

    # -.-.-.-
    def _toggle_details(self) -> None:
        self._details_visible = not self._details_visible
        self._details_row.setVisible(self._details_visible)
        self._details_toggle.setText(
            "▾ Detalhes técnicos" if self._details_visible else "▸ Detalhes técnicos"
        )

    # -.-.-.-
    def _stop(self) -> None:
        result = self._session.stop()
        self._notice.setText("Pedido de paragem enviado. O agente termina no próximo ponto seguro.")
        self._write_host_log("SYS: Computer Use · paragem solicitada pela interface")
        if not result.get("ok"):
            self._notice.setText(str(result.get("error") or "Não foi possível parar o agente."))
        self.refresh()

    # -.-.-.-
    def _approve(self) -> None:
        result = self._session.approve_once()
        if result.get("ok"):
            self._notice.setText("Aprovação concedida apenas para o passo actualmente pendente.")
            self._write_host_log("SYS: Computer Use · um passo aprovado pela interface")
        else:
            self._notice.setText(str(result.get("error") or "O agente não aguarda aprovação."))
        self.refresh()

    # -.-.-.-
    def _write_host_log(self, text: str) -> None:
        try:
            self._host._log.append_event(text)
        except Exception:
            pass

    # -.-.-.-
    def _set_progress(self, state: str) -> None:
        """Bounded progress presentation for the known-but-total-less step feed."""
        if state in _ACTIVE_STATES:
            self._progress.setRange(0, 0)
            self._progress.show()
        elif state == "done":
            self._progress.setRange(0, 1)
            self._progress.setValue(1)
            self._progress.setStyleSheet(
                f"QProgressBar{{background:#1b1d2b;border:0;border-radius:2px;}}"
                f"QProgressBar::chunk{{background:{_GREEN};border-radius:2px;}}"
            )
            self._progress.show()
        elif state == "failed":
            self._progress.setRange(0, 1)
            self._progress.setValue(1)
            self._progress.setStyleSheet(
                f"QProgressBar{{background:#1b1d2b;border:0;border-radius:2px;}}"
                f"QProgressBar::chunk{{background:{_RED};border-radius:2px;}}"
            )
            self._progress.show()
        else:
            self._progress.setRange(0, 1)
            self._progress.setValue(0)
            self._progress.hide()

    # -.-.-.-
    def _render_history(self, history: list[str]) -> None:
        if not history:
            self._history.setPlainText("Ainda não existem passos executados nesta tarefa.")
            return
        markup: list[str] = []
        for index, line in enumerate(history):
            clean = html.escape(str(line), quote=False)
            action, _, detail = clean.partition(": ")
            markup.append(
                f'<p><span style="color:{_VIOLET_SOFT};">{index + 1:02d}</span> '
                f'<span style="color:{_TEXT};font-weight:600;">{action}</span>'
                f'<span style="color:{_MUTED};"> · {detail}</span></p>'
            )
        self._history.setHtml("".join(markup))
        self._history.verticalScrollBar().setValue(self._history.verticalScrollBar().maximum())

    # -.-.-.-
    def refresh(self) -> None:
        try:
            status = self._session.status()
        except Exception as exc:
            self._notice.setText(f"Estado indisponível · {type(exc).__name__}")
            return

        state = str(status.get("state") or "idle").lower()
        label = _LABELS.get(state, state.replace("_", " ").title())
        if state == "failed":
            accent = _RED
        elif state == "awaiting_approval":
            accent = _PINK
        elif state == "done":
            accent = _GREEN
        elif state in _ACTIVE_STATES:
            accent = _VIOLET
        else:
            accent = _FAINT

        self._state_badge.setText(label.upper())
        self._state_badge.setStyleSheet(
            f"color:{accent};background:{_SURFACE_2};border:1px solid {_BORDER};border-radius:9px;"
        )
        self._set_progress(state)

        objective = str(status.get("objective") or "").strip()
        self._objective.setText(objective or "Nenhuma tarefa activa")
        self._step.set_value(str(int(status.get("step") or 0)))
        self._model_calls.set_value(str(int(status.get("model_calls") or 0)), _VIOLET_SOFT)
        saved = int(status.get("saved_model_calls") or 0)
        self._saved_calls.set_value(str(saved), _GREEN if saved else _MUTED)

        target_window = str(status.get("target_window") or "").strip()
        self._target_window.set_value(
            target_window[:48] if target_window else "—",
            _BLUE if target_window else _MUTED,
        )

        requested = status.get("requested_monitor")
        resolved = status.get("monitor_index")
        if requested not in {None, "", "active", "auto"}:
            display_text = f"{resolved or requested} · fixo"
        elif resolved:
            display_text = f"{resolved} · auto"
        else:
            display_text = "Auto"
        self._display.set_value(display_text, _BLUE)

        cost_text, cost_mode = _format_cost(status)
        cost_color = (
            _GREEN
            if status.get("cost_complete") and status.get("estimated_cost_usd") is not None
            else _BLUE if cost_mode == "balanced" else _MUTED
        )
        self._cost.set_value(cost_text, cost_color)

        self._provider.set_value(str(status.get("provider") or "—"))
        self._model.set_value(str(status.get("model") or "—"))

        self._capture_scope.set_value(
            "Janela"
            if str(status.get("capture_scope") or "monitor") == "window"
            else "Monitor completo",
            _BLUE,
        )
        savings = int(status.get("capture_savings_pct") or 0)
        self._capture_savings.set_value(
            f"{savings}%", _GREEN if savings else _MUTED
        )
        self._visual_updates.set_value(str(int(status.get("visual_updates") or 0)))
        self._batched.set_value(str(int(status.get("batched_actions") or 0)))

        history = list(status.get("history") or [])
        history_key = tuple(history)
        if history_key != self._last_history:
            self._render_history(history)
            self._last_history = history_key

        self._stop_button.setEnabled(state in _ACTIVE_STATES and state != "stopping")
        self._approve_button.setEnabled(state == "awaiting_approval")
        pending = str(status.get("last_action") or "").strip()
        if state == "awaiting_approval":
            self._approve_button.setText(
                f"APROVAR: {pending[:38]}" if pending else "APROVAR 1 PASSO"
            )
        else:
            self._approve_button.setText("APROVAR 1 PASSO")

        if state == "awaiting_approval":
            self._notice.setText(
                f"Aprovação necessária para: {pending or 'passo sensível'}"
            )
        elif state == "failed":
            self._notice.setText(str(status.get("last_error") or "A tarefa falhou."))
        elif state == "done":
            self._notice.setText(str(status.get("result") or "Tarefa concluída."))
        elif state not in _ACTIVE_STATES:
            self._notice.setText("")


# -.-.-.-
def show_agent_control(host_window: Any) -> AgentControlDialog:
    existing = getattr(host_window, "_agent_control_dialog", None)
    if existing is not None and existing.isVisible():
        existing.raise_()
        existing.activateWindow()
        existing.refresh()
        return existing

    dialog = AgentControlDialog(host_window)
    host_window._agent_control_dialog = dialog
    dialog.show()
    return dialog
