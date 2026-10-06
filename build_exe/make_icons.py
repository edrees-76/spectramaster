"""Build app icon + About-dialog logo from the designer's logo.jfif.

python build_exe/make_icons.py   (run from the project root)
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

SRC = "logo.jfif"
ASSETS = "spectramaster/gui/assets"


def background_alpha(rgb: Image.Image) -> Image.Image:
    """Alpha mask: 0 for near-white pixels connected to the image border."""
    a = np.asarray(rgb).astype(int)
    white = a.min(axis=2) > 225
    labels, _ = ndimage.label(white)
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    bg = np.isin(labels, list(border))
    alpha = np.where(bg, 0, 255).astype(np.uint8)
    return Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(1.2))


def main() -> None:
    im = Image.open(SRC).convert("RGB")
    a = np.asarray(im).astype(int)
    # cyan page outline -> page box, used to keep the page interior opaque white
    cyan = (a[:, :, 2] > 150) & (a[:, :, 0] < 120) & (a[:, :, 1] > 140)
    ys, xs = np.where(cyan[: int(im.height * 0.72)])
    px0, px1, py0, py1 = xs.min(), xs.max(), ys.min(), ys.max()

    def cut(box):
        region = im.crop(box)
        ox, oy = box[0], box[1]
        out = Image.new("RGBA", region.size, (0, 0, 0, 0))
        m, fold = 12, int((px1 - px0) * 0.30)
        d = ImageDraw.Draw(out)
        r = int((px1 - px0) * 0.07)  # the outline has rounded corners; stay inside them
        d.rounded_rectangle((px0 + m - ox, py0 + m - oy, px1 - m - ox, py1 - m - oy), radius=r,
                            fill=(255, 255, 255, 255))
        # cut away the folded top-right corner
        d.polygon([(px1 - fold - ox, py0 - oy), (px1 - ox + 1, py0 - oy), (px1 - ox + 1, py0 + fold - oy)],
                  fill=(0, 0, 0, 0))
        fg = region.copy()
        fg.putalpha(background_alpha(region))
        out.alpha_composite(fg)
        return out

    # symbol = everything above the wordmark
    ink = (a.min(axis=2) < 215) | (a.max(axis=2) - a.min(axis=2) > 40)
    rows = np.where(ink.sum(axis=1) > 3)[0]
    gap = next(rows[i] for i in range(len(rows) - 1) if rows[i + 1] - rows[i] > 25)
    cols = np.where(ink[:gap].sum(axis=0) > 3)[0]
    sym = cut((cols[0] - 10, rows[0] - 10, cols[-1] + 11, gap + 11))
    side = int(max(sym.size) * 1.04)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(sym, ((side - sym.width) // 2, (side - sym.height) // 2), sym)
    sq.resize((512, 512), Image.LANCZOS).save(f"{ASSETS}/icon_512.png")
    sq.save("spectramaster/gui/spectramaster.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])

    full = cut((0, 0, im.width, im.height))
    bb = full.getbbox()
    full = full.crop((bb[0] - 10, bb[1] - 10, bb[2] + 10, bb[3] + 10))
    full.thumbnail((900, 900), Image.LANCZOS)
    full.save(f"{ASSETS}/logo_full.png")


if __name__ == "__main__":
    main()
