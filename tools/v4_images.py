"""Workshop images for 1.19.4.0-4 from the in-game test screenshots.

    python -I tools/v4_images.py

Inputs (test/): snow_after/run_hoi4_4.png (fog, 1.19.4.0-3), v4_all/hoi4_4.png
(fog, -4), v4_mainonly/hoi4_3.png (water without Calm Water), v4_all/hoi4_6.png
(water with Calm Water, offset dx=34 dy=21 measured on land), v4_all/hoi4_5.png
(production screen with the colour-blind add-on), workshop/images/indicators_compare.png.
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = lambda *p: os.path.join(ROOT, 'test', *p)
OUT = os.path.join(ROOT, 'workshop', 'images')
GOLD, INK, WHITE = (226, 186, 92), (14, 17, 22), (240, 240, 236)


def font(size, bold=True):
    f = ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf', size)
    f.set_variation_by_name('Bold' if bold else 'Regular')
    return f


def tag(d, text, xy, anchor):
    f = font(30)
    l, t, r, b = d.textbbox(xy, text, font=f, anchor=anchor)
    d.rounded_rectangle((l - 14, t - 9, r + 14, b + 11), 8, fill=(*INK, 215), outline=GOLD, width=2)
    d.text(xy, text, font=f, fill=WHITE, anchor=anchor)


def pair(before, after, title, subtitle, left, right, out):
    """Two equal crops side by side, labelled, with a caption band."""
    w = 960
    a = before.resize((w, round(before.height * w / before.width)), Image.LANCZOS)
    b = after.resize(a.size, Image.LANCZOS)
    img = Image.new('RGB', (w * 2 + 8, a.height + 150), INK)
    img.paste(a, (0, 0))
    img.paste(b, (w + 8, 0))
    d = ImageDraw.Draw(img, 'RGBA')
    tag(d, left, (24, 24), 'la')
    tag(d, right, (w + 32, 24), 'la')
    d.text((40, a.height + 62), title, font=font(46), fill=GOLD, anchor='ls')
    d.text((42, a.height + 112), subtitle, font=font(25, False), fill=WHITE, anchor='ls')
    img.save(os.path.join(OUT, out), optimize=True)
    print(out, img.size)


# fog of war: same frame (start camera, fixed route), Prague-Liberec region
box = (0, 90, 1180, 900)
pair(Image.open(T('snow_after', 'run_hoi4_4.png')).convert('RGB').crop(box),
     Image.open(T('v4_all', 'hoi4_4.png')).convert('RGB').crop(box),
     'Calmer fog of war up close',
     'Same place and day. Fog stays where it was and just as strong - only the glaring white wisps became a soft grey that drifts slower.',
     'BEFORE  ·  1.19.4.0-3', 'AFTER  ·  1.19.4.0-4', '09_fog_of_war.png')

# calm water: align the two frames (measured on land), crop around the glare
dx, dy = 34, 21
box = (420, 330, 1500, 930)
pair(Image.open(T('v4_mainonly', 'hoi4_3.png')).convert('RGB').crop(box),
     Image.open(T('v4_all', 'hoi4_6.png')).convert('RGB').crop((box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)),
     'Calm Water add-on: softer sun glare',
     'Same camera. The bright sun spot on the sea is toned down; water colour, waves, ice and borders are unchanged.',
     'FPS MAP', 'FPS MAP + CALM WATER', '10_calm_water.png')

# colour-blind indicators: measured swatches + the real production screen
sw = Image.open(os.path.join(OUT, 'indicators_compare.png')).convert('RGB')
prod = Image.open(T('v4_all', 'hoi4_5.png')).convert('RGB').crop((0, 80, 600, 1000))
prod = prod.resize((round(prod.width * sw.height / prod.height), sw.height), Image.LANCZOS)
img = Image.new('RGB', (sw.width + prod.width + 16, sw.height + 80), INK)
img.paste(sw, (0, 0))
img.paste(prod, (sw.width + 16, 0))
d = ImageDraw.Draw(img)
d.text((sw.width + 16 + prod.width // 2, sw.height + 40), 'In game: production bars blue',
       font=font(24, False), fill=GOLD, anchor='mm')
d.text((30, sw.height + 40), 'Colour-blind add-on - worst-case difference for deuteranopia: 3.4 -> 27.7 (CIEDE2000)',
       font=font(24, False), fill=WHITE, anchor='lm')
img.save(os.path.join(OUT, '11_colorblind_indicators.png'), optimize=True)
print('11_colorblind_indicators.png', img.size)
