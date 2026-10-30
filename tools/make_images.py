"""Build Steam Workshop images from matched vanilla/mod screenshots.

Usage: python -I make_images.py <test dir with vanilla/ and mod/> <out dir> <mod dir for thumbnail.png>
"""
import os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

TEST, OUT, MOD = sys.argv[1:4]
os.makedirs(OUT, exist_ok=True)
FONTS = 'C:/Windows/Fonts/'
GOLD, INK, WHITE = (226, 186, 92), (14, 17, 22), (240, 240, 236)


def font(size, bold=True):
    for name in (['bahnschrift.ttf'] if bold else []) + ['segoeuib.ttf' if bold else 'segoeui.ttf']:
        try:
            f = ImageFont.truetype(FONTS + name, size)
            if name == 'bahnschrift.ttf' and bold:
                f.set_variation_by_name('Bold')
            return f
        except Exception:
            continue
    return ImageFont.load_default()


def load(side, name):
    return Image.open(os.path.join(TEST, side, name)).convert('RGB')


def tag(img, text, xy, anchor='la', size=34):
    d = ImageDraw.Draw(img, 'RGBA')
    f = font(size)
    l, t, r, b = d.textbbox(xy, text, font=f, anchor=anchor)
    d.rounded_rectangle((l - 16, t - 10, r + 16, b + 12), 8, fill=(*INK, 215), outline=(*GOLD, 255), width=2)
    d.text(xy, text, font=f, fill=WHITE, anchor=anchor)


def banner(img, title, subtitle):
    """Dark gradient band at the bottom with a title."""
    w, h = img.size
    band = Image.new('RGBA', (w, 170), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    for y in range(170):
        bd.line([(0, y), (w, y)], fill=(*INK, int(235 * y / 170)))
    img.paste(band, (0, h - 170), band)
    d = ImageDraw.Draw(img)
    d.text((48, h - 92), title, font=font(52), fill=GOLD, anchor='ls')
    d.text((50, h - 44), subtitle, font=font(28, bold=False), fill=WHITE, anchor='ls')


def split(name, title, subtitle, out):
    """Vanilla left half | mod right half, gold divider, labels."""
    v, m = load('vanilla', name), load('mod', name)
    w, h = m.size
    img = v.copy()
    img.paste(m.crop((w // 2, 0, w, h)), (w // 2, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((w // 2 - 2, 0, w // 2 + 2, h), fill=GOLD)
    tag(img, 'VANILLA 1.19', (w // 2 - 40, 120), anchor='ra')
    tag(img, 'FPS MAP', (w // 2 + 40, 120))
    banner(img, title, subtitle)
    img.save(os.path.join(OUT, out), optimize=True)


def pair_crop(name, box, title, out):
    """Two crops stacked side by side (vanilla | mod)."""
    v, m = load('vanilla', name).crop(box), load('mod', name).crop(box)
    cw, ch = v.size
    pad = 24
    img = Image.new('RGB', (cw * 2 + pad * 3, ch + 160), INK)
    img.paste(v, (pad, 110))
    img.paste(m, (cw + pad * 2, 110))
    d = ImageDraw.Draw(img)
    d.text((img.width // 2, 58), title, font=font(46), fill=GOLD, anchor='mm')
    d.text((pad + cw // 2, ch + 136), 'Vanilla 1.19', font=font(28, bold=False), fill=WHITE, anchor='mm')
    d.text((cw + pad * 2 + cw // 2, ch + 136), 'FPS Map', font=font(28), fill=GOLD, anchor='mm')
    img.save(os.path.join(OUT, out), optimize=True)


split('close.png', 'Non-reflective water · Sharper borders · Clean rivers',
      'Same camera, same moment — left: vanilla 1.19.4, right: FPS Map', '01_compare_close.png')
split('wide.png', 'Clear strategic view',
      'Deep, calm seas make every coastline and border instantly readable', '02_compare_wide.png')
pair_crop('close.png', (380, 80, 1380, 620), 'Baltic coast up close', '03_coast_detail.png')
pair_crop('production.png', (0, 0, 560, 1080), 'Coloured, readable UI', '04_ui_production.png')

hero = load('mod', 'close.png')
banner(hero, 'FPS Map — Updated for 1.19', 'Ironman & Multiplayer safe  ·  All DLC  ·  Purely visual')
hero.save(os.path.join(OUT, '05_mod_close.png'), optimize=True)
wide = load('mod', 'wide.png')
banner(wide, 'Built for long wars', 'Flat, unlit plan arrows and solid borders at every zoom level')
wide.save(os.path.join(OUT, '06_mod_wide.png'), optimize=True)

# Thumbnail: square crop of the modded coast with a title plate. Under 1 MB.
src = load('mod', 'close.png').crop((560, 80, 1560, 1080)).resize((512, 512), Image.LANCZOS)
src = Image.blend(src, src.filter(ImageFilter.GaussianBlur(1.2)), 0.5)
th = src.convert('RGBA')
ov = Image.new('RGBA', th.size, (0, 0, 0, 0))
od = ImageDraw.Draw(ov)
for y in range(512):
    a = int(200 * max(0, (y - 220) / 292))
    od.line([(0, y), (512, y)], fill=(*INK, a))
od.rectangle((0, 0, 511, 511), outline=(*GOLD, 255), width=6)
th = Image.alpha_composite(th, ov)
d = ImageDraw.Draw(th)
d.text((256, 360), 'FPS MAP', font=font(96), fill=GOLD, anchor='mm', stroke_width=3, stroke_fill=INK)
d.text((256, 425), 'UPDATED FOR 1.19', font=font(34), fill=WHITE, anchor='mm', stroke_width=2, stroke_fill=INK)
d.rounded_rectangle((120, 452, 392, 492), 8, fill=(*INK, 230), outline=(*GOLD, 255), width=2)
d.text((256, 472), 'IRONMAN  ·  MP SAFE', font=font(22), fill=GOLD, anchor='mm')
th = th.convert('RGB')
th.save(os.path.join(OUT, 'thumbnail.png'), optimize=True)
th.save(os.path.join(MOD, 'thumbnail.png'), optimize=True)

# Colour-blind sub-mod thumbnail: same plate, with the first 8 army colours.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import colorblind
cb = Image.alpha_composite(src.convert('RGBA'), ov)
d = ImageDraw.Draw(cb)
d.text((256, 330), 'FPS MAP', font=font(96), fill=GOLD, anchor='mm', stroke_width=3, stroke_fill=INK)
d.text((256, 395), 'COLOUR-BLIND ADD-ON', font=font(34), fill=WHITE, anchor='mm', stroke_width=2, stroke_fill=INK)
for i, c in enumerate(colorblind.palette(8)):
    x = 72 + i * 47
    d.rounded_rectangle((x, 430, x + 40, 470), 6, fill=tuple(int(v * 255 + .5) for v in c), outline=INK, width=2)
d.text((256, 490), 'ARMY ARROWS + RED/GREEN INDICATORS', font=font(18), fill=GOLD, anchor='mm')
cb.convert('RGB').save(os.path.join(OUT, 'thumbnail_colorblind.png'), optimize=True)

# Calm Water add-on thumbnail: open sea from the modded wide shot.
sea = load('mod', 'wide.png').crop((120, 90, 1020, 990)).resize((512, 512), Image.LANCZOS).convert('RGBA')
cw = Image.alpha_composite(sea, ov)
d = ImageDraw.Draw(cw)
d.text((256, 340), 'FPS MAP', font=font(96), fill=GOLD, anchor='mm', stroke_width=3, stroke_fill=INK)
d.text((256, 405), 'CALM WATER ADD-ON', font=font(34), fill=WHITE, anchor='mm', stroke_width=2, stroke_fill=INK)
d.rounded_rectangle((110, 440, 402, 480), 8, fill=(*INK, 230), outline=(*GOLD, 255), width=2)
d.text((256, 460), 'SOFTER SUN GLARE', font=font(22), fill=GOLD, anchor='mm')
cw.convert('RGB').save(os.path.join(OUT, 'thumbnail_calmwater.png'), optimize=True)

for f in sorted(os.listdir(OUT)):
    p = os.path.join(OUT, f)
    print(f'{os.path.getsize(p) // 1024:6d} KB  {f}  {Image.open(p).size}')
