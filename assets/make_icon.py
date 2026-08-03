"""Generate the MediaForge app icon (assets/mediaforge.ico).

A white play triangle on a rounded square with the brand purple->teal gradient.
Run:  python assets/make_icon.py   (needs Pillow)
"""
from pathlib import Path

from PIL import Image, ImageDraw

S = 256
A = (0x7C, 0x5C, 0xFF)  # brand purple  (--accent)
B = (0x00, 0xD4, 0xAA)  # brand teal    (--accent-2)

# Diagonal gradient background.
grad = Image.new("RGB", (S, S))
px = grad.load()
for y in range(S):
    for x in range(S):
        t = (x + y) / (2 * (S - 1))
        px[x, y] = (
            round(A[0] + (B[0] - A[0]) * t),
            round(A[1] + (B[1] - A[1]) * t),
            round(A[2] + (B[2] - A[2]) * t),
        )

# Rounded-square mask.
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=56, fill=255)

icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
icon.paste(grad, (0, 0), mask)

# White play triangle, optically centered (nudged right).
d = ImageDraw.Draw(icon)
d.polygon([(104, 74), (104, 182), (188, 128)], fill=(255, 255, 255, 240))

out = Path(__file__).with_name("mediaforge.ico")
icon.save(out, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
# Also a PNG preview.
icon.save(Path(__file__).with_name("mediaforge.png"))
print("wrote", out)
