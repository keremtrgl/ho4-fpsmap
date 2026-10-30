"""Workshop image for the close-up snow change: before | after split of two
aligned in-game screenshots (after warped onto before by warp landmarks).

Usage: python -I snow_image.py <before_aligned.png> <after_aligned.png> <out.png>
"""
import sys
from PIL import Image, ImageDraw, ImageFont

BEFORE, AFTER, OUT = sys.argv[1:4]
GOLD, INK, WHITE = (226, 186, 92), (14, 17, 22), (240, 240, 236)


def font(size, bold=True):
    try:
        f = ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf', size)
        f.set_variation_by_name('Bold' if bold else 'Regular')
        return f
    except Exception:
        return ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', size)


a = Image.open(BEFORE).convert('RGB')
b = Image.open(AFTER).convert('RGB')
top = 84  # rows above this still show the after shot's top bar
a, b = a.crop((0, top, a.width, a.height)), b.crop((0, top, b.width, b.height))
w, h = a.size
img = a.copy()
img.paste(b.crop((w // 2, 0, w, h)), (w // 2, 0))
img = img.resize((1920, round(h * 1920 / w)), Image.LANCZOS)
w, h = img.size
d = ImageDraw.Draw(img, 'RGBA')
d.rectangle((w // 2 - 2, 0, w // 2 + 2, h), fill=GOLD)


def tag(text, xy, anchor):
    f = font(34)
    l, t, r, bt = d.textbbox(xy, text, font=f, anchor=anchor)
    d.rounded_rectangle((l - 16, t - 10, r + 16, bt + 12), 8, fill=(*INK, 215), outline=GOLD, width=2)
    d.text(xy, text, font=f, fill=WHITE, anchor=anchor)


tag('BEFORE  ·  1.19.4.0-2', (w // 2 - 40, 50), 'ra')
tag('AFTER  ·  1.19.4.0-3', (w // 2 + 40, 50), 'la')
band = Image.new('RGBA', (w, 170))
bd = ImageDraw.Draw(band)
for y in range(170):
    bd.line([(0, y), (w, y)], fill=(*INK, int(235 * y / 170)))
img.paste(band, (0, h - 170), band)
d.text((48, h - 92), 'No more white-out when zoomed in', font=font(52), fill=GOLD, anchor='ls')
d.text((50, h - 44), 'Same place, same winter day (1 Jan 1936). Snow now fades out up close; the strategic view keeps vanilla winter.',
       font=font(26, False), fill=WHITE, anchor='ls')
img.save(OUT, optimize=True)
print(OUT, img.size)
