from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import get_config
from core.runtime_preferences import apply_session_preferences


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
_GREEN = "#68e6b2"


# -.-.-.-
def _font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    return QFont("Segoe UI Variable", size, weight)


class ExplicitCommitButton(QPushButton):
    """Commit control that never treats Enter or Return as activation.

    Keyboard navigation remains available and Space keeps the normal Qt
    push-button activation semantics. This mirrors the fail-closed approval
    control without removing keyboard accessibility.
    """

    # -.-.-.-
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            event.accept()
            return
        super().keyPressEvent(event)


class AntonellaSettingsDialog(QDialog):
    def __init__(self, host_window: Any):
        super().__init__(host_window)
        self._host = host_window
        self._config = get_config()

        self.setWindowTitle("Antonella · Preferências")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet(
            f"QDialog{{background:{_BG};color:{_TEXT};}}"
            f"QLabel{{background:transparent;color:{_TEXT};}}"
            f"QLineEdit,QComboBox{{background:{_SURFACE_2};color:{_TEXT};border:1px solid {_BORDER};"
            "border-radius:9px;padding:8px 10px;min-height:22px;}"
            f"QLineEdit:focus,QComboBox:focus{{border-color:{_VIOLET};}}"
            f"QComboBox QAbstractItemView{{background:{_SURFACE_2};color:{_TEXT};"
            f"selection-background-color:{_VIOLET};border:1px solid {_BORDER};}}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(16)

        title = QLabel("PREFERÊNCIAS DA ANTONELLA")
        title.setFont(_font(14, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color:{_VIOLET_SOFT};letter-spacing:1px;")
        root.addWidget(title)

        subtitle = QLabel(
            "Controla inteligência, custo e voz sem alterar a arquitectura nem expor segredos."
        )
        subtitle.setWordWrap(True)
        subtitle.setFont(_font(9))
        subtitle.setStyleSheet(f"color:{_MUTED};")
        root.addWidget(subtitle)

        root.addWidget(self._build_intelligence_card())
        root.addWidget(self._build_keys_card())

        note = QLabel(
            "As chaves introduzidas aqui ficam apenas nesta sessão. Para persistência, "
            "usa variáveis ANTONELLA_* no sistema. A voz e o esquema de ferramentas Live "
            "podem exigir reinício da Antonella."
        )
        note.setWordWrap(True)
        note.setFont(_font(8))
        note.setStyleSheet(f"color:{_FAINT};")
        root.addWidget(note)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancelar")
        apply_button = ExplicitCommitButton("Aplicar")
        for button in (cancel, apply_button):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(38)
            button.setFont(_font(9, QFont.Weight.DemiBold))
        cancel.setStyleSheet(
            f"QPushButton{{background:{_SURFACE_2};color:{_MUTED};border:1px solid {_BORDER};"
            "border-radius:9px;padding:0 16px;}"
            f"QPushButton:focus{{color:{_TEXT};border-color:{_BORDER_HOVER};outline:none;}}"
        )
        apply_button.setStyleSheet(
            f"QPushButton{{background:{_VIOLET};color:#09060f;border:0;border-radius:9px;"
            "padding:0 18px;font-weight:700;}"
            f"QPushButton:hover{{background:{_VIOLET_SOFT};}}"
            f"QPushButton:focus{{background:{_VIOLET_SOFT};outline:none;}}"
        )

        # Settings commit must be an explicit action. Disabling QDialog's
        # default-button promotion is necessary but not sufficient: the
        # focused commit button also consumes Return/Enter itself.
        cancel.setAutoDefault(False)
        cancel.setDefault(False)
        apply_button.setAutoDefault(False)
        apply_button.setDefault(False)
        cancel.setAccessibleName("Cancelar alterações")
        apply_button.setAccessibleName("Aplicar preferências")

        cancel.clicked.connect(self.reject)
        apply_button.clicked.connect(self._apply)
        buttons.addWidget(cancel)
        buttons.addWidget(apply_button)
        root.addLayout(buttons)

        # Keyboard order: cancel (safe) before apply (commit).
        QWidget.setTabOrder(cancel, apply_button)

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("settingsCard")
        card.setStyleSheet(
            f"QFrame#settingsCard{{background:{_SURFACE};border:1px solid {_BORDER};border-radius:12px;}}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        return card, layout

    def _build_intelligence_card(self) -> QFrame:
        card, layout = self._card()
        heading = QLabel("INTELIGÊNCIA")
        heading.setFont(_font(8, QFont.Weight.DemiBold))
        heading.setStyleSheet(f"color:{_MUTED};letter-spacing:1px;")
        layout.addWidget(heading)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self._provider = QComboBox()
        self._provider.addItem("Automático — escolhe o melhor disponível", "auto")
        self._provider.addItem("Preferir OpenAI", "openai")
        self._provider.addItem("Preferir Gemini", "gemini")
        self._select_combo(self._provider, str(self._config.get("model_provider_preference") or "auto"))

        self._cost = QComboBox()
        self._cost.addItem("Económico — mínimo de chamadas", "economy")
        self._cost.addItem("Equilibrado — mais margem", "balanced")
        self._cost.addItem("Qualidade — máximo de detalhe", "quality")
        self._select_combo(self._cost, str(self._config.get("computer_use_cost_mode") or "economy"))

        self._voice = QLineEdit(str(self._config.get("voice_name") or "Kore"))
        self._voice.setPlaceholderText("Kore")

        form.addRow("Provider", self._provider)
        form.addRow("Computer Use", self._cost)
        form.addRow("Voz Live", self._voice)
        layout.addLayout(form)
        return card

    def _build_keys_card(self) -> QFrame:
        card, layout = self._card()
        heading = QLabel("PROVIDERS")
        heading.setFont(_font(8, QFont.Weight.DemiBold))
        heading.setStyleSheet(f"color:{_MUTED};letter-spacing:1px;")
        layout.addWidget(heading)

        gemini_ready = bool(str(self._config.get("gemini_api_key") or "").strip())
        openai_ready = bool(str(self._config.get("openai_api_key") or "").strip())

        status = QLabel(
            f"Gemini  {'● configurado' if gemini_ready else '○ não configurado'}     "
            f"OpenAI  {'● configurado' if openai_ready else '○ opcional'}"
        )
        status.setFont(_font(9, QFont.Weight.Medium))
        status.setStyleSheet(f"color:{_GREEN if gemini_ready else _MUTED};")
        layout.addWidget(status)

        form = QFormLayout()
        form.setSpacing(10)

        self._gemini_key = QLineEdit()
        self._gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._gemini_key.setPlaceholderText("Nova chave Gemini · deixar vazio para manter")

        self._openai_key = QLineEdit()
        self._openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._openai_key.setPlaceholderText("Nova chave OpenAI · deixar vazio para manter")

        form.addRow("Gemini", self._gemini_key)
        form.addRow("OpenAI", self._openai_key)
        layout.addLayout(form)
        return card

    @staticmethod
    def _select_combo(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _apply(self) -> None:
        result = apply_session_preferences(
            gemini_api_key=self._gemini_key.text(),
            openai_api_key=self._openai_key.text(),
            cost_mode=str(self._cost.currentData() or "economy"),
            provider_preference=str(self._provider.currentData() or "auto"),
            voice_name=self._voice.text(),
        )

        changed = result.get("changed") or []
        if changed:
            try:
                self._host._log.append_event(
                    "SYS: preferências actualizadas · " + ", ".join(str(item) for item in changed)
                )
            except Exception:
                pass

        if result.get("restart_required"):
            try:
                self._host._log.append_event(
                    "SYS: reinicia a Antonella para aplicar voz/especialista à sessão Live"
                )
            except Exception:
                pass

        if bool(str(get_config().get("gemini_api_key") or "").strip()):
            self._host._ready = True

        dashboard = getattr(self._host, "_runtime_dashboard", None)
        if dashboard is not None:
            try:
                dashboard.refresh()
            except Exception:
                pass

        self.accept()


# -.-.-.-
def show_settings_dialog(ui) -> None:
    window = getattr(ui, "_win", None)
    if window is None:
        return
    AntonellaSettingsDialog(window).exec()


# -.-.-.-
def bind_settings_button(ui) -> bool:
    """Upgrade the existing top-right ellipsis without changing the approved base UI file."""
    window = getattr(ui, "_win", None)
    if window is None:
        return False

    buttons = window.findChildren(QPushButton)
    target = next((button for button in buttons if button.text() == "•••"), None)
    if target is None:
        return False

    try:
        target.clicked.disconnect()
    except TypeError:
        pass

    target.clicked.connect(lambda: show_settings_dialog(ui))
    target.setToolTip("Preferências da Antonella")
    window._configure_api_key = lambda: show_settings_dialog(ui)
    return True
