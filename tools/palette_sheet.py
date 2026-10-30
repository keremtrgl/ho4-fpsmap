"""Swatch sheet: first 32 army colours, standard vs colour-blind palette, under
normal vision and simulated protanopia / deuteranopia / tritanopia.

Usage: python -I palette_sheet.py <maparrows.txt> <out.png>
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import colorblind as cb

text = open(sys.argv[1], encoding='utf-8-sig').read()
std = cb.read_leader_groups(text)
new = cb.palette(len(std))
N, S, PAD = 32, 34, 24
INK, GOLD, WHITE = (14, 17, 22), (226, 186, 92), (240, 240, 236)
f = lambda s, b=True: ImageFont.truetype('C:/Windows/Fonts/' + ('segoeuib.ttf' if b else 'segoeui.ttf'), s)


def simulate(rgb, m):
    lin = np.clip(cb._lin(rgb) @ m.T, 0, 1)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)


names = {'normal': 'Normal vision', 'protan': 'Protanopia', 'deutan': 'Deuteranopia', 'tritan': 'Tritanopia'}
W = 220 + N * S + PAD
H = 110 + 4 * (2 * S + 60)
img = Image.new('RGB', (W, H), INK)
d = ImageDraw.Draw(img)
d.text((W // 2, 50), 'Army arrow colours — first 32 armies', font=f(40), fill=GOLD, anchor='mm')
y = 110
for k, m in cb.CVD.items():
    d.text((PAD, y), names[k], font=f(26), fill=WHITE)
    for row, (label, pal) in enumerate((('Standard', std), ('Colour-blind', new))):
        yy = y + 36 + row * (S + 6)
        d.text((PAD, yy + S // 2), label, font=f(20, False), fill=GOLD if row else WHITE, anchor='lm')
        for i, c in enumerate(simulate(pal[:N], m)):
            x = 200 + i * S
            d.rectangle((x, yy, x + S - 4, yy + S - 1), fill=tuple(int(v * 255 + .5) for v in c))
    y += 2 * S + 60
img.save(sys.argv[2], optimize=True)
print(sys.argv[2], img.size)
