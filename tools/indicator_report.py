"""Measure the colour-blind indicator recolour and render a comparison sheet.

    python -I tools/indicator_report.py <out.png>

For every good/bad indicator pair: CIEDE2000 difference between the two fill
colours, standard vs colour-blind add-on, under normal vision and simulated
protanopia / deuteranopia / tritanopia (Machado 2009).
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import colorblind as cb

GAME = r'C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV'
MAIN, ADDON = os.path.join(ROOT, 'fps_map'), os.path.join(ROOT, 'fps_map_colorblind')
PAIRS = [
    ('Land combat (attacker / defender)', 'landcombat_attacker_progress', 'landcombat_defender_progress'),
    ('Naval combat (winning / losing)', 'navalcombat/bar_progress_win', 'navalcombat/bar_progress_loose'),
    ('Air superiority (good / bad)', 'strategicair/progress_good', 'strategicair/progress_bad'),
    ('Naval region control (good / bad)', 'strategicnavy/progress_good', 'strategicnavy/progress_bad'),
    ('Naval mines (good / bad)', 'naval_mine_progress_good', 'naval_mine_progress_bad'),
    ('Naval dominance arrows (good / bad)', 'mapicons/naval_mission_dominance_anim_arrows_good', 'mapicons/naval_mission_dominance_anim_arrows_bad'),
    ('Decision progress on map (good / bad)', 'decisionview/on_map_progress_bar_good', 'decisionview/on_map_progress_bar_bad'),
    ('Surrender progress (fill / background)', 'surrender_progress', 'surrender_progress_bg'),
    ('Production line (ok / lacking)', 'prod_progress_bar2', 'prod_progress_bar2_red'),
]


def load(root, name):
    p = os.path.join(root, f'gfx/interface/{name}.dds')
    if not os.path.exists(p):
        p = os.path.join(GAME, f'gfx/interface/{name}.dds')
    return np.asarray(Image.open(p).convert('RGBA'), float) / 255


def de(c1, c2, m):
    return float(cb.de2000(cb.lab(c1[None], m), cb.lab(c2[None], m)[0])[0])


rows = []
for title, good, bad in PAIRS:
    std = (cb.mean_status_colour(load(MAIN, good)), cb.mean_status_colour(load(MAIN, bad)))
    new = (cb.mean_status_colour(load(ADDON, good)), cb.mean_status_colour(load(ADDON, bad)))
    rows.append((title, good, bad, std, new,
                 {k: (de(*std, m), de(*new, m)) for k, m in cb.CVD.items()}))

print(f'{"indicator":40} {"vision":7} {"standard":>8} {"add-on":>8}')
worst = {k: [99, 99] for k in cb.CVD}
for title, _, _, _, _, d in rows:
    for k, (a, b) in d.items():
        print(f'{title:40} {k:7} {a:8.1f} {b:8.1f}')
        worst[k] = [min(worst[k][0], a), min(worst[k][1], b)]
print()
for k, (a, b) in worst.items():
    print(f'WORST PAIR  {k:7} standard {a:5.1f}  ->  add-on {b:5.1f}')

# sheet: swatches of each pair, standard vs add-on, normal + deuteranopia
f = lambda s, b=True: ImageFont.truetype('C:/Windows/Fonts/' + ('segoeuib.ttf' if b else 'segoeui.ttf'), s)
INK, GOLD, WHITE = (14, 17, 22), (226, 186, 92), (240, 240, 236)


def sim(c, m):
    lin = np.clip(cb._lin(c[None]) @ m.T, 0, 1)[0]
    return tuple(int(v * 255 + .5) for v in np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055))


W, RH = 1500, 58
img = Image.new('RGB', (W, 150 + RH * len(rows) + 30), INK)
d = ImageDraw.Draw(img)
d.text((W // 2, 46), 'Red / green indicators  ->  blue / orange', font=f(40), fill=GOLD, anchor='mm')
cols = [('Standard', 'normal', 3), ('Standard', 'deutan', 3), ('Add-on', 'normal', 4), ('Add-on', 'deutan', 4)]
for j, (lab, vis, _) in enumerate(cols):
    d.text((560 + j * 230, 112), f'{lab} · {"Normal" if vis == "normal" else "Deuteranopia"}',
           font=f(18), fill=GOLD if lab == 'Add-on' else WHITE, anchor='mm')
for i, (title, _, _, std, new, dd) in enumerate(rows):
    y = 140 + i * RH
    d.text((30, y + 18), title, font=f(20, False), fill=WHITE, anchor='lm')
    for j, (lab, vis, _) in enumerate(cols):
        pair = std if lab == 'Standard' else new
        x = 470 + j * 230
        for k, c in enumerate(pair):
            d.rectangle((x + k * 90, y, x + k * 90 + 84, y + 38), fill=sim(c, cb.CVD[vis]))
img.save(sys.argv[1], optimize=True)
print(sys.argv[1], img.size)
