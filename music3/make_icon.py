"""Generate the app icon (PNG + ICO) with PIL."""
from PIL import Image, ImageDraw, ImageFont

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# rounded-square gradient background
grad = Image.new("RGBA", (S, S))
gd = ImageDraw.Draw(grad)
for i in range(S):
    t = i / (S - 1)
    c = (int(124 + (0 - 124) * t), int(92 + (212 - 92) * t), 255, 255)
    gd.line([(0, i), (S, i)], fill=c)
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
img.paste(grad, (0, 0), mask)

d = ImageDraw.Draw(img)
# eighth note
cx, cy = S * 0.5, S * 0.42
stem_w = int(S * 0.055)
d.rounded_rectangle([cx - S * 0.16, cy - S * 0.06, cx - S * 0.16 + stem_w, S * 0.70],
                    radius=stem_w // 2, fill=(255, 255, 255, 255))
d.ellipse([cx - S * 0.30, S * 0.62, cx - S * 0.02, S * 0.80], fill=(255, 255, 255, 255))
# flag
d.polygon([(cx - S * 0.16 + stem_w, cy - S * 0.06),
            (cx + S * 0.22, cy - S * 0.02),
            (cx + S * 0.22, cy + S * 0.16),
            (cx - S * 0.16 + stem_w, cy + S * 0.10)],
           fill=(255, 255, 255, 255))

img.save("assets/icon.png")
img.resize((256, 256), Image.LANCZOS).save("assets/icon.ico",
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote assets/icon.png and assets/icon.ico")
