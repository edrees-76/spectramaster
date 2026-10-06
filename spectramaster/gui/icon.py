"""Application icon and logo.

Uses the designer logo in ``assets/`` (built by ``build_exe/make_icons.py``);
falls back to an icon drawn with QPainter if the assets are missing.

``python -m spectramaster.gui.icon`` writes ``spectramaster/gui/spectramaster.ico``
for PyInstaller (``--icon``).
"""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QIcon, QImage, QLinearGradient, QPainter, QPainterPath,
                           QPen, QPixmap)

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _curve(x: float) -> float:
    """Toy gamma spectrum: Compton continuum + two photopeaks, x in [0, 1]."""
    cont = 0.22 * math.exp(-2.2 * x) + 0.05
    peak1 = 0.42 * math.exp(-((x - 0.33) / 0.035) ** 2)
    peak2 = 0.72 * math.exp(-((x - 0.66) / 0.03) ** 2)
    edge = 0.07 if x < 0.55 else 0.02
    return cont + peak1 + peak2 + edge


def render_icon(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)
    m = s * 0.04
    rect = QRectF(m, m, s - 2 * m, s - 2 * m)
    bg = QLinearGradient(rect.topLeft(), rect.bottomRight())
    bg.setColorAt(0.0, QColor("#1f4e79"))
    bg.setColorAt(1.0, QColor("#0f2c47"))
    p.setPen(Qt.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(rect, s * 0.18, s * 0.18)

    left, right = rect.left() + s * 0.12, rect.right() - s * 0.10
    top, bottom = rect.top() + s * 0.12, rect.bottom() - s * 0.14
    w, h = right - left, bottom - top
    n = max(24, size)
    path = QPainterPath(QPointF(left, bottom))
    for i in range(n + 1):
        x = i / n
        path.lineTo(left + x * w, bottom - min(1.0, _curve(x)) * h)
    path.lineTo(right, bottom)
    path.closeSubpath()
    fill = QLinearGradient(0, top, 0, bottom)
    fill.setColorAt(0.0, QColor(255, 196, 61, 240))
    fill.setColorAt(1.0, QColor(255, 196, 61, 70))
    p.setBrush(fill)
    pen = QPen(QColor("#ffd772"), max(1.0, s / 40))
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.drawPath(path)
    # baseline
    p.setPen(QPen(QColor(255, 255, 255, 170), max(1.0, s / 48)))
    p.drawLine(QPointF(left, bottom), QPointF(right, bottom))
    p.end()
    return img


ASSETS = Path(__file__).with_name("assets")
ICON_PNG = ASSETS / "icon_512.png"
LOGO_PNG = ASSETS / "logo_full.png"
DESIGNER_PNG = ASSETS / "designer_logo.png"


def app_icon() -> QIcon:
    """The designer logo's symbol (assets/icon_512.png); drawn fallback if missing."""
    icon = QIcon()
    if ICON_PNG.exists():
        src = QPixmap(str(ICON_PNG))
        for sz in ICON_SIZES:
            icon.addPixmap(src.scaled(sz, sz, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        return icon
    for sz in ICON_SIZES:
        icon.addPixmap(QPixmap.fromImage(render_icon(sz)))
    return icon


def logo_pixmap(width: int) -> QPixmap | None:
    """Full logo with wordmark (assets/logo_full.png), scaled to `width`, or None."""
    if not LOGO_PNG.exists():
        return None
    return QPixmap(str(LOGO_PNG)).scaledToWidth(width, Qt.SmoothTransformation)


def designer_pixmap(height: int) -> QPixmap | None:
    """Designer monogram (assets/designer_logo.png) scaled smoothly to `height`, or None."""
    if not DESIGNER_PNG.exists():
        return None
    pm = QPixmap(str(DESIGNER_PNG))
    if pm.isNull():
        return None
    return pm.scaledToHeight(int(height), Qt.SmoothTransformation)


def write_ico(path: Path | None = None) -> Path:
    """Write a multi-resolution-ish .ico (Qt writes the 256 px image)."""
    path = Path(path) if path else Path(__file__).with_name("spectramaster.ico")
    render_icon(256).save(str(path), "ICO")
    return path


if __name__ == "__main__":  # pragma: no cover
    from PySide6.QtGui import QGuiApplication
    import sys
    _app = QGuiApplication(sys.argv)
    print(write_ico())
