"""Draw the League Remote icon (original artwork, no Riot assets).

A gold notification bell with teal "signal" arcs on a dark rounded square.
Writes assets/icon.png (512 px) and assets/icon.ico (16-256 px).
Run: python tools/make_icon.py
"""
import os

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
S = 1024  # draw big, downsample for smooth edges

NAVY, NAVY2 = (1, 10, 19), (10, 20, 40)
GOLD, GOLD_DARK, GOLD_LIGHT = (200, 170, 110), (120, 90, 40), (240, 230, 210)
TEAL = (10, 200, 185)


def draw(card=True):
    """card=True: rounded card with a gold frame (app icon). False: full-bleed square (profile pictures)."""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # background: subtle vertical gradient
    bg = Image.new("RGBA", (S, S))
    g = ImageDraw.Draw(bg)
    for y in range(S):
        t = y / S
        g.line([(0, y), (S, y)], fill=tuple(int(NAVY2[i] * (1 - t) + NAVY[i] * t) for i in range(3)) + (255,))
    d = ImageDraw.Draw(img)
    if card:
        mask = Image.new("L", (S, S), 0)
        ImageDraw.Draw(mask).rounded_rectangle([24, 24, S - 24, S - 24], radius=210, fill=255)
        img.paste(bg, (0, 0), mask)
        d.rounded_rectangle([24, 24, S - 24, S - 24], radius=210, outline=GOLD_DARK + (255,), width=18)
    else:
        img.paste(bg, (0, 0))

    # teal signal arcs (the "remote" part), with a soft glow
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = S // 2, 430
    for r, w in ((300, 34), (380, 30)):
        for start, end in ((200, 250), (290, 340)):
            gd.arc([cx - r, cy - r, cx + r, cy + r], start, end, fill=TEAL + (255,), width=w)
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))
    img.alpha_composite(glow)

    # gold bell: draw the silhouette as a mask, fill it with a metallic gradient
    shape = Image.new("L", (S, S), 0)
    b = ImageDraw.Draw(shape)
    b.ellipse([cx - 38, 212, cx + 38, 288], fill=255)                                # top knob
    b.pieslice([cx - 190, 250, cx + 190, 630], 180, 360, fill=255)                   # dome
    b.polygon([(cx - 190, 438), (cx + 190, 438), (cx + 245, 680), (cx - 245, 680)], fill=255)
    b.rounded_rectangle([cx - 285, 662, cx + 285, 722], radius=30, fill=255)          # rim
    b.ellipse([cx - 58, 728, cx + 58, 830], fill=255)                                # clapper
    metal = Image.new("RGBA", (S, S))
    m = ImageDraw.Draw(metal)
    for x in range(S):  # light on the left, darker on the right
        t = max(0.0, min(1.0, (x - (cx - 290)) / 580))
        k = 1.25 - 0.55 * t
        m.line([(x, 0), (x, S)], fill=tuple(min(255, int(c * k)) for c in GOLD) + (255,))
    img.paste(metal, (0, 0), shape)

    # shine on the dome and a dark line between body and rim, for depth
    shine = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shine).ellipse([cx - 130, 300, cx - 60, 520], fill=GOLD_LIGHT + (110,))
    img.alpha_composite(shine.filter(ImageFilter.GaussianBlur(14)))
    d.line([(cx - 250, 664), (cx + 250, 664)], fill=GOLD_DARK + (255,), width=10)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    big = draw()
    big.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, "icon.png"))
    big.resize((256, 256), Image.LANCZOS).save(
        os.path.join(OUT, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    # square profile picture (GitHub organization avatar): full-bleed, no frame
    draw(card=False).convert("RGB").resize((500, 500), Image.LANCZOS).save(os.path.join(OUT, "avatar.png"))
    print("wrote assets/icon.png, assets/icon.ico and assets/avatar.png")


if __name__ == "__main__":
    main()
