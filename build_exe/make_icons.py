"""Build the app icon and the About-dialog logo from the designer's sources.

python build_exe/make_icons.py   (run from the project root)

Sources (designer, 1254 x 1254):
  icon_source.webp        the symbol (S, orbit, gamma peak and the letter gamma), transparent background
  logo_full_source.webp   symbol, "SpectraMaster" and the English subtitle on a white background

The Arabic subtitle is drawn with Qt (which shapes Arabic; Pillow here cannot) between the name
and the English subtitle.  Writes spectramaster/gui/assets/icon_512.png, assets/logo_full.png,
spectramaster/gui/spectramaster.ico and docs/images/logo_full.png; then run
installer/make_wizard_images.py for the installer images.
"""
import shutil

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

ICON_SRC = "icon_source.webp"
FULL_SRC = "logo_full_source.webp"
ASSETS = "spectramaster/gui/assets"
WHITE = 225                     # min(R, G, B) above this is background white
FULL_WIDTH = 1200
ARABIC = "منظومة تحليل أطياف أشعة جاما"
NAVY = (7, 40, 74)              # colour of the name in the source
ARABIC_PX = 64                  # font pixel size of the Arabic line
LINE_GAP = 26                   # extra space around the inserted line


def white_mask(a: np.ndarray) -> np.ndarray:
    return a[..., :3].min(axis=2) > WHITE


def border_white(a: np.ndarray) -> np.ndarray:
    """White connected to the image border (keeps enclosed white inside the symbol)."""
    labels, _ = ndimage.label(white_mask(a))
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    return np.isin(labels, list(border))


def with_alpha(rgb: Image.Image, transparent: np.ndarray) -> Image.Image:
    alpha = Image.fromarray(np.where(transparent, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def arabic_line(width: int) -> Image.Image:
    """The Arabic subtitle, shaped by Qt, black on white, `width` wide."""
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 (fonts need an application)
    h = int(ARABIC_PX * 1.9)
    img = QImage(width, h, QImage.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setRenderHint(QPainter.TextAntialiasing)
    f = QFont("Segoe UI")
    f.setPixelSize(ARABIC_PX)
    f.setWeight(QFont.DemiBold)
    p.setFont(f)
    p.setPen(QColor(*NAVY))
    p.setLayoutDirection(Qt.RightToLeft)
    p.drawText(QRect(0, 0, width, h), int(Qt.AlignCenter), ARABIC)
    p.end()
    buf = img.constBits().tobytes()
    arr = np.frombuffer(buf, np.uint8).reshape(h, img.bytesPerLine() // 4, 4)[:, :width, :3][..., ::-1]
    out = Image.fromarray(np.ascontiguousarray(arr))
    a = np.asarray(out).astype(int)
    rows = np.where((a.min(axis=2) < 200).any(axis=1))[0]
    return out.crop((0, rows[0] - 4, width, rows[-1] + 5))


def full_logo() -> Image.Image:
    im = Image.open(FULL_SRC).convert("RGB")
    a = np.asarray(im).astype(int)
    ink = a.min(axis=2) < WHITE
    rows = np.where(ink.sum(axis=1) > 2)[0]
    # the symbol ends at the first wide blank band; the name and the English subtitle follow,
    # separated by the last blank band
    sym_end = next(rows[i] for i in range(len(rows) - 1) if rows[i + 1] - rows[i] > 25)
    text = rows[rows > sym_end]
    split = next(text[i] for i in range(len(text) - 1) if text[i + 1] - text[i] > 3)
    cut = (split + text[text > split][0]) // 2
    ar = arabic_line(im.width)
    top, bottom = im.crop((0, 0, im.width, cut)), im.crop((0, cut, im.width, im.height))
    out = Image.new("RGB", (im.width, im.height + ar.height + 2 * LINE_GAP), "white")
    out.paste(top, (0, 0))
    out.paste(ar, (0, cut + LINE_GAP))
    out.paste(bottom, (0, cut + ar.height + 2 * LINE_GAP))
    b = np.asarray(out).astype(int)
    transparent = border_white(b)
    transparent[sym_end + 1:] = white_mask(b)[sym_end + 1:]      # letter counters too
    return with_alpha(out, transparent)


def main() -> None:
    icon = Image.open(ICON_SRC).convert("RGBA")
    sym = icon.crop(icon.getbbox())
    side = int(max(sym.size) * 1.04)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(sym, ((side - sym.width) // 2, (side - sym.height) // 2), sym)
    sq.resize((512, 512), Image.LANCZOS).save(f"{ASSETS}/icon_512.png")
    sq.save("spectramaster/gui/spectramaster.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])

    rgba = full_logo()
    bb = rgba.getbbox()
    full = rgba.crop((bb[0] - 12, bb[1] - 12, bb[2] + 12, bb[3] + 12))
    full = full.resize((FULL_WIDTH, round(full.height * FULL_WIDTH / full.width)), Image.LANCZOS)
    full.save(f"{ASSETS}/logo_full.png", optimize=True)
    shutil.copyfile(f"{ASSETS}/logo_full.png", "docs/images/logo_full.png")


if __name__ == "__main__":
    main()
