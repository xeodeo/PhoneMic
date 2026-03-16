"""
PhoneMic Client - Windows
Recibe audio del micrófono del celular via USB ADB y lo reproduce
en un dispositivo de audio virtual (ej. VB-Cable) para usarlo como micrófono.
"""

import ctypes
import json
import os
import socket as _socket
import struct
import subprocess
import sys
import threading
from typing import Optional
import tkinter as tk
from tkinter import ttk, messagebox
import sounddevice as sd             # type: ignore[import]
import pystray                       # type: ignore[import]
from PIL import Image, ImageDraw     # type: ignore[import]


def _find_adb() -> str:
    """Devuelve la ruta a adb.exe: primero busca junto al .exe empaquetado,
    luego en la misma carpeta del script, y por último usa el PATH del sistema."""
    base = (
        os.path.dirname(sys.executable)
        if getattr(sys, "frozen", False)          # empaquetado con PyInstaller
        else os.path.dirname(os.path.abspath(__file__))
    )
    bundled = os.path.join(base, "adb.exe")
    return bundled if os.path.exists(bundled) else "adb"


ADB = _find_adb()

PORT        = 7777
SAMPLE_RATE = 16000
CHANNELS    = 1
CHUNK       = 4096

# ── Discord color palette ────────────────────────────────────────────────────
BG_DARK    = "#1e1f22"
BG_PANEL   = "#2b2d31"
CLR_TEXT   = "#f2f3f5"
CLR_MUTED  = "#80848e"
CLR_SUB    = "#b5bac1"
CLR_GREEN  = "#23a55a"
CLR_RED    = "#f23f43"
CLR_BLUE   = "#5865f2"
CLR_GRAY   = "#4f545c"
# ────────────────────────────────────────────────────────────────────────────


def _scale_volume(data: bytes, factor: float) -> bytes:
    """Scale PCM 16-bit LE audio by factor (0.0 – 1.0+)."""
    if factor >= 1.0:
        return data
    n = len(data) // 2
    samples = struct.unpack_from(f"<{n}h", data)
    scaled = [max(-32768, min(32767, int(s * factor))) for s in samples]
    return struct.pack(f"<{n}h", *scaled)


class PhoneMicClient:
    def __init__(self) -> None:
        self.is_running: bool = False
        self.muted: bool      = False
        self.volume: float    = 1.0
        self.stream: Optional[sd.RawOutputStream] = None
        self.sock:   Optional[_socket.socket]     = None
        self._thread: Optional[threading.Thread]  = None
        self.connection_mode: str = "usb"   # "usb" | "wifi"
        self.wifi_ip: str = ""

    def setup_adb_forward(self):
        try:
            _cflags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
            check = subprocess.run(
                [ADB, "devices"], capture_output=True, text=True,
                timeout=5, creationflags=_cflags,
            )
            lines = [l for l in check.stdout.splitlines() if "\t" in l]
            if not lines:
                return False, (
                    "No se detectó ningún celular por USB.\n\n"
                    "Revisa lo siguiente:\n"
                    "• Conecta el cable USB al PC\n"
                    "• En el celular: Ajustes → Opciones de desarrollador → Depuración USB (activar)\n"
                    "• Si aparece un aviso en el celular, toca «Permitir»"
                )
            result = subprocess.run(
                [ADB, "forward", f"tcp:{PORT}", f"tcp:{PORT}"],
                capture_output=True, text=True, timeout=5, creationflags=_cflags,
            )
            if result.returncode != 0:
                return False, f"Error ADB: {result.stderr.strip()}"
            return True, "ADB forward configurado"
        except FileNotFoundError:
            return False, (
                "adb.exe no encontrado.\n"
                "Copia adb.exe junto a PhoneMic.exe o instala Android SDK Platform Tools."
            )
        except subprocess.TimeoutExpired:
            return False, "ADB tardó demasiado. ¿Está el celular conectado?"
        except Exception as e:
            return False, str(e)

    def remove_adb_forward(self):
        try:
            _cflags = 0x08000000 if sys.platform == "win32" else 0
            subprocess.run(
                [ADB, "forward", "--remove", f"tcp:{PORT}"],
                capture_output=True, timeout=3, creationflags=_cflags,
            )
        except Exception:
            pass

    def get_output_devices(self):
        devices = []
        for i, d in enumerate(sd.query_devices()):
            if d["max_output_channels"] > 0:
                devices.append((i, d["name"]))
        return devices

    def find_virtual_device_index(self, devices):
        # Prioridad: CABLE Input (VB-Cable) > otros virtuales > primero disponible
        priority = ["cable input", "cable", "vb-audio", "voicemeeter", "vac", "virtual"]
        for keyword in priority:
            for idx, (_, name) in enumerate(devices):
                if keyword in name.lower():
                    return idx
        return 0

    def is_vbcable_available(self, devices) -> bool:
        return any("cable" in name.lower() for _, name in devices)

    def start(self, device_index, status_callback=None):
        def cb(msg):
            if status_callback:
                status_callback(msg)

        if self.connection_mode == "usb":
            cb("Configurando ADB...")
            ok, adb_msg = self.setup_adb_forward()
            if not ok:
                return False, adb_msg
            host = "127.0.0.1"
        else:
            host = self.wifi_ip.strip()
            if not host:
                return False, "Ingresa la IP del celular para modo WiFi."

        cb("Conectando al celular...")
        try:
            sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, PORT))
            sock.settimeout(None)
            self.sock = sock
        except ConnectionRefusedError:
            return False, (
                "Conexión rechazada.\n"
                "¿Abriste PhoneMic en el celular y presionaste Iniciar?"
            )
        except _socket.timeout:
            return False, "Timeout al conectar. Verifica que PhoneMic esté activo."
        except Exception as e:
            return False, f"Error de conexión: {e}"

        cb("Abriendo dispositivo de audio...")
        try:
            self.stream = sd.RawOutputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                device=device_index,
                blocksize=CHUNK,
            )
            self.stream.start()  # type: ignore[union-attr]
        except Exception as e:
            self.sock.close()  # type: ignore[union-attr]
            self.sock = None
            return False, f"Error dispositivo de audio: {e}"

        self.is_running = True
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()  # type: ignore[union-attr]
        return True, "Transmitiendo"

    def _receive_loop(self):
        bytes_received = 0
        try:
            while self.is_running and self.sock is not None:
                data = self.sock.recv(CHUNK)  # type: ignore[union-attr]
                if not data:
                    break
                bytes_received += len(data)
                stream = self.stream
                if stream is not None and stream.active:
                    if self.muted:
                        stream.write(b"\x00" * len(data))
                    else:
                        stream.write(_scale_volume(data, self.volume))
        except Exception:
            pass
        finally:
            self.is_running = False
            self._no_data = (bytes_received == 0)

    def stop(self):
        self.is_running = False
        if self.sock:
            try:
                self.sock.close()  # type: ignore[union-attr]
            except Exception:
                pass
        if self.stream:
            try:
                self.stream.stop()   # type: ignore[union-attr]
                self.stream.close()  # type: ignore[union-attr]
            except Exception:
                pass
        self.stream  = None
        self.sock    = None
        if self.connection_mode == "usb":
            self.remove_adb_forward()

    def cleanup(self):
        self.stop()


# ── Tkinter GUI ──────────────────────────────────────────────────────────────

# ── Esfera de estado (mic indicator) ─────────────────────────────────────────
def _darken(hex_color: str, factor: float = 0.55) -> str:
    """Returns a scaled version of a hex color (factor <1 darkens, >1 lightens)."""
    h = hex_color.lstrip("#")
    rv = int(h[0:2], 16); gv = int(h[2:4], 16); bv = int(h[4:6], 16)  # type: ignore[misc]
    rv = min(255, int(rv * factor))
    gv = min(255, int(gv * factor))
    bv = min(255, int(bv * factor))
    return f"#{rv:02x}{gv:02x}{bv:02x}"


class MicSphere(tk.Canvas):
    """Esfera de micrófono coloreada con icono de mic."""
    _R = 30   # radio — más pequeño que antes

    def __init__(self, parent, **kw):
        s = self._R * 2 + 12
        kw.setdefault("width", s); kw.setdefault("height", s)
        kw.setdefault("bg", BG_DARK)
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        super().__init__(parent, **kw)
        self._color = CLR_GRAY
        self.bind("<Configure>", lambda _: self._redraw())
        self.after(30, self._redraw)   # type: ignore[arg-type]  # forzar dibujo tras mapeo

    def set_color(self, color: str):
        self._color = color
        self._redraw()

    def _redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            self.after(30, self._redraw)   # type: ignore[arg-type]
            return
        cx, cy, r = w // 2, h // 2, self._R
        c = self._color

        # Sombra (color sólido más oscuro, sin alpha)
        sd = _darken(c, 0.4)
        self.create_oval(cx-r+3, cy-r+5, cx+r+3, cy+r+5, fill=sd, outline="")
        # Esfera principal
        self.create_oval(cx-r, cy-r, cx+r, cy+r, fill=c, outline="")
        # Brillo superior-izquierdo (color más claro sólido)
        shine_size = max(5, r // 4)
        self.create_oval(cx-r+5, cy-r+4, cx-r+5+shine_size, cy-r+4+shine_size,
                         fill=_darken(c, 1.8) if c != CLR_GRAY else "#707880", outline="")
        # Icono de micrófono (blanco)
        mx, my = cx, cy
        self.create_oval(mx-5, my-10, mx+5, my+2, fill="white", outline="")
        self.create_arc(mx-8, my-2, mx+8, my+10,
                        start=0, extent=-180, outline="white", style="arc", width=2)
        self.create_line(mx, my+10, mx, my+15, fill="white", width=2)
        self.create_line(mx-4, my+15, mx+4, my+15, fill="white", width=2)


# Slider estilo pill (imagen referencia) ──────────────────────────────────────
class IPhoneSlider(tk.Canvas):
    """Slider pill: contenedor negro redondeado + fill verde + pulgar blanco."""

    _PILL_H  = 28   # alto del contenedor pill exterior
    _TRACK_H = 4    # alto de la línea de progreso interior
    _THUMB_R = 10   # radio del pulgar (más pequeño)
    _PAD     = 16

    def __init__(self, parent, from_: float = 0, to: float = 100,
                 command=None, **kw):
        kw.setdefault("height", self._PILL_H + 8)
        kw.setdefault("bg", BG_DARK)
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        super().__init__(parent, **kw)
        self._from     = float(from_)
        self._to       = float(to)
        self._value    = float(to)
        self._command  = command
        self._disabled = False
        self.bind("<Configure>",      lambda _e: self._redraw())
        self.bind("<ButtonPress-1>",  self._on_mouse)
        self.bind("<B1-Motion>",      self._on_mouse)

    # ── drawing ──────────────────────────────────────────────────────────────

    def _pill(self, x1, y1, x2, y2, r, **kw):
        pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r,
               x2,y2-r, x2,y2, x2-r,y2, x1+r,y2,
               x1,y2, x1,y2-r, x1,y1+r, x1,y1]
        self.create_polygon(pts, smooth=True, **kw)

    def _redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 4:
            return

        cy   = h // 2
        PH   = self._PILL_H
        TH   = self._TRACK_H
        TR   = self._THUMB_R
        PAD  = self._PAD

        # Outer pill container (negro)
        self._pill(0, cy - PH//2, w, cy + PH//2, PH//2, fill="#111214", outline="")

        tx1 = PAD
        tx2 = w - PAD
        ratio = max(0.0, min(1.0,
            (self._value - self._from) / max(self._to - self._from, 1)))
        fx = tx1 + ratio * (tx2 - tx1)

        # Inner track background
        self._pill(tx1, cy - TH//2, tx2, cy + TH//2, TH//2,
                   fill="#2a2d35", outline="")

        # Fill (morado cuando activo, gris cuando disabled)
        if fx > tx1:
            fc = "#4a4f58" if self._disabled else CLR_BLUE
            self._pill(tx1, cy - TH//2, max(float(tx1 + TH), fx), cy + TH//2,
                       TH//2, fill=fc, outline="")

        # Thumb (sin alpha — sombra sólida oscura)
        cx_t = min(fx, float(tx2))   # asegurar que no salga del borde
        if not self._disabled:
            self.create_oval(cx_t-TR+2, cy-TR+3, cx_t+TR+2, cy+TR+3, fill="#0a0b0d", outline="")
        tc = "#666" if self._disabled else "#ffffff"
        self.create_oval(cx_t-TR, cy-TR, cx_t+TR, cy+TR, fill=tc, outline="")

    # ── interaction ──────────────────────────────────────────────────────────

    def _on_mouse(self, event):
        if self._disabled:
            return
        tx1 = self._PAD
        tx2 = self.winfo_width() - self._PAD
        ratio = max(0.0, min(1.0, (event.x - tx1) / max(tx2 - tx1, 1)))
        self._value = self._from + ratio * (self._to - self._from)
        self._redraw()
        if self._command:
            self._command(str(self._value))

    # ── public API (compatible con tk.Scale) ─────────────────────────────────

    def set(self, value: float):
        self._value = max(self._from, min(self._to, float(value)))
        self._redraw()

    def get(self) -> float:
        return self._value

    def config(self, **kw):          # type: ignore[override]
        if "state" in kw:
            self._disabled = (kw.pop("state") == "disabled")
            self._redraw()
        if kw:
            super().config(**kw)


def _btn(parent, text, command, bg, fg="#ffffff", width=18, height=2, font_size=12):
    return tk.Button(
        parent, text=text, command=command,
        width=width, height=height,
        font=("Segoe UI", font_size, "bold"),
        bg=bg, fg=fg,
        activebackground=bg, activeforeground=fg,
        relief="flat", cursor="hand2", bd=0,
    )


TITLEBAR_H    = 32
TITLEBAR_BG   = "#0f1012"
RESIZE_MARGIN = 6
WIN_MIN_W     = 480
WIN_MIN_H     = 680


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PhoneMic")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_DARK)
        self.root.overrideredirect(True)   # quita barra del OS
        self._set_window_icon()

        # Centrar en pantalla
        W, H = 500, 722
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        # Drag / resize / maximize state
        self._drag_dx: int = 0
        self._drag_dy: int = 0
        self._resize_dir: str = ""
        self._rs_x: int = 0
        self._rs_y: int = 0
        self._rs_geo: tuple = (0, 0, 500, 722)
        self._maximized: bool = False
        self._pre_max_geo: Optional[tuple] = None

        self.client  = PhoneMicClient()
        self.devices = self.client.get_output_devices()
        self._tray: pystray.Icon

        # Declare widget attributes (assigned inside _build_ui)
        self.device_var: tk.StringVar
        self.combo: ttk.Combobox
        self.btn_connect: tk.Button
        self.btn_mute: tk.Button
        self.lbl_vol: tk.Label
        self.scale_vol: IPhoneSlider
        self.indicator: tk.Label
        self.status_var: tk.StringVar
        self.mode_var:    tk.StringVar
        self.wifi_ip_var: tk.StringVar
        self.wifi_frame:  tk.Frame
        self.wifi_entry:  tk.Entry
        self.mic_sphere:  MicSphere
        self._connecting: bool = False
        self._connect_timeout: Optional[str] = None

        self._build_titlebar()
        self._build_ui()
        self._build_menu()
        self._load_config()
        self._bind_resize()

    # ── Custom title bar ─────────────────────────────────────────────────────

    def _build_titlebar(self):
        tb = tk.Frame(self.root, bg=TITLEBAR_BG, height=TITLEBAR_H)
        tb.pack(fill="x")
        tb.pack_propagate(False)

        # Dragging
        tb.bind("<ButtonPress-1>", self._tb_press)
        tb.bind("<B1-Motion>",     self._tb_motion)

        # Título
        lbl = tk.Label(tb, text="  PhoneMic",
                       font=("Segoe UI", 10), fg="#b5bac1", bg=TITLEBAR_BG, cursor="fleur")
        lbl.pack(side="left")
        lbl.bind("<ButtonPress-1>", self._tb_press)
        lbl.bind("<B1-Motion>",     self._tb_motion)

        # Botón cerrar
        def _on_close_enter(e: tk.Event) -> None:  # type: ignore[type-arg]
            btn_close.config(bg="#c42b1c", fg="#ffffff")
        def _on_close_leave(e: tk.Event) -> None:  # type: ignore[type-arg]
            btn_close.config(bg=TITLEBAR_BG, fg="#b5bac1")
        btn_close = tk.Button(
            tb, text="✕", command=self.on_close,
            font=("Segoe UI", 11), fg="#b5bac1", bg=TITLEBAR_BG,
            activebackground="#c42b1c", activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", width=4,
        )
        btn_close.pack(side="right")
        btn_close.bind("<Enter>", _on_close_enter)
        btn_close.bind("<Leave>", _on_close_leave)

        # Botón maximizar / restaurar
        self._btn_max = tk.Button(
            tb, text="□", command=self._toggle_maximize,
            font=("Segoe UI", 11), fg="#b5bac1", bg=TITLEBAR_BG,
            activebackground="#3a3d47", activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", width=4,
        )
        self._btn_max.pack(side="right")
        self._btn_max.bind("<Enter>", lambda e: self._btn_max.config(bg="#3a3d47"))
        self._btn_max.bind("<Leave>", lambda e: self._btn_max.config(bg=TITLEBAR_BG))

        # Botón minimizar
        btn_min = tk.Button(
            tb, text="─", command=self._minimize_window,
            font=("Segoe UI", 11), fg="#b5bac1", bg=TITLEBAR_BG,
            activebackground="#3a3d47", activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", width=4,
        )
        btn_min.pack(side="right")
        btn_min.bind("<Enter>", lambda e: btn_min.config(bg="#3a3d47"))
        btn_min.bind("<Leave>", lambda e: btn_min.config(bg=TITLEBAR_BG))

        # Doble clic en la barra = maximizar/restaurar
        tb.bind("<Double-Button-1>",  lambda e: self._toggle_maximize())
        lbl.bind("<Double-Button-1>", lambda e: self._toggle_maximize())

    def _tb_press(self, e: tk.Event) -> None:  # type: ignore[type-arg]
        self._drag_dx = e.x_root - self.root.winfo_x()
        self._drag_dy = e.y_root - self.root.winfo_y()

    def _tb_motion(self, e: tk.Event) -> None:  # type: ignore[type-arg]
        if self._resize_dir:   # resize tiene prioridad
            return
        self.root.geometry(f"+{e.x_root - self._drag_dx}+{e.y_root - self._drag_dy}")

    def _minimize_window(self):
        """Minimiza a la barra de tareas (con overrideredirect se necesita quitar el flag momentáneamente)."""
        self.root.overrideredirect(False)
        self.root.iconify()

    def _on_map(self, e: tk.Event) -> None:  # type: ignore[type-arg]
        """Se dispara cuando la ventana vuelve a ser visible (restaurada desde taskbar)."""
        if e.widget is self.root and self.root.state() == "normal":
            self.root.overrideredirect(True)

    def _toggle_maximize(self):
        if self._maximized:
            self._maximized = False
            self._btn_max.config(text="□")
            if self._pre_max_geo:
                ox, oy, ow, oh = self._pre_max_geo
                self.root.geometry(f"{ow}x{oh}+{ox}+{oy}")
        else:
            self._maximized = True
            self._btn_max.config(text="❐")
            self._pre_max_geo = (
                self.root.winfo_x(), self.root.winfo_y(),
                self.root.winfo_width(), self.root.winfo_height(),
            )
            try:
                import ctypes
                class _RECT(ctypes.Structure):
                    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
                rc = _RECT()
                ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rc), 0)  # type: ignore[attr-defined]
                self.root.geometry(f"{rc.right - rc.left}x{rc.bottom - rc.top}+{rc.left}+{rc.top}")
            except Exception:
                sw = self.root.winfo_screenwidth()
                sh = self.root.winfo_screenheight()
                self.root.geometry(f"{sw}x{sh}+0+0")

    # ── Resize (bordes) ──────────────────────────────────────────────────────

    def _bind_resize(self):
        self.root.bind("<Motion>",          self._on_resize_motion)
        self.root.bind("<ButtonPress-1>",   self._on_resize_press,  add="+")
        self.root.bind("<B1-Motion>",       self._on_resize_drag,   add="+")
        self.root.bind("<ButtonRelease-1>", lambda _: setattr(self, "_resize_dir", ""), add="+")
        self.root.bind("<Map>",             self._on_map)

    def _resize_zone(self, x: int, y: int) -> str:
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        m = RESIZE_MARGIN
        top    = y < m
        bottom = y > h - m
        left_  = x < m
        right_ = x > w - m
        if top    and left_:  return "nw"
        if top    and right_: return "ne"
        if bottom and left_:  return "sw"
        if bottom and right_: return "se"
        if top:    return "n"
        if bottom: return "s"
        if left_:  return "w"
        if right_: return "e"
        return ""

    def _on_resize_motion(self, e: tk.Event) -> None:  # type: ignore[type-arg]
        cursors = {
            "n": "top_side",    "s": "bottom_side",
            "e": "right_side",  "w": "left_side",
            "ne": "top_right_corner",  "nw": "top_left_corner",
            "se": "bottom_right_corner", "sw": "bottom_left_corner",
        }
        self.root.config(cursor=cursors.get(self._resize_zone(e.x, e.y), ""))

    def _on_resize_press(self, e: tk.Event) -> None:  # type: ignore[type-arg]
        zone = self._resize_zone(e.x, e.y)
        self._resize_dir = zone
        if zone:
            self._rs_x   = e.x_root
            self._rs_y   = e.y_root
            self._rs_geo = (self.root.winfo_x(), self.root.winfo_y(),
                            self.root.winfo_width(), self.root.winfo_height())

    def _on_resize_drag(self, e: tk.Event) -> None:  # type: ignore[type-arg]
        if not self._resize_dir:
            return
        dx = e.x_root - self._rs_x
        dy = e.y_root - self._rs_y
        ox, oy, ow, oh = self._rs_geo
        d = self._resize_dir
        x, y, w, h = ox, oy, ow, oh
        if "e" in d: w = max(WIN_MIN_W, ow + dx)
        if "s" in d: h = max(WIN_MIN_H, oh + dy)
        if "w" in d:
            w = max(WIN_MIN_W, ow - dx)
            x = ox + ow - w
        if "n" in d:
            h = max(WIN_MIN_H, oh - dy)
            y = oy + oh - h
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=BG_DARK)
        hdr.pack(fill="x", padx=28, pady=(24, 0))

        tk.Label(
            hdr, text="PhoneMic",
            font=("Segoe UI", 26, "bold"),
            fg=CLR_TEXT, bg=BG_DARK,
        ).pack(anchor="w")

        tk.Label(
            hdr, text="Micrófono del celular por USB ADB",
            font=("Segoe UI", 11),
            fg=CLR_MUTED, bg=BG_DARK,
        ).pack(anchor="w", pady=(2, 0))

        # ── Mic sphere ──────────────────────────────────────────────────────
        self.mic_sphere = MicSphere(self.root)
        self.mic_sphere.pack(pady=(12, 0))

        # ── Divider ─────────────────────────────────────────────────────────
        tk.Frame(self.root, bg=BG_PANEL, height=1).pack(fill="x", padx=28, pady=14)

        # ── Connection mode ──────────────────────────────────────────────────
        mode_frame = tk.Frame(self.root, bg=BG_DARK)
        mode_frame.pack(fill="x", padx=28, pady=(0, 10))

        tk.Label(
            mode_frame, text="Modo de conexión",
            font=("Segoe UI", 10), fg=CLR_SUB, bg=BG_DARK,
        ).pack(anchor="w", pady=(0, 6))

        radio_row = tk.Frame(mode_frame, bg=BG_DARK)
        radio_row.pack(fill="x")

        self.mode_var = tk.StringVar(value="usb")

        for val, label in (("usb", "USB  (ADB)"), ("wifi", "WiFi  (red local)")):
            tk.Radiobutton(
                radio_row, text=label, variable=self.mode_var, value=val,
                command=self._on_mode_change,
                bg=BG_DARK, fg=CLR_TEXT, activebackground=BG_DARK,
                activeforeground=CLR_TEXT, selectcolor=BG_PANEL,
                font=("Segoe UI", 10), indicatoron=True,
                highlightthickness=0, bd=0, cursor="hand2",
            ).pack(side="left", padx=(0, 20))

        self.wifi_frame = tk.Frame(mode_frame, bg=BG_DARK)
        self.wifi_frame.pack(fill="x", pady=(8, 0))

        tk.Label(
            self.wifi_frame, text="IP del celular",
            font=("Segoe UI", 10), fg=CLR_SUB, bg=BG_DARK,
        ).pack(side="left", padx=(0, 8))

        self.wifi_ip_var = tk.StringVar()
        self.wifi_entry = tk.Entry(
            self.wifi_frame, textvariable=self.wifi_ip_var,
            width=18, font=("Segoe UI", 10),
            bg=BG_PANEL, fg=CLR_TEXT, insertbackground=CLR_TEXT,
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground="#3a3d47",
            highlightcolor=CLR_BLUE,
        )
        self.wifi_entry.pack(side="left", ipady=5)

        tk.Label(
            self.wifi_frame, text=":7777",
            font=("Segoe UI", 10), fg=CLR_MUTED, bg=BG_DARK,
        ).pack(side="left", padx=(4, 0))

        self.wifi_frame.pack_forget()  # hidden by default (USB mode)

        tk.Frame(self.root, bg=BG_PANEL, height=1).pack(fill="x", padx=28, pady=(10, 14))

        # ── Output device selector ───────────────────────────────────────────
        dev_frame = tk.Frame(self.root, bg=BG_DARK)
        dev_frame.pack(fill="x", padx=28)

        tk.Label(
            dev_frame, text="Dispositivo de salida",
            font=("Segoe UI", 10), fg=CLR_SUB, bg=BG_DARK,
        ).pack(anchor="w", pady=(0, 4))

        # Forzar colores oscuros en el listbox del dropdown (nivel Tk, no ttk)
        self.root.option_add("*TCombobox*Listbox.background",       BG_PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground",       CLR_TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", CLR_BLUE)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.root.option_add("*TCombobox*Listbox.font",             ("Segoe UI", 10))
        self.root.option_add("*TCombobox*Listbox.relief",           "flat")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Discord.TCombobox",
            fieldbackground=BG_PANEL,
            background=BG_PANEL,
            foreground=CLR_TEXT,
            selectbackground=BG_PANEL,
            selectforeground=CLR_TEXT,
            arrowcolor=CLR_MUTED,
            bordercolor="#3a3d47",
            darkcolor=BG_PANEL,
            lightcolor=BG_PANEL,
            padding=(10, 7),
        )
        style.map("Discord.TCombobox",
            fieldbackground=[("readonly", BG_PANEL), ("disabled", BG_DARK)],
            foreground=[("readonly", CLR_TEXT), ("disabled", CLR_MUTED)],
            selectbackground=[("readonly", BG_PANEL)],
            selectforeground=[("readonly", CLR_TEXT)],
            bordercolor=[("focus", CLR_BLUE), ("!focus", "#3a3d47")],
        )

        self.device_var = tk.StringVar()
        self.combo = ttk.Combobox(
            dev_frame, textvariable=self.device_var,
            values=[f"[{i}] {name}" for i, name in self.devices],
            state="readonly", width=52,
            style="Discord.TCombobox",
        )
        preferred = self.client.find_virtual_device_index(self.devices)
        if self.devices:
            self.combo.current(preferred)
        self.combo.pack(fill="x")

        if self.client.is_vbcable_available(self.devices):
            hint_text = "✓ VB-Cable detectado  •  En Discord/Zoom/OBS selecciona \"CABLE Output\" como micrófono"
            hint_color = CLR_GREEN
        else:
            hint_text = "Sin micrófono virtual — instala VB-Cable para usarlo en Discord/Zoom/OBS"
            hint_color = CLR_MUTED

        tk.Label(
            dev_frame,
            text=hint_text,
            font=("Segoe UI", 9), fg=hint_color, bg=BG_DARK, wraplength=420,
        ).pack(anchor="w", pady=(4, 0))

        # ── Connect button ───────────────────────────────────────────────────
        self.btn_connect = _btn(
            self.root, "Conectar", self.toggle,
            bg=CLR_BLUE, width=22, height=2, font_size=13,
        )
        self.btn_connect.pack(pady=18)

        # ── Divider ─────────────────────────────────────────────────────────
        tk.Frame(self.root, bg=BG_PANEL, height=1).pack(fill="x", padx=28)

        # ── Mute + Volume row ────────────────────────────────────────────────
        ctrl = tk.Frame(self.root, bg=BG_DARK)
        ctrl.pack(fill="x", padx=28, pady=14)

        self.btn_mute = _btn(
            ctrl, "🎤  Silenciar", self._toggle_mute,
            bg=CLR_BLUE, width=14, height=1, font_size=10,
        )
        self.btn_mute.config(state="disabled")
        self.btn_mute.pack(side="left")

        vol_frame = tk.Frame(ctrl, bg=BG_DARK)
        vol_frame.pack(side="right", fill="x", expand=True, padx=(16, 0))

        vol_hdr = tk.Frame(vol_frame, bg=BG_DARK)
        vol_hdr.pack(fill="x")

        tk.Label(
            vol_hdr, text="🔊  Volumen",
            font=("Segoe UI", 10), fg=CLR_SUB, bg=BG_DARK,
        ).pack(side="left")

        self.lbl_vol = tk.Label(
            vol_hdr, text="100%",
            font=("Segoe UI", 10), fg=CLR_SUB, bg=BG_DARK,
        )
        self.lbl_vol.pack(side="right")

        self.scale_vol = IPhoneSlider(
            vol_frame, from_=0, to=100, command=self._on_volume,
        )
        self.scale_vol.set(100)
        self.scale_vol.config(state="disabled")
        self.scale_vol.pack(fill="x", pady=(6, 0))

        # ── Divider ─────────────────────────────────────────────────────────
        tk.Frame(self.root, bg=BG_PANEL, height=1).pack(fill="x", padx=28)

        # ── Status bar ───────────────────────────────────────────────────────
        status_frame = tk.Frame(self.root, bg=BG_DARK)
        status_frame.pack(fill="x", padx=28, pady=12)

        self.indicator = tk.Label(
            status_frame, text="●",
            font=("Segoe UI", 16), fg=CLR_GRAY, bg=BG_DARK,
        )
        self.indicator.pack(side="left")

        self.status_var = tk.StringVar(
            value="Conecta el celular por USB con depuración USB habilitada"
        )
        tk.Label(
            status_frame, textvariable=self.status_var,
            font=("Segoe UI", 10), fg=CLR_MUTED, bg=BG_DARK,
            wraplength=400, justify="left",
        ).pack(side="left", padx=(6, 0))

    def _build_menu(self):
        pass  # menú eliminado

    # ── Actions ─────────────────────────────────────────────────────────────

    def _on_mode_change(self):
        if self.mode_var.get() == "wifi":
            self.wifi_frame.pack(fill="x", pady=(8, 0))
        else:
            self.wifi_frame.pack_forget()

    def toggle(self):
        if self._connecting:
            return
        if self.client.is_running:
            self._disconnect()
        else:
            self._connect()

    def _show_dark_popup(self, title: str, msg: str):
        """Muestra un diálogo de error con estilo oscuro."""
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg=BG_PANEL)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        # Icono de la app (quita la pluma de tkinter)
        try:
            ico = self._icon_path("ico")
            if os.path.exists(ico):
                win.iconbitmap(ico)
        except Exception:
            pass
        # Barra oscura
        try:
            user32 = ctypes.windll.user32   # type: ignore[attr-defined]
            dwmapi = ctypes.windll.dwmapi   # type: ignore[attr-defined]
            win.update_idletasks()
            hwnd = user32.GetAncestor(win.winfo_id(), 2)
            val1 = ctypes.c_int(1); sz = ctypes.sizeof(ctypes.c_int)
            dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(val1), sz)
            dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val1), sz)
        except Exception:
            pass
        tk.Label(
            win, text=title, font=("Segoe UI", 12, "bold"),
            fg=CLR_TEXT, bg=BG_PANEL, padx=20, pady=12,
        ).pack()
        tk.Label(
            win, text=msg, font=("Segoe UI", 10),
            fg=CLR_SUB, bg=BG_PANEL, wraplength=340, justify="center",
            padx=20, pady=8,
        ).pack()
        tk.Button(
            win, text="OK", command=win.destroy,
            font=("Segoe UI", 10, "bold"),
            bg=CLR_BLUE, fg="#ffffff", activebackground=CLR_BLUE,
            activeforeground="#ffffff", relief="flat", cursor="hand2",
            width=10, height=1, bd=0,
        ).pack(pady=(0, 16))
        win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")

    def _connect(self):
        if self._connecting:
            return
        if not self.devices:
            self._show_dark_popup("Sin audio", "No hay dispositivos de audio disponibles.")
            return
        self._connecting = True
        dev_idx = self.devices[self.combo.current()][0]
        self.btn_connect.config(state="disabled", text="Conectando...")
        self.combo.config(state="disabled")

        self.client.connection_mode = self.mode_var.get()
        self.client.wifi_ip = self.wifi_ip_var.get()
        self._save_config()

        # Timeout: si en 10 s no hay resultado, mostrar error
        def _timeout():
            self._on_connect_result(False, "Tiempo de espera agotado (10 s).\n¿Está PhoneMic activo en el celular?")
        self._connect_timeout = self.root.after(10_000, _timeout)  # type: ignore[arg-type]

        def do_connect():
            ok, msg = self.client.start(dev_idx, status_callback=self._set_status)
            self.root.after(0, lambda: self._on_connect_result(ok, msg))  # type: ignore[arg-type]

        threading.Thread(target=do_connect, daemon=True).start()

    def _on_connect_result(self, ok: bool, msg: str):
        if not self._connecting:
            return   # ya fue resuelto (timeout llegó después de éxito o viceversa)
        self._connecting = False
        if self._connect_timeout is not None:
            self.root.after_cancel(self._connect_timeout)  # type: ignore[arg-type]
            self._connect_timeout = None
        if ok:
            self.btn_connect.config(
                text="Desconectar", bg=CLR_RED,
                activebackground=CLR_RED, state="normal",
            )
            self.btn_mute.config(state="normal")
            self.scale_vol.config(state="normal")
            self.status_var.set("Transmitiendo audio del micrófono del celular")
            self._set_indicator(CLR_GREEN)
            self._pulse_check()
        else:
            self.client.stop()
            self.btn_connect.config(text="Conectar", bg=CLR_BLUE, state="normal")
            self.combo.config(state="readonly")
            self._set_status(f"Error: {msg}")
            self._set_indicator(CLR_GRAY)
            self._show_dark_popup("Error al conectar", msg)

    def _disconnect(self):
        self._connecting = False
        self.client.stop()
        self.btn_connect.config(text="Conectar", bg=CLR_BLUE, state="normal")
        self.btn_mute.config(text="🎤  Silenciar", bg=CLR_BLUE, state="disabled")
        self.scale_vol.config(state="disabled")
        self.combo.config(state="readonly")
        self.client.muted = False
        self._set_status("Desconectado.")
        self._set_indicator(CLR_GRAY)

    def _toggle_mute(self):
        self.client.muted = not self.client.muted
        if self.client.muted:
            self.btn_mute.config(text="🔇  Activar mic", bg=CLR_RED, activebackground=CLR_RED)
            self._set_indicator(CLR_RED)
            self._set_status("Silenciado")
        else:
            self.btn_mute.config(text="🎤  Silenciar", bg=CLR_BLUE, activebackground=CLR_BLUE)
            self._set_indicator(CLR_GREEN)
            self._set_status("Transmitiendo audio del micrófono del celular")

    def _on_volume(self, val: str):
        v = int(float(val))
        self.client.volume = v / 100.0
        self.lbl_vol.config(text=f"{v}%")

    def _pulse_check(self):
        if self.client.is_running:
            self.root.after(1000, self._pulse_check)
        else:
            self.btn_connect.config(text="Conectar", bg=CLR_BLUE)
            self.btn_mute.config(text="🎤  Silenciar", bg=CLR_BLUE, state="disabled")
            self.scale_vol.config(state="disabled")
            self.combo.config(state="readonly")
            self.client.muted = False
            no_data = getattr(self.client, "_no_data", False)
            if no_data:
                msg = ("PhoneMic no está iniciado en el celular.\n\n"
                       "Abre la app y toca «Iniciar» antes de conectar.")
                self._set_status("App no iniciada en el celular.")
                self._show_dark_popup("App no iniciada", msg)
            else:
                self._set_status("Conexión perdida. ¿Se desconectó el celular?")
            self._set_indicator(CLR_RED)

    def _set_status(self, msg: str):
        self.root.after(0, self.status_var.set, msg)

    def _set_indicator(self, color: str):
        def _upd(**_) -> object:
            self.indicator.config(fg=color)
            self.mic_sphere.set_color(color)
            return None
        self.root.after(0, _upd)  # type: ignore[arg-type]

    # ── Dark titlebar ────────────────────────────────────────────────────────

    def _apply_dark_titlebar(self):
        try:
            user32  = ctypes.windll.user32   # type: ignore[attr-defined]
            dwmapi  = ctypes.windll.dwmapi   # type: ignore[attr-defined]
            # winfo_id() devuelve el HWND del área cliente interna de tkinter.
            # GetAncestor(..., GA_ROOT=2) sube al frame exterior que tiene la
            # barra de título real (la que muestra la X y el ─).
            inner = self.root.winfo_id()
            hwnd  = user32.GetAncestor(inner, 2)
            val1  = ctypes.c_int(1)
            sz    = ctypes.sizeof(ctypes.c_int)
            # Atributo 19: dark mode builds anteriores a Win10 20H1
            dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(val1), sz)
            # Atributo 20: dark mode Win10 20H1+ y Win11
            dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val1), sz)
            # Atributo 35: color de caption (negro) — sólo Win11, ignorado en Win10
            black = ctypes.c_int(0x00000000)
            dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(black), sz)
        except Exception:
            pass

    # ── Window / tray icon ───────────────────────────────────────────────────

    @staticmethod
    def _icon_path(ext: str) -> str:
        base = (os.path.dirname(sys.executable)
                if getattr(sys, "frozen", False)
                else os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, f"phonemic.{ext}")

    def _set_window_icon(self):
        try:
            ico = self._icon_path("ico")
            if os.path.exists(ico):
                self.root.iconbitmap(ico)
        except Exception:
            pass

    def _make_tray_icon(self) -> Image.Image:  # type: ignore[override]
        try:
            png = self._icon_path("png")
            if os.path.exists(png):
                return Image.open(png).resize((64, 64)).convert("RGBA")
        except Exception:
            pass
        # fallback: draw a simple mic icon
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, size - 4, size - 4], fill="#23a55a")
        draw.ellipse([22, 14, 42, 38], fill="white")
        draw.rectangle([28, 38, 36, 46], fill="white")
        draw.rectangle([22, 46, 42, 50], fill="white")
        return img

    # ── Config persistence ───────────────────────────────────────────────────

    @staticmethod
    def _config_path() -> str:
        app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
        folder = os.path.join(app_data, "PhoneMic")
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, "config.json")

    def _load_config(self):
        try:
            with open(self._config_path(), "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if "wifi_ip" in cfg:
                self.wifi_ip_var.set(cfg["wifi_ip"])
            if cfg.get("mode") == "wifi":
                self.mode_var.set("wifi")
                self._on_mode_change()
        except Exception:
            pass

    def _save_config(self):
        try:
            cfg = {"wifi_ip": self.wifi_ip_var.get(), "mode": self.mode_var.get()}
            with open(self._config_path(), "w", encoding="utf-8") as f:
                json.dump(cfg, f)
        except Exception:
            pass

    # ── System tray ─────────────────────────────────────────────────────────

    def _setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Abrir PhoneMic", self._show_window, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", self._quit_app),
        )
        self._tray = pystray.Icon(
            "PhoneMic", self._make_tray_icon(), "PhoneMic", menu
        )
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _show_window(self, icon=None, item=None):
        def _do():
            self.root.overrideredirect(True)
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        self.root.after(0, _do)  # type: ignore[arg-type]

    def _quit_app(self, icon=None, item=None):
        self._tray.stop()
        self.client.cleanup()
        self.root.after(0, lambda: self.root.destroy())    # type: ignore[arg-type]

    def on_close(self):
        self.root.withdraw()  # ocultar en vez de cerrar

    def on_close_real(self):
        self._quit_app()


def _acquire_single_instance_lock():
    """Bind a local socket as a mutex. Returns the socket or None if already running."""
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 0)
        s.bind(("127.0.0.1", 19847))
        s.listen(1)
        return s
    except OSError:
        return None


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    _lock = _acquire_single_instance_lock()
    if _lock is None:
        try:
            ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
                0, "PhoneMic ya está abierto.", "PhoneMic", 0x40
            )
        except Exception:
            pass
        sys.exit(0)

    root = tk.Tk()
    app = App(root)
    app._setup_tray()
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
