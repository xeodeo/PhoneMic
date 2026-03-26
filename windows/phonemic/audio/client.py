"""PhoneMicClient: ADB management + TCP connection + audio streaming."""
import os
import socket as _socket
import subprocess
import sys
import threading
from typing import Optional, Callable

import sounddevice as sd  # type: ignore[import]

from ..constants import PORT, CHUNK, SAMPLE_RATE_LOW, SAMPLE_RATE_HIGH, CHANNELS
from .processing import scale_volume, noise_gate


def _find_adb() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        # __file__ is windows/phonemic/audio/client.py
        # go up 3 levels to get to windows/
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bundled = os.path.join(base, "adb.exe")
    return bundled if os.path.exists(bundled) else "adb"


ADB = _find_adb()
_CFLAGS = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW

# Protocol header: Android sends "PHONEMIC:SR:CH\n" before raw PCM
# SR = sample rate (int), CH = channels (int)
_HEADER_PREFIX = b"PHONEMIC:"
_HEADER_TIMEOUT = 1.5  # seconds to wait for header


class PhoneMicClient:
    def __init__(self) -> None:
        self.is_running: bool = False
        self.muted: bool = False
        self.volume: float = 1.0
        self.stream: Optional[sd.RawOutputStream] = None
        self.sock: Optional[_socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self.connection_mode: str = "usb"
        self.wifi_ip: str = ""
        self.high_quality: bool = False
        self.noise_gate_enabled: bool = False
        self.noise_gate_threshold: float = 0.02
        self._no_data: bool = False
        self._negotiated_rate: int = SAMPLE_RATE_LOW
        self._header_buf: bytes = b""

    # ── ADB ──────────────────────────────────────────────────────────────────

    def _adb_devices(self, timeout: int = 5):
        """Returns (authorized_lines, unauthorized_lines) from 'adb devices'."""
        r = subprocess.run(
            [ADB, "devices"], capture_output=True, text=True,
            timeout=timeout, creationflags=_CFLAGS,
        )
        auth, unauth = [], []
        for line in r.stdout.splitlines():
            if "\t" not in line:
                continue
            if "unauthorized" in line:
                unauth.append(line)
            elif "offline" not in line:
                auth.append(line)
        return auth, unauth

    def _restart_adb_server(self) -> None:
        """Kill and restart the ADB server to force re-auth on the phone."""
        for cmd in (["kill-server"], ["start-server"]):
            try:
                subprocess.run(
                    [ADB] + cmd, capture_output=True,
                    timeout=8, creationflags=_CFLAGS,
                )
            except Exception:
                pass

    def setup_adb_forward(self) -> tuple:
        try:
            auth, unauth = self._adb_devices()

            # Device present but not yet authorized → restart ADB server so the
            # phone shows the "Allow USB debugging?" dialog again.
            if unauth and not auth:
                self._restart_adb_server()
                import time; time.sleep(1.5)
                auth, unauth = self._adb_devices()
                if not auth:
                    return False, (
                        "El celular está conectado pero no autorizado.\n\n"
                        "• Desbloquea el celular\n"
                        "• Aparecerá un mensaje «¿Permitir depuración USB?» → toca Permitir\n"
                        "• Si no aparece: Ajustes → Opciones de desarrollador → "
                        "Revocar autorizaciones USB, luego vuelve a conectar"
                    )

            if not auth:
                return False, (
                    "No se detectó ningún celular por USB.\n\n"
                    "• Conecta el cable USB al PC\n"
                    "• En el celular: Ajustes → Opciones de desarrollador → Depuración USB (activar)\n"
                    "• Si aparece un aviso en el celular, toca «Permitir»"
                )

            result = subprocess.run(
                [ADB, "forward", f"tcp:{PORT}", f"tcp:{PORT}"],
                capture_output=True, text=True, timeout=5, creationflags=_CFLAGS,
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

    def remove_adb_forward(self) -> None:
        try:
            subprocess.run(
                [ADB, "forward", "--remove", f"tcp:{PORT}"],
                capture_output=True, timeout=3, creationflags=_CFLAGS,
            )
        except Exception:
            pass

    # ── Device listing ────────────────────────────────────────────────────────

    def get_output_devices(self) -> list:
        devices = []
        seen: set = set()
        for i, d in enumerate(sd.query_devices()):
            if d["max_output_channels"] > 0:
                name = d["name"]
                if name not in seen:
                    seen.add(name)
                    devices.append((i, name))
        return devices

    def find_virtual_device_index(self, devices: list) -> int:
        priority = ["cable input", "cable", "vb-audio", "voicemeeter", "vac", "virtual"]
        for kw in priority:
            for idx, (_, name) in enumerate(devices):
                if kw in name.lower():
                    return idx
        return 0

    def is_vbcable_available(self, devices: list) -> bool:
        return any("cable" in name.lower() for _, name in devices)

    # ── Connection ───────────────────────────────────────────────────────────

    def start(self, device_index: int, status_callback: Optional[Callable] = None) -> tuple:
        def cb(msg: str) -> None:
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

        # Leer primer chunk para detectar header de protocolo (sin bloquear indefinido)
        negotiated_rate = self._read_header(sock)
        self._negotiated_rate = negotiated_rate

        cb("Abriendo dispositivo de audio...")
        try:
            self.stream = sd.RawOutputStream(
                samplerate=negotiated_rate,
                channels=CHANNELS,
                dtype="int16",
                device=device_index,
                blocksize=0,   # dejar que PortAudio elija — evita excepciones con chunks variables
            )
            self.stream.start()  # type: ignore[union-attr]
        except Exception as e:
            self.sock.close()  # type: ignore[union-attr]
            self.sock = None
            return False, f"Error dispositivo de audio: {e}"

        self.is_running = True
        self._no_data = False
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()  # type: ignore[union-attr]
        return True, "Transmitiendo"

    def _read_header(self, sock: _socket.socket) -> int:
        """Lee el primer chunk y detecta header opcional 'PHONEMIC:SR:CH\\n'.
        El chunk completo (o el audio restante tras el header) queda en _header_buf
        para reproducirlo sin pérdida. Nunca bloquea más de 2 s."""
        default_rate = SAMPLE_RATE_HIGH if self.high_quality else SAMPLE_RATE_LOW
        try:
            sock.settimeout(2.0)
            first = sock.recv(CHUNK)
            sock.settimeout(None)
        except Exception:
            sock.settimeout(None)
            self._header_buf = b""
            return default_rate

        if not first:
            self._header_buf = b""
            return default_rate

        if first.startswith(_HEADER_PREFIX):
            nl = first.find(b"\n")
            if nl > 0:
                header_line = first[:nl].decode("ascii", errors="ignore")
                parts = header_line.split(":")
                if len(parts) >= 2 and parts[1].isdigit():
                    rate = int(parts[1])
                    if rate in (SAMPLE_RATE_LOW, SAMPLE_RATE_HIGH):
                        self._header_buf = first[nl + 1:]   # audio after header
                        return rate
            self._header_buf = first   # header parse failed, treat as audio
        else:
            self._header_buf = first   # no header, whole chunk is audio

        return default_rate

    # ── Jitter buffer (simple - para WiFi) ───────────────────────────────────

    def _get_jitter_prefill(self) -> int:
        """Number of chunks to buffer before playback (WiFi=4, USB=0)."""
        return 4 if self.connection_mode == "wifi" else 0

    # ── Receive loop ─────────────────────────────────────────────────────────

    def _receive_loop(self) -> None:
        bytes_received = 0
        jitter_buf: list = []
        prefill = self._get_jitter_prefill()
        header_leftover = getattr(self, "_header_buf", b"")

        try:
            while self.is_running and self.sock is not None:
                if header_leftover:
                    data = header_leftover
                    header_leftover = b""
                else:
                    data = self.sock.recv(CHUNK)  # type: ignore[union-attr]
                if not data:
                    break
                bytes_received += len(data)

                # Apply processing
                processed = data
                if self.noise_gate_enabled:
                    processed = noise_gate(processed, self.noise_gate_threshold)
                if self.muted:
                    processed = b"\x00" * len(processed)
                else:
                    processed = scale_volume(processed, self.volume)

                stream = self.stream
                if stream is None or not stream.active:
                    break

                # Jitter buffer for WiFi
                if prefill > 0:
                    jitter_buf.append(processed)
                    if len(jitter_buf) >= prefill:
                        for chunk in jitter_buf:
                            stream.write(chunk)
                        jitter_buf.clear()
                        prefill = 0
                else:
                    stream.write(processed)

        except Exception:
            pass
        finally:
            self.is_running = False
            self._no_data = (bytes_received == 0)

    # ── Stop / cleanup ────────────────────────────────────────────────────────

    def stop(self) -> None:
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
        self.stream = None
        self.sock = None
        if self.connection_mode == "usb":
            self.remove_adb_forward()

    def cleanup(self) -> None:
        self.stop()
