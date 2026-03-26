"""PySide6 custom widgets for PhoneMic."""
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QPen,
    QRadialGradient, QPainterPath, QFont,
)


class MicSphere(QWidget):
    """Large clickable microphone sphere with state-based colors and glow."""
    clicked = Signal()

    DISCONNECTED = "disconnected"
    CONNECTING   = "connecting"
    CONNECTED    = "connected"
    MUTED        = "muted"

    _STATE_COLORS = {
        DISCONNECTED: ("#2c2e33", None),
        CONNECTING:   ("#f59f00", None),
        CONNECTED:    ("#845ef7", (132, 94, 247, 55)),
        MUTED:        ("#5c1a1a", None),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = self.DISCONNECTED
        self.setFixedSize(140, 140)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_state(self, state: str):
        self._state = state
        interactive = state in (self.CONNECTED, self.MUTED)
        self.setCursor(Qt.CursorShape.PointingHandCursor if interactive
                       else Qt.CursorShape.ArrowCursor)
        self.update()

    def mousePressEvent(self, event):
        if self._state in (self.CONNECTED, self.MUTED):
            self.clicked.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h   = float(self.width()), float(self.height())
        cx, cy = w / 2.0, h / 2.0
        r      = 42.0   # sphere radius
        gr_max = w / 2.0  # glow reaches exactly the widget edge → perfect circle

        base_hex, glow_rgba = self._STATE_COLORS.get(
            self._state, ("#2c2e33", None)
        )

        # ── Glow ────────────────────────────────────────────────────────────
        if glow_rgba:
            gr   = gr_max  # fills widget exactly → circular, no square clipping
            grad = QRadialGradient(QPointF(cx, cy), gr)
            gc   = QColor(*glow_rgba)
            grad.setColorAt(0.0, gc)
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - gr, cy - gr, gr * 2, gr * 2))

        # ── Sphere ──────────────────────────────────────────────────────────
        p.setBrush(QBrush(QColor(base_hex)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # ── Mic icon (scales with r) ─────────────────────────────────────────
        s = r / 60.0  # scale factor relative to original design at r=60
        icon_color = QColor("white")
        pen = QPen(icon_color, max(1.5, 2.5 * s), Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)

        # Mic capsule
        p.setBrush(QBrush(icon_color))
        bw, bh = 14.0 * s, 22.0 * s
        body = QRectF(cx - bw / 2, cy - bh * 0.82, bw, bh)
        p.drawRoundedRect(body, bw / 2, bw / 2)

        # Stand arc
        p.setBrush(Qt.BrushStyle.NoBrush)
        aw = 26.0 * s
        p.drawArc(QRectF(cx - aw / 2, cy - 4.0 * s, aw, 20.0 * s), 0, -180 * 16)

        # Stem + base
        p.drawLine(QPointF(cx, cy + 16.0 * s), QPointF(cx, cy + 22.0 * s))
        p.drawLine(QPointF(cx - 7.0 * s, cy + 22.0 * s), QPointF(cx + 7.0 * s, cy + 22.0 * s))

        # ── Muted slash ──────────────────────────────────────────────────────
        if self._state == self.MUTED:
            slash_pen = QPen(QColor("#fa5252"), max(2.0, 3.0 * s),
                             Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(slash_pen)
            sr = r * 0.60
            p.drawLine(QPointF(cx - sr, cy - sr), QPointF(cx + sr, cy + sr))

        p.end()
