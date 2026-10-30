"""Colour-blind-friendly army arrow palette for FPS Map.

The game colours each army's plan arrows with the `leader_group` entries of
gfx/maparrows/maparrows.txt, in order. This module generates a replacement list
where every colour is as distinct as possible from all earlier ones under normal
vision AND simulated protanopia, deuteranopia and tritanopia:

  * seeded with the Okabe-Ito colour-blind-safe set (black dropped: invisible
    on the dark map),
  * then greedy farthest-point selection over a candidate grid, using CIEDE2000
    on Machado et al. (2009) full-severity simulations,
  * lightness kept in L* 45..90 so arrows stay readable on terrain and on
    pastel country colours.

Usage:
    python -I colorblind.py report <maparrows.txt>        compare palettes
    (build.py imports palette() and apply())
"""
import re, sys
import numpy as np

OKABE_ITO = ['E69F00', '56B4E9', '009E73', 'F0E442', '0072B2', 'D55E00', 'CC79A7']

# Machado, Oliveira & Fernandes 2009, severity 1.0, applied to linear RGB.
CVD = {
    'normal': np.eye(3),
    'protan': np.array([[0.152286, 1.052583, -0.204868],
                        [0.114503, 0.786281, 0.099216],
                        [-0.003882, -0.048116, 1.051998]]),
    'deutan': np.array([[0.367322, 0.860646, -0.227968],
                        [0.280085, 0.672501, 0.047413],
                        [-0.011820, 0.042940, 0.968881]]),
    'tritan': np.array([[1.255528, -0.076749, -0.178779],
                        [-0.078411, 0.930809, 0.147602],
                        [0.004733, 0.691367, 0.303900]]),
}


def _lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lab(rgb, matrix=np.eye(3)):
    """sRGB (N,3 in 0..1) -> CIELAB (N,3), through an optional CVD matrix."""
    lin = np.clip(_lin(np.asarray(rgb, float)) @ matrix.T, 0, 1)
    xyz = lin @ np.array([[0.4124564, 0.3575761, 0.1804375],
                          [0.2126729, 0.7151522, 0.0721750],
                          [0.0193339, 0.1191920, 0.9503041]]).T
    xyz /= np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], 1)


def de2000(a, b):
    """CIEDE2000 between Lab rows of a (N,3) and one Lab colour b (3,)."""
    L1, a1, b1 = a[:, 0], a[:, 1], a[:, 2]
    L2, a2, b2 = b
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cm = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dh = h2p - h1p
    dh = np.where(C1p * C2p == 0, 0, np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh)))
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh / 2))
    Lpm, Cpm = (L1 + L2) / 2, (C1p + C2p) / 2
    hs = h1p + h2p
    hpm = np.where(C1p * C2p == 0, hs,
                   np.where(np.abs(h1p - h2p) <= 180, hs / 2, np.where(hs < 360, (hs + 360) / 2, (hs - 360) / 2)))
    T = (1 - 0.17 * np.cos(np.radians(hpm - 30)) + 0.24 * np.cos(np.radians(2 * hpm))
         + 0.32 * np.cos(np.radians(3 * hpm + 6)) - 0.20 * np.cos(np.radians(4 * hpm - 63)))
    dtheta = 30 * np.exp(-(((hpm - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cpm ** 7 / (Cpm ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lpm - 50) ** 2 / np.sqrt(20 + (Lpm - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cpm, 1 + 0.015 * Cpm * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def palette(n=256):
    """Greedy farthest-point palette, worst case over all four vision types."""
    g = np.linspace(0, 1, 18)
    cand = np.array(np.meshgrid(g, g, g, indexing='ij')).reshape(3, -1).T
    L = lab(cand)
    keep = (L[:, 0] >= 45) & (L[:, 0] <= 90) & (np.hypot(L[:, 1], L[:, 2]) >= 20)
    cand = cand[keep]
    labs = {k: lab(cand, m) for k, m in CVD.items()}
    mind = np.full(len(cand), np.inf)
    chosen = []

    def take(rgb):
        chosen.append(rgb)
        for k, m in CVD.items():
            np.minimum(mind, de2000(labs[k], lab(rgb[None], m)[0]), out=mind)

    for h in OKABE_ITO:
        take(np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]))
    while len(chosen) < n:
        take(cand[int(np.argmax(mind))])
    return np.array(chosen[:n])


def min_separation(rgb, first):
    """Smallest pairwise CIEDE2000 among the first `first` colours, per vision type."""
    out = {}
    for k, m in CVD.items():
        L = lab(rgb[:first], m)
        out[k] = min(de2000(L[:i], L[i]).min() for i in range(1, len(L)))
    return out


# ------------------------------------------------------------------ indicators
# Red/green status indicators (winning/losing, good/bad). Green -> blue,
# red -> orange (the Okabe-Ito pair that stays distinct for every CVD type).
INDICATORS = [f'gfx/interface/{p}.dds' for p in (
    'landcombat_attacker_progress', 'landcombat_defender_progress',
    'navalcombat/bar_progress_win', 'navalcombat/bar_progress_win_157x14',
    'navalcombat/bar_progress_loose', 'navalcombat/bar_progress_loose_157x14',
    'strategicair/progress_good', 'strategicair/progress_bad',
    'strategicnavy/progress_good', 'strategicnavy/progress_bad',
    'naval_mine_progress_good', 'naval_mine_progress_bad',
    'mapicons/naval_mission_dominance_anim_arrows_good', 'mapicons/naval_mission_dominance_anim_arrows_bad',
    'decisionview/on_map_progress_bar_good', 'decisionview/on_map_progress_bar_bad',
    'surrender_progress', 'surrender_progress_bg',
    'warscore_progressbar', 'warscore_progressbar_small', 'warscore_progressbar_bg',
    'prod_progress_bar2', 'prod_progress_bar2_red',
)]
BLUE_HUE, ORANGE_HUE = 205.0, 32.0  # Okabe-Ito blue / orange


def _band(h, lo, hi, feather=12.0):
    """1 inside [lo, hi] degrees (wrapping), fading to 0 over `feather`."""
    d = np.minimum(np.abs((h - lo + 180) % 360 - 180), np.abs((h - hi + 180) % 360 - 180))
    inside = ((h - lo) % 360) <= ((hi - lo) % 360)
    return np.where(inside, 1.0, np.clip(1 - d / feather, 0, 1))


def recolor(rgba):
    """Hue-remap an RGBA float array (0..1): greens to blue, reds to orange.
    Value, alpha and low-saturation pixels (frames, text, shading) are kept."""
    rgb = rgba[..., :3]
    mx, mn = rgb.max(-1), rgb.min(-1)
    c = mx - mn
    s = np.where(mx > 0, c / np.maximum(mx, 1e-9), 0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.where(c == 0, 0,
                 np.where(mx == r, ((g - b) / np.maximum(c, 1e-9)) % 6,
                          np.where(mx == g, (b - r) / np.maximum(c, 1e-9) + 2, (r - g) / np.maximum(c, 1e-9) + 4))) * 60
    sat_w = np.clip((s - 0.15) / 0.15, 0, 1)
    wg = _band(h, 75, 165) * sat_w
    wr = _band(h, 335, 22) * sat_w
    # move hue along the short way round
    def toward(h, target, w):
        d = (target - h + 180) % 360 - 180
        return (h + d * w) % 360
    h2 = toward(toward(h, BLUE_HUE, wg), ORANGE_HUE, wr)
    v = mx * (1 + 0.12 * wg)  # blue reads darker than green at equal value
    v = np.clip(v, 0, 1)
    hh = h2 / 60
    i = np.floor(hh).astype(int) % 6
    f = hh - np.floor(hh)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    out = np.stack([np.choose(i, [v, q, p, p, t, v]), np.choose(i, [t, v, v, q, p, p]),
                    np.choose(i, [p, p, t, v, v, q])], -1)
    return np.concatenate([out, rgba[..., 3:4]], -1)


def mean_status_colour(rgba):
    """Mean colour of the saturated, opaque pixels (the indicator fill)."""
    rgb, a = rgba[..., :3], rgba[..., 3]
    mx, mn = rgb.max(-1), rgb.min(-1)
    m = (a > 0.5) & ((mx - mn) / np.maximum(mx, 1e-9) > 0.35)
    return rgb[m].mean(0) if m.any() else rgb[a > 0.5].mean(0)


COLORS_RE = re.compile(r'(colors\s*=\s*\{)(.*?)(\n\}\n)', re.S)


def read_leader_groups(text):
    block = COLORS_RE.search(text).group(2)
    return np.array([[float(x) for x in m.groups()] for m in
                     re.finditer(r'leader_group\s*=\s*\{\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)', block)])


def apply(text, rgb):
    """Replace the colors block of maparrows.txt with the given palette (same count)."""
    old = read_leader_groups(text)
    assert len(old) == len(rgb), (len(old), len(rgb))
    lines = ['\n\t# Should match LEADER_GROUP_MAX_SIZE in common defines',
             '\t# FPS Map colour-blind palette: Okabe-Ito first, then greedy CIEDE2000',
             '\t# separation under normal vision, protanopia, deuteranopia and tritanopia.',
             '\t# Earlier entries are the most distinct; the game assigns them first.']
    for i, (r, g, b) in enumerate(rgb):
        if i % 16 == 0:
            lines.append(f'\n\t# {i + 1}-{i + 16}')
        lines.append(f'\tleader_group = {{ {r:.2f} {g:.2f} {b:.2f} 1.0 }}')
    return COLORS_RE.sub(lambda m: m.group(1) + '\n'.join(lines) + m.group(3), text, count=1)


def report(text, rgb):
    old = read_leader_groups(text)
    rows = []
    for first in (8, 16, 32):
        a, b = min_separation(old, first), min_separation(rgb, first)
        for k in CVD:
            rows.append(f'first {first:>2} armies  {k:<7} worst dE2000  standard {a[k]:5.1f}  ->  colour-blind {b[k]:5.1f}')
    return '\n'.join(rows)


if __name__ == '__main__' and sys.argv[1] == 'report':
    t = open(sys.argv[2], encoding='utf-8-sig').read()
    print(report(t, palette(len(read_leader_groups(t)))))
