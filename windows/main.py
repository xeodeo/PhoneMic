"""PhoneMic – Entry point (PySide6)."""
from __future__ import annotations

import ctypes
import multiprocessing
import socket as _socket
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt


def _acquire_lock():
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 0)
        s.bind(("127.0.0.1", 19847))
        s.listen(1)
        return s
    except OSError:
        return None


if __name__ == "__main__":
    multiprocessing.freeze_support()

    lock = _acquire_lock()
    if lock is None:
        try:
            ctypes.windll.user32.MessageBoxW(0, "PhoneMic ya está abierto.", "PhoneMic", 0x40)
        except Exception:
            pass
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    from phonemic.ui.app import App
    window = App()
    window.show()

    sys.exit(app.exec())
