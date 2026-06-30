"""PhoneMic – Entry point (PySide6)."""
from __future__ import annotations

import ctypes
import multiprocessing
import os
import socket as _socket
import sys

# When frozen by PyInstaller, register PySide6 and shiboken6 dirs so
# Windows can find Qt DLLs and shiboken6.abi3.dll before Qt is imported.
if getattr(sys, "frozen", False) and hasattr(os, "add_dll_directory"):
    _base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    _exe_dir = os.path.dirname(sys.executable)
    for _subdir in ("PySide6", "shiboken6"):
        for _parent in (_base, os.path.join(_exe_dir, "_internal")):
            _p = os.path.join(_parent, _subdir)
            if os.path.isdir(_p):
                os.add_dll_directory(_p)
                break

def _acquire_lock():
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 0)
        s.bind(("127.0.0.1", 19847))
        s.listen(1)
        return s
    except OSError:
        return None


def _fatal(msg: str) -> None:
    import traceback
    _log = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "phonemic_error.log")
    try:
        with open(_log, "w", encoding="utf-8") as _f:
            _f.write(msg + "\n\n")
            traceback.print_exc(file=_f)
    except Exception:
        pass
    ctypes.windll.user32.MessageBoxW(0, f"{msg}\n\nLog: {_log}", "PhoneMic - Error", 0x10)


if __name__ == "__main__":
    multiprocessing.freeze_support()

    lock = _acquire_lock()
    if lock is None:
        try:
            ctypes.windll.user32.MessageBoxW(0, "PhoneMic ya está abierto.", "PhoneMic", 0x40)
        except Exception:
            pass
        sys.exit(0)

    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
    except Exception as _e:
        _fatal(f"Error cargando Qt: {_e}")
        sys.exit(1)

    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

        from phonemic.ui.app import App
        window = App()
        window.show()

        sys.exit(app.exec())
    except Exception as _e:
        _fatal(f"Error iniciando app: {_e}")
        sys.exit(1)
