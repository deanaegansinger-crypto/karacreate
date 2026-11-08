# Makes karaoke.ico: python scripts/make_icon.py karaoke.ico icon.png
"""Draws the app icon: a microphone on a dark rounded square, with a blue wipe."""
import sys
from PIL import Image, ImageDraw

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((40, 40, S - 40, S - 40), radius=200, fill=(18, 20, 32, 255))
# lyric lines: one sung (blue), one to sing (white)
d.rounded_rectangle((170, 760, 600, 820), radius=30, fill=(51, 153, 255, 255))
d.rounded_rectangle((620, 760, 854, 820), radius=30, fill=(255, 255, 255, 255))
d.rounded_rectangle((260, 860, 764, 905), radius=22, fill=(255, 255, 255, 170))
# microphone
cx = S // 2
d.rounded_rectangle((cx - 120, 130, cx + 120, 500), radius=120, fill=(255, 255, 255, 255))
for y in range(220, 460, 55):
    d.line((cx - 80, y, cx + 80, y), fill=(18, 20, 32, 255), width=14)
d.arc((cx - 190, 260, cx + 190, 600), start=0, end=180, fill=(255, 204, 0, 255), width=34)
d.rectangle((cx - 17, 595, cx + 17, 680), fill=(255, 204, 0, 255))
d.rounded_rectangle((cx - 110, 670, cx + 110, 710), radius=20, fill=(255, 204, 0, 255))
img.save(sys.argv[1], sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.resize((256, 256), Image.LANCZOS).save(sys.argv[2])
