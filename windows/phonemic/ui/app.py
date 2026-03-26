"""PhoneMic main window – PySide6."""
from __future__ import annotations

import ctypes
import os
import sys
import threading
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QLineEdit, QCheckBox,
    QSizePolicy, QSystemTrayIcon, QMenu, QTabWidget,
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QPoint
from PySide6.QtGui import QColor, QIcon, QAction

from ..constants import CLR_BLUE, CLR_RED, CLR_GREEN, CLR_GRAY, BG_DARK, BG_PANEL
from ..config import AppConfig, load_config, save_config
from ..audio.client import PhoneMicClient
from .widgets import MicSphere

# ── Palette ────────────────────────────────────────────────────────────────
C_BG     = "#1a1b1e"
C_CARD   = "#25262b"
C_BORDER = "#2c2e33"
C_TEXT   = "#c1c2c5"
C_MUTED  = "#909296"
C_PURPLE = "#845ef7"
C_RED    = "#fa5252"
C_ORANGE = "#f59f00"
C_GREEN  = "#37b24d"

# ── QSS ────────────────────────────────────────────────────────────────────
QSS = f"""
QWidget {{
    background-color: {C_BG};
    color: {C_TEXT};
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}}
QFrame#card {{
    background-color: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 12px;
}}
QLabel#title {{
    font-size: 22px;
    font-weight: bold;
    color: #ffffff;
    background: transparent;
}}
QLabel#subtitle {{
    font-size: 11px;
    color: {C_MUTED};
    background: transparent;
}}
QLabel#section {{
    font-size: 10px;
    font-weight: bold;
    color: {C_MUTED};
    letter-spacing: 1px;
    background: transparent;
}}
QLabel#status_text {{
    font-size: 13px;
    color: {C_MUTED};
    background: transparent;
}}
QLabel#pct {{
    font-size: 12px;
    color: {C_MUTED};
    background: transparent;
}}
QTabWidget::pane {{
    border: none;
    background: transparent;
}}
QTabBar {{
    background: {C_CARD};
    border-radius: 8px;
}}
QTabBar::tab {{
    background: transparent;
    color: {C_MUTED};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 9px 0px;
    min-width: 120px;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    color: {C_PURPLE};
    border-bottom: 2px solid {C_PURPLE};
}}
QTabBar::tab:hover:!selected {{
    color: {C_TEXT};
}}
QComboBox {{
    background-color: {C_BG};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    color: {C_TEXT};
    padding: 7px 12px;
    font-size: 13px;
}}
QComboBox:hover {{
    border-color: {C_PURPLE};
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {C_MUTED};
    width: 0; height: 0;
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    color: {C_TEXT};
    selection-background-color: {C_PURPLE};
    selection-color: white;
    outline: none;
    padding: 4px;
}}
QLineEdit {{
    background-color: {C_BG};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    color: {C_TEXT};
    padding: 6px 10px;
    font-size: 13px;
}}
QLineEdit:focus {{
    border-color: {C_PURPLE};
}}
QSlider::groove:horizontal {{
    background: {C_BORDER};
    height: 4px;
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {C_PURPLE};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {C_PURPLE};
    border: 2px solid {C_PURPLE};
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: -5px 0;
}}
QSlider::handle:horizontal:hover {{
    background: #9775fa;
    border-color: #9775fa;
}}
QSlider::groove:horizontal:disabled {{
    background: #2c2e33;
}}
QSlider::sub-page:horizontal:disabled {{
    background: #3a3b3f;
}}
QSlider::handle:horizontal:disabled {{
    background: #444;
    border-color: #444;
}}
QCheckBox {{
    background: transparent;
    color: {C_TEXT};
    spacing: 8px;
    font-size: 12px;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    background: {C_BG};
}}
QCheckBox::indicator:checked {{
    background: {C_PURPLE};
    border-color: {C_PURPLE};
}}
QPushButton#btn_main {{
    background-color: transparent;
    color: {C_GREEN};
    border: 2px solid {C_GREEN};
    border-radius: 10px;
    padding: 13px;
    font-size: 15px;
    font-weight: bold;
}}
QPushButton#btn_main:hover {{
    background-color: {C_GREEN};
    color: white;
}}
QPushButton#btn_main:disabled {{
    border-color: #2a4a2f;
    color: #2a4a2f;
    background-color: transparent;
}}
QPushButton#btn_main[state="disconnect"] {{
    background-color: transparent;
    border: 2px solid {C_RED};
    color: {C_RED};
}}
QPushButton#btn_main[state="disconnect"]:hover {{
    background-color: {C_RED};
    color: white;
}}
QPushButton#btn_main[state="connecting"] {{
    background-color: transparent;
    border: 2px solid {C_ORANGE};
    color: {C_ORANGE};
}}
"""


# ── Helpers ────────────────────────────────────────────────────────────────
class _NoScrollCombo(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class _Bridge(QObject):
    status         = Signal(str)
    connect_result = Signal(bool, str)
    disconnected   = Signal(bool)


# ── Main App window ────────────────────────────────────────────────────────
class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhoneMic")
        self.setMinimumSize(360, 420)
        self.resize(420, 520)
        self.setStyleSheet(QSS)
        self.setWindowIcon(self._load_icon())
        QTimer.singleShot(0, self._apply_dark_titlebar)

        self._bridge          = _Bridge()
        self._client          = PhoneMicClient()
        self._config          = load_config()
        self._connecting      = False
        self._timeout_timer: Optional[QTimer] = None
        self._tray: Optional[QSystemTrayIcon]  = None

        self._bridge.status.connect(self._on_status)
        self._bridge.connect_result.connect(self._on_connect_result)
        self._bridge.disconnected.connect(self._on_disconnected)

        # ── Root layout ───────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 12, 20, 14)
        root.setSpacing(10)

        self._build_header(root)
        self._build_tabs(root)
        self._build_connect_btn(root)

        self._load_config()
        self._setup_tray()
        self._center()

    # ── Center window ─────────────────────────────────────────────────────
    def _center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        fg = self.frameGeometry()
        fg.moveCenter(screen.center())
        self.move(fg.topLeft())

    # ── Header ────────────────────────────────────────────────────────────
    def _build_header(self, root: QVBoxLayout):
        lbl_title = QLabel("PhoneMic")
        lbl_title.setObjectName("title")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(lbl_title)

        lbl_sub = QLabel("Usa tu teléfono como micrófono")
        lbl_sub.setObjectName("subtitle")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(lbl_sub)

    # ── Tabs ──────────────────────────────────────────────────────────────
    def _build_tabs(self, root: QVBoxLayout):
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_mic_tab(),    "🎤  Micrófono")
        self._tabs.addTab(self._build_config_tab(), "⚙️  Configuración")
        root.addWidget(self._tabs, 1)

    # ── Tab 0: Micrófono ──────────────────────────────────────────────────
    def _build_mic_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 16, 0, 8)
        lay.setSpacing(8)

        # Sphere
        row_sphere = QHBoxLayout()
        row_sphere.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sphere = MicSphere()
        self._sphere.clicked.connect(self._toggle_mute)
        row_sphere.addWidget(self._sphere)
        lay.addLayout(row_sphere)

        # Status
        row_status = QHBoxLayout()
        row_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row_status.setSpacing(6)
        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color: {C_MUTED}; font-size: 9px; background: transparent;")
        row_status.addWidget(self._dot)
        self._lbl_status = QLabel("Desconectado")
        self._lbl_status.setObjectName("status_text")
        row_status.addWidget(self._lbl_status)
        lay.addLayout(row_status)

        lay.addSpacing(4)

        # Noise gate
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C_BORDER};")
        lay.addWidget(sep)

        lbl_aud = QLabel("AJUSTES DE AUDIO")
        lbl_aud.setObjectName("section")
        lay.addWidget(lbl_aud)

        self._chk_ng = QCheckBox("Noise gate")
        self._chk_ng.stateChanged.connect(self._on_ng_toggle)
        lay.addWidget(self._chk_ng)

        self._ng_widget = QWidget()
        self._ng_widget.setStyleSheet("background: transparent;")
        ng_lay = QVBoxLayout(self._ng_widget)
        ng_lay.setContentsMargins(0, 4, 0, 0)
        ng_lay.setSpacing(4)
        ng_hdr = QHBoxLayout()
        lbl_ng = QLabel("Umbral")
        lbl_ng.setObjectName("section")
        ng_hdr.addWidget(lbl_ng)
        ng_hdr.addStretch()
        self._lbl_ng_pct = QLabel("2%")
        self._lbl_ng_pct.setObjectName("pct")
        ng_hdr.addWidget(self._lbl_ng_pct)
        ng_lay.addLayout(ng_hdr)
        self._slider_ng = QSlider(Qt.Orientation.Horizontal)
        self._slider_ng.setRange(0, 20)
        self._slider_ng.setValue(2)
        self._slider_ng.valueChanged.connect(self._on_ng_threshold)
        ng_lay.addWidget(self._slider_ng)
        self._slider_ng.setEnabled(False)  # disabled until checkbox checked
        lay.addWidget(self._ng_widget)

        return page

    # ── Tab 1: Configuración ──────────────────────────────────────────────
    def _build_config_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 16, 0, 8)
        lay.setSpacing(10)

        # Connection mode
        lbl_mode = QLabel("MODO DE CONEXIÓN")
        lbl_mode.setObjectName("section")
        lay.addWidget(lbl_mode)

        self._combo_mode = _NoScrollCombo()
        self._combo_mode.addItem("🔌  USB (ADB)", "usb")
        self._combo_mode.addItem("📶  WiFi", "wifi")
        self._combo_mode.currentIndexChanged.connect(self._on_mode_change)
        lay.addWidget(self._combo_mode)

        # WiFi IP row
        self._wifi_widget = QWidget()
        self._wifi_widget.setStyleSheet("background: transparent;")
        wifi_lay = QHBoxLayout(self._wifi_widget)
        wifi_lay.setContentsMargins(0, 0, 0, 0)
        wifi_lay.setSpacing(8)
        lbl_ip = QLabel("IP del celular")
        lbl_ip.setStyleSheet(f"color: {C_MUTED}; font-size: 12px; background: transparent;")
        wifi_lay.addWidget(lbl_ip)
        self._entry_ip = QLineEdit()
        self._entry_ip.setPlaceholderText("192.168.1.x")
        self._entry_ip.setMaximumWidth(150)
        wifi_lay.addWidget(self._entry_ip)
        lbl_port = QLabel(":7777")
        lbl_port.setStyleSheet(f"color: {C_MUTED}; font-size: 12px; background: transparent;")
        wifi_lay.addWidget(lbl_port)
        wifi_lay.addStretch()
        self._wifi_widget.hide()
        lay.addWidget(self._wifi_widget)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C_BORDER};")
        lay.addWidget(sep)

        # Audio device
        lbl_dev = QLabel("DISPOSITIVO DE AUDIO")
        lbl_dev.setObjectName("section")
        lay.addWidget(lbl_dev)

        self._combo_dev = _NoScrollCombo()
        self._devices = self._client.get_output_devices()
        for idx, name in self._devices:
            self._combo_dev.addItem(name, idx)
        preferred = self._client.find_virtual_device_index(self._devices)
        self._combo_dev.setCurrentIndex(preferred)
        lay.addWidget(self._combo_dev)

        if self._client.is_vbcable_available(self._devices):
            lbl_hint = QLabel("✓ VB-Cable detectado — selecciona «CABLE Output» en Discord/Zoom")
            lbl_hint.setStyleSheet(f"color: {C_GREEN}; font-size: 11px; background: transparent;")
        else:
            lbl_hint = QLabel("Sin micrófono virtual — instala VB-Cable para Discord/Zoom")
            lbl_hint.setStyleSheet(f"color: {C_MUTED}; font-size: 11px; background: transparent;")
        lbl_hint.setWordWrap(True)
        lay.addWidget(lbl_hint)

        lay.addStretch()
        return page

    # ── Connect button ────────────────────────────────────────────────────
    def _build_connect_btn(self, root: QVBoxLayout):
        self._btn_connect = QPushButton("Conectar")
        self._btn_connect.setObjectName("btn_main")
        self._btn_connect.setMinimumHeight(48)
        self._btn_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_connect.clicked.connect(self._toggle_connect)
        root.addWidget(self._btn_connect)

    # ── Actions ───────────────────────────────────────────────────────────
    def _toggle_connect(self):
        if self._connecting:
            return
        if self._client.is_running:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        if self._connecting:
            return
        self._connecting = True

        dev_idx = self._combo_dev.currentData()
        mode    = self._combo_mode.currentData()
        wifi_ip = self._entry_ip.text().strip()

        self._client.connection_mode      = mode
        self._client.wifi_ip              = wifi_ip
        self._client.noise_gate_enabled   = self._chk_ng.isChecked()
        self._client.noise_gate_threshold = self._slider_ng.value() / 100.0
        self._save_config()

        self._btn_connect.setText("Conectando...")
        self._btn_connect.setProperty("state", "connecting")
        self._btn_connect.style().unpolish(self._btn_connect)
        self._btn_connect.style().polish(self._btn_connect)
        self._btn_connect.setEnabled(False)
        self._combo_mode.setEnabled(False)
        self._combo_dev.setEnabled(False)
        self._sphere.set_state(MicSphere.CONNECTING)
        self._set_status("Conectando...", C_ORANGE)

        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(lambda: self._bridge.connect_result.emit(
            False, "Tiempo de espera agotado (10 s).\n¿Está PhoneMic activo en el celular?"
        ))
        self._timeout_timer.start(10_000)

        def _work():
            ok, msg = self._client.start(
                dev_idx,
                status_callback=lambda m: self._bridge.status.emit(m),
            )
            self._bridge.connect_result.emit(ok, msg)

        threading.Thread(target=_work, daemon=True).start()

    def _on_connect_result(self, ok: bool, msg: str):
        if not self._connecting:
            return
        self._connecting = False
        if self._timeout_timer:
            self._timeout_timer.stop()
            self._timeout_timer = None

        self._combo_mode.setEnabled(True)
        self._combo_dev.setEnabled(True)

        if ok:
            self._btn_connect.setEnabled(True)
            self._btn_connect.setText("Desconectar")
            self._btn_connect.setProperty("state", "disconnect")
            self._btn_connect.style().unpolish(self._btn_connect)
            self._btn_connect.style().polish(self._btn_connect)
            self._sphere.set_state(MicSphere.CONNECTED)
            self._set_status("Conectado", C_GREEN)
            self._tabs.setCurrentIndex(0)   # ir a pestaña Micrófono
            self._start_pulse()
        else:
            self._client.stop()
            self._btn_connect.setEnabled(True)
            self._btn_connect.setText("Conectar")
            self._btn_connect.setProperty("state", "")
            self._btn_connect.style().unpolish(self._btn_connect)
            self._btn_connect.style().polish(self._btn_connect)
            self._sphere.set_state(MicSphere.DISCONNECTED)
            self._set_status("Desconectado", C_MUTED)
            self._show_error("Error al conectar", msg)

    def _disconnect(self):
        self._connecting = False
        if hasattr(self, "_pulse_timer"):
            self._pulse_timer.stop()
        self._client.stop()
        self._btn_connect.setText("Conectar")
        self._btn_connect.setProperty("state", "")
        self._btn_connect.style().unpolish(self._btn_connect)
        self._btn_connect.style().polish(self._btn_connect)
        self._btn_connect.setEnabled(True)
        self._combo_mode.setEnabled(True)
        self._combo_dev.setEnabled(True)
        self._client.muted = False
        self._sphere.set_state(MicSphere.DISCONNECTED)
        self._set_status("Desconectado", C_MUTED)
        self._tabs.setCurrentIndex(1)   # ir a pestaña Configuración

    def _toggle_mute(self):
        if not self._client.is_running:
            return
        self._client.muted = not self._client.muted
        if self._client.muted:
            self._sphere.set_state(MicSphere.MUTED)
            self._set_status("Micrófono silenciado", C_RED)
        else:
            self._sphere.set_state(MicSphere.CONNECTED)
            self._set_status("Conectado", C_GREEN)

    # ── Pulse check ───────────────────────────────────────────────────────
    def _start_pulse(self):
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(1000)
        self._pulse_timer.timeout.connect(self._pulse_check)
        self._pulse_timer.start()

    def _pulse_check(self):
        if self._client.is_running:
            return
        self._pulse_timer.stop()
        no_data = getattr(self._client, "_no_data", False)
        self._sphere.set_state(MicSphere.DISCONNECTED)
        self._btn_connect.setText("Conectar")
        self._btn_connect.setProperty("state", "")
        self._btn_connect.style().unpolish(self._btn_connect)
        self._btn_connect.style().polish(self._btn_connect)
        self._combo_mode.setEnabled(True)
        self._combo_dev.setEnabled(True)
        self._client.muted = False
        self._tabs.setCurrentIndex(1)
        if no_data:
            msg = "PhoneMic no está iniciado en el celular.\nAbre la app y toca «Iniciar»."
            self._set_status("App no iniciada en el celular.", C_RED)
            self._show_error("App no iniciada", msg)
        else:
            self._set_status("Conexión perdida.", C_RED)

    def _on_disconnected(self, no_data: bool):
        pass

    # ── Helpers ───────────────────────────────────────────────────────────
    def _set_status(self, text: str, color: str = C_MUTED):
        self._lbl_status.setText(text)
        self._dot.setStyleSheet(f"color: {color}; font-size: 9px; background: transparent;")
        self._lbl_status.setStyleSheet(f"font-size: 13px; color: {color}; background: transparent;")

    def _on_status(self, msg: str):
        self._lbl_status.setText(msg)

    def _on_mode_change(self, idx: int):
        if self._combo_mode.currentData() == "wifi":
            self._wifi_widget.show()
        else:
            self._wifi_widget.hide()

    def _on_ng_toggle(self, state: int):
        self._slider_ng.setEnabled(bool(state))
        self._lbl_ng_pct.setEnabled(bool(state))

    def _on_ng_threshold(self, val: int):
        self._lbl_ng_pct.setText(f"{val}%")
        self._client.noise_gate_threshold = val / 100.0

    def _show_error(self, title: str, msg: str):
        from PySide6.QtWidgets import QDialog
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setStyleSheet(QSS + f"QDialog {{ background: {C_CARD}; }}")
        dlg.setMinimumWidth(320)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 15px; font-weight: bold; color: white; background: transparent;")
        lay.addWidget(lbl_t)
        lbl_m = QLabel(msg)
        lbl_m.setWordWrap(True)
        lbl_m.setStyleSheet(f"font-size: 12px; color: {C_MUTED}; background: transparent;")
        lay.addWidget(lbl_m)
        btn_ok = QPushButton("OK")
        btn_ok.setObjectName("btn_main")
        btn_ok.clicked.connect(dlg.accept)
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(btn_ok)
        dlg.exec()

    # ── Config ────────────────────────────────────────────────────────────
    def _load_config(self):
        cfg = self._config
        if cfg.mode == "wifi":
            self._combo_mode.setCurrentIndex(1)
            self._wifi_widget.show()
        self._entry_ip.setText(cfg.wifi_ip)
        self._chk_ng.setChecked(cfg.noise_gate)
        self._slider_ng.setValue(int(cfg.noise_gate_threshold * 100))
        self._slider_ng.setEnabled(cfg.noise_gate)
        self._lbl_ng_pct.setEnabled(cfg.noise_gate)

    def _save_config(self):
        cfg = AppConfig(
            wifi_ip=self._entry_ip.text().strip(),
            mode=self._combo_mode.currentData(),
            high_quality=False,
            noise_gate=self._chk_ng.isChecked(),
            noise_gate_threshold=self._slider_ng.value() / 100.0,
        )
        save_config(cfg)

    # ── System tray ───────────────────────────────────────────────────────
    def _setup_tray(self):
        icon = self._load_icon()
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("PhoneMic")
        menu = QMenu()
        menu.setStyleSheet(QSS)
        act_show = QAction("Abrir PhoneMic", self)
        act_show.triggered.connect(self._show_window)
        act_quit = QAction("Salir", self)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_show)
        menu.addSeparator()
        menu.addAction(act_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _apply_dark_titlebar(self):
        try:
            hwnd   = int(self.winId())
            dwmapi = ctypes.windll.dwmapi  # type: ignore[attr-defined]
            val1   = ctypes.c_int(1)
            sz     = ctypes.sizeof(ctypes.c_int)
            dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(val1), sz)
            dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val1), sz)
            black = ctypes.c_int(0x00000000)
            dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(black), sz)
        except Exception:
            pass

    def _load_icon(self) -> QIcon:
        if getattr(sys, "frozen", False):
            search_dirs = [
                os.path.dirname(sys.executable),
                getattr(sys, "_MEIPASS", ""),
            ]
        else:
            search_dirs = [os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)
            )))]
        for base in search_dirs:
            for ext in ("ico", "png"):
                path = os.path.join(base, f"phonemic.{ext}")
                if os.path.exists(path):
                    return QIcon(path)
        return QIcon()

    def _quit(self):
        self._client.cleanup()
        if self._tray:
            self._tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def changeEvent(self, event):
        super().changeEvent(event)
