#!/usr/bin/env python3
"""Generate the full favicon set from public/favicon.svg (ECO.NOVA leaf mark)."""
import io
import os

import cairosvg
from PIL import Image

PUB = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public")
PUB = os.path.abspath(PUB)
SVG = os.path.join(PUB, "favicon.svg")

SIZES = {
    "favicon-16x16.png": 16,
    "favicon-32x32.png": 32,
    "favicon-48x48.png": 48,
    "favicon-96x96.png": 96,
    "mstile-150x150.png": 150,
    "apple-touch-icon.png": 180,
    "android-chrome-192x192.png": 192,
    "android-chrome-512x512.png": 512,
}


def main():
    with open(SVG, "rb") as f:
        svg_bytes = f.read()

    for name, size in SIZES.items():
        png = cairosvg.svg2png(bytestring=svg_bytes, output_width=size, output_height=size)
        with open(os.path.join(PUB, name), "wb") as out:
            out.write(png)
        print(f"  ✓ {name} ({size}x{size})")

    # favicon.ico — multi-size (16/32/48)
    frames = []
    for size in (16, 32, 48):
        png = cairosvg.svg2png(bytestring=svg_bytes, output_width=size, output_height=size)
        frames.append(Image.open(io.BytesIO(png)).convert("RGBA"))
    ico_path = os.path.join(PUB, "favicon.ico")
    frames[0].save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)], append_images=frames[1:])
    print("  ✓ favicon.ico (16/32/48)")


if __name__ == "__main__":
    main()
