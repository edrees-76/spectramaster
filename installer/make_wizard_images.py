"""Create the Inno Setup wizard images from the SpectraMaster / designer logos.

python installer/make_wizard_images.py      (run from the project root)

Output (24-bit BMP, one file per DPI step; Inno Setup picks the best match):
  installer/images/wizard_<w>x<h>.bmp         WizardImageFile   (Welcome / Finished pages)
  installer/images/wizard_small_<w>x<h>.bmp   WizardSmallImageFile (top-right of inner pages)
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "spectramaster" / "gui" / "assets"
OUT = ROOT / "installer" / "images"
FONTS = Path("C:/Windows/Fonts")

# sizes recommended by the Inno Setup 6 help for 100/125/150/175/200/225/250 % DPI
LARGE = [(164, 314), (192, 386), (246, 459), (273, 556), (328, 604), (355, 700), (410, 797)]
SMALL = [(55, 55), (64, 68), (83, 80), (92, 97), (110, 106), (119, 123), (138, 140)]

NAVY = (27, 58, 92)
SLATE = (84, 104, 128)
ORANGE = (240, 138, 36)
CYAN = (59, 178, 204)
TOP = (226, 243, 249)        # gradient: light cyan at the top -> white at the bottom
SS = 3                       # supersampling factor


def font(name: str, px: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), max(6, int(round(px))))


def fit_font(draw: ImageDraw.ImageDraw, text: str, name: str, px: float, max_w: float) -> ImageFont.FreeTypeFont:
    f = font(name, px)
    while draw.textlength(text, font=f) > max_w and px > 6:
        px -= 0.5
        f = font(name, px)
    return f


def centered(draw: ImageDraw.ImageDraw, y: float, text: str, f, fill, width: int) -> float:
    """Draw ``text`` horizontally centred with its top at ``y``; returns the bottom."""
    x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=f)
    draw.text(((width - (x1 - x0)) / 2 - x0, y - y0), text, font=f, fill=fill)
    return y + (y1 - y0)


def designer_logo() -> Image.Image:
    """Designer mark cropped to its ink (white page background stays white)."""
    im = Image.open(ASSETS / "designer_logo.png").convert("RGB")
    gray = im.convert("L").point(lambda v: 255 if v < 200 else 0)
    return im.crop(gray.getbbox())


def large(w: int, h: int, icon: Image.Image, mark: Image.Image) -> Image.Image:
    W, H = w * SS, h * SS
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    for y in range(H):                                   # vertical gradient
        t = min(1.0, y / (H * 0.62))
        d.line([(0, y), (W, y)], fill=tuple(int(a + (255 - a) * t) for a in TOP))
    d.rectangle([0, 0, W, int(4 * SS * w / 164)], fill=CYAN)   # thin brand stripe at the top
    u = min(W / 164, H / 314)                            # layout unit (1 px at 100 %)
    side = int(118 * u)
    ic = icon.resize((side, side), Image.LANCZOS)
    y = int(H * 0.075)
    img.paste(ic, ((W - side) // 2, y), ic)
    y += side + 8 * u
    f_name = fit_font(d, "SpectraMaster", "segoeuib.ttf", 23 * u, W - 14 * u)
    y = centered(d, y, "SpectraMaster", f_name, NAVY, W) + 7 * u
    y = centered(d, y, "Gamma-Spectrum Analysis", fit_font(d, "Gamma-Spectrum Analysis", "segoeui.ttf",
                                                           11 * u, W - 16 * u), SLATE, W) + 8 * u
    d.rounded_rectangle([W / 2 - 22 * u, y, W / 2 + 22 * u, y + 2.2 * u], radius=1.1 * u, fill=ORANGE)
    y += 9 * u
    centered(d, y, "Version 1.0.0", font("segoeuisl.ttf", 10.5 * u), NAVY, W)

    # designer credit at the bottom
    credit = "Designed by Edrees F. Hery"
    f_cr = fit_font(d, credit, "segoeui.ttf", 8.6 * u, W - 10 * u)
    cr_h = d.textbbox((0, 0), credit, font=f_cr)[3]
    mh = int(52 * u)
    mw = int(mark.width * mh / mark.height)
    m = mark.resize((mw, mh), Image.LANCZOS)
    y_cr = H - 10 * u - cr_h
    y_m = int(y_cr - 6 * u - mh)
    img.paste(m, ((W - mw) // 2, y_m))
    centered(d, y_cr, credit, f_cr, SLATE, W)
    return img.resize((w, h), Image.LANCZOS)


def small(w: int, h: int, icon: Image.Image) -> Image.Image:
    W, H = w * SS, h * SS
    img = Image.new("RGB", (W, H), "white")
    side = int(min(W, H) * 0.92)
    ic = icon.resize((side, side), Image.LANCZOS)
    img.paste(ic, ((W - side) // 2, (H - side) // 2), ic)
    return img.resize((w, h), Image.LANCZOS)


def main() -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    icon = Image.open(ASSETS / "icon_512.png").convert("RGBA")
    mark = designer_logo()
    written = []
    for w, h in LARGE:
        p = OUT / f"wizard_{w}x{h}.bmp"
        large(w, h, icon, mark).save(p)
        written.append(p)
    for w, h in SMALL:
        p = OUT / f"wizard_small_{w}x{h}.bmp"
        small(w, h, icon).save(p)
        written.append(p)
    return written


if __name__ == "__main__":
    for p in main():
        print(p.relative_to(ROOT))
