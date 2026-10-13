"""Draws icon.ico (and docs/icon.png): violet rounded square with a white rack module (a sound
module front: display window and two knobs), same construction as the EBL-to-WAV icon.

Every size is rendered on its own (16x supersampled, then reduced with Lanczos) so small sizes
stay sharp: no knobs below 24 px, no margin below 24 px.
"""
from PIL import Image, ImageDraw

SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
TOP, BOTTOM = (196, 181, 253), (109, 40, 217)  # vertical gradient
SS = 16


def render(n: int) -> Image.Image:
    big = n * SS
    margin = 0 if n < 24 else round(big / 16)
    side = big - 2 * margin
    grad = Image.new("RGBA", (1, side))
    for y in range(side):
        t = y / max(1, side - 1)
        grad.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM)) + (255,))
    grad = grad.resize((side, side))
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, side - 1, side - 1), radius=round(side * 0.23), fill=255)
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    img.paste(grad, (margin, margin), mask)

    d = ImageDraw.Draw(img)
    x0, x1 = margin + side * 0.14, margin + side * 0.86
    y0, y1 = margin + side * 0.32, margin + side * 0.68
    line = side * (0.1 if n <= 20 else 0.075 if n <= 32 else 0.06)
    d.rounded_rectangle((x0, y0, x1, y1), radius=side * 0.07, outline="white", width=round(line))
    # Display window
    dx0, dy0 = x0 + side * 0.11, y0 + side * 0.1
    dx1, dy1 = x0 + side * (0.38 if n >= 24 else 0.58), y1 - side * 0.1
    d.rounded_rectangle((dx0, dy0, dx1, dy1), radius=side * 0.025, fill="white")
    if n >= 24:  # two knobs
        r = side * 0.05
        cy = (y0 + y1) / 2
        for cx in (x0 + side * 0.44, x0 + side * 0.59):
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill="white")
    return img.resize((n, n), Image.Resampling.LANCZOS)


if __name__ == "__main__":
    frames = [render(n) for n in SIZES]
    frames[-1].save("icon.ico", format="ICO", sizes=[(n, n) for n in SIZES], append_images=frames[:-1])
    frames[-1].save("docs/icon.png")
