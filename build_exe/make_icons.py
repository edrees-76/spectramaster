"""Build the app icon and the About-dialog logo from the designer's logo.jpg (2000 x 2000, white
background: magnifying glass over a gamma spectrum, wordmark and subtitles below).

python build_exe/make_icons.py   (run from the project root)

Writes spectramaster/gui/assets/icon_512.png (symbol only), assets/logo_full.png,
spectramaster/gui/spectramaster.ico and docs/images/logo_full.png; then run
installer/make_wizard_images.py for the installer images.
"""
import shutil

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

SRC = "logo.jpg"
ASSETS = "spectramaster/gui/assets"
WHITE = 225                  # min(R, G, B) above this is background white
FULL_WIDTH = 1200


def white_mask(a: np.ndarray) -> np.ndarray:
    return a.min(axis=2) > WHITE


def border_white(a: np.ndarray) -> np.ndarray:
    """White connected to the image border (keeps the white ring inside the lens)."""
    labels, _ = ndimage.label(white_mask(a))
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    return np.isin(labels, list(border))


def with_alpha(rgb: Image.Image, transparent: np.ndarray) -> Image.Image:
    alpha = Image.fromarray(np.where(transparent, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def main() -> None:
    im = Image.open(SRC).convert("RGB")
    a = np.asarray(im).astype(int)
    ink = ~white_mask(a)
    rows = np.where(ink.sum(axis=1) > 3)[0]
    # the symbol ends at the first wide blank band above the wordmark
    gap = next(rows[i] for i in range(len(rows) - 1) if rows[i + 1] - rows[i] > 25)
    # symbol: only the outer white goes; text: every white pixel goes (letter counters too)
    transparent = border_white(a)
    transparent[gap + 1:] = white_mask(a)[gap + 1:]
    rgba = with_alpha(im, transparent)

    cols = np.where(ink[:gap + 1].sum(axis=0) > 3)[0]
    sym = rgba.crop((cols[0] - 6, rows[0] - 6, cols[-1] + 7, gap + 7))
    side = int(max(sym.size) * 1.04)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(sym, ((side - sym.width) // 2, (side - sym.height) // 2), sym)
    sq.resize((512, 512), Image.LANCZOS).save(f"{ASSETS}/icon_512.png")
    sq.save("spectramaster/gui/spectramaster.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])

    bb = rgba.getbbox()
    full = rgba.crop((bb[0] - 12, bb[1] - 12, bb[2] + 12, bb[3] + 12))
    full = full.resize((FULL_WIDTH, round(full.height * FULL_WIDTH / full.width)), Image.LANCZOS)
    full.save(f"{ASSETS}/logo_full.png", optimize=True)
    shutil.copyfile(f"{ASSETS}/logo_full.png", "docs/images/logo_full.png")


if __name__ == "__main__":
    main()
