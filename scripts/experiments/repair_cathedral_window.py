import numpy as np
from PIL import Image, ImageDraw

p1_path = r"F:\AI-Office\data\manga\de_ai_panels\p1_cathedral_de_ai.png"
p1_out = r"F:\AI-Office\data\manga\de_ai_panels\p1_cathedral_masterpiece.png"

im = Image.open(p1_path).convert("RGB")
draw = ImageDraw.Draw(im)

# The round window is located at center x~512, y~150, radius ~46 px
cx, cy, r = 512, 148, 46

# 1. Remove the weird red donut ring by repainting the round aperture with authentic dark gothic stained glass
# Soft dark moonlit background with subtle screentone
for ri in range(r, 0, -1):
    alpha = ri / r
    shade = int(25 + 35 * (1 - alpha))
    draw.ellipse([cx - ri, cy - ri, cx + ri, cy + ri], fill=(shade, shade + 5, shade + 15), outline=None)

# 2. Draw authentic Gothic Rose Stone Tracery (Mullions & Quatrefoil petals in solid dark iron/stone)
# Outer stone ring
draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(15, 15, 20), width=4)
draw.ellipse([cx - r + 6, cy - r + 6, cx + r - 6, cy + r - 6], outline=(25, 25, 30), width=2)

# Central stone rosette
cr = 12
draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(15, 15, 20), outline=(5, 5, 10), width=2)

# 8 Gothic radiating stone spokes
import math
for i in range(8):
    ang = i * (math.pi / 4)
    x1 = cx + int((r - 2) * math.cos(ang))
    y1 = cy + int((r - 2) * math.sin(ang))
    draw.line([(cx, cy), (x1, y1)], fill=(15, 15, 20), width=3)

# 8 Quatrefoil outer petal loops
for i in range(8):
    ang = (i + 0.5) * (math.pi / 4)
    px = cx + int((r * 0.65) * math.cos(ang))
    py = cy + int((r * 0.65) * math.sin(ang))
    pr = 9
    draw.ellipse([px - pr, py - pr, px + pr, py + pr], outline=(15, 15, 20), width=2)

im.save(p1_out, "PNG")
print(f"[REPAIR] Fixed weird red donut! Replaced with authentic Gothic Rose Stone Tracery -> {p1_out}")
