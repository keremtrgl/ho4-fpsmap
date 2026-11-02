"""Compatibility report: FPS Map vs other installed mods.

    python -I tools/conflicts.py [--game DIR] [extra mod dirs...]

Scans every mod registered in Documents/Paradox Interactive/Hearts of Iron IV/mod
(plus any extra dirs). Files both mods ship are classified, assuming FPS Map
loads AFTER the other mod:
  * VANILLA-COPY - their text file equals vanilla (ignoring whitespace): safe
  * ART          - texture with the same layout: only decides whose art shows
  * RESOLUTION   - texture with the same aspect ratio at another resolution
                   (same frames, scaled): safe
  * LAYOUT       - texture with a different aspect ratio: sprite frames break
  * CUBEMAP      - ours is a valid cube map where vanilla has one: safe
  * EDITED       - their text/shader file has real changes FPS Map would hide
and also:
  * WIPE    - a replace_path that removes a folder FPS Map relies on
  * FRAMES  - they redefine a sprite FPS Map retextures with another frame
              count, without shipping their own texture
  * RELATED - shaders/arrow files that interact with FPS Map, no direct overlap
Writes workshop/compatibility.md. Exit code 1 if any mod has a real conflict.
"""
import os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# Each of our mods is checked on its own, so a conflict names the culprit.
OUR_MODS = [('FPS Map', 'fps_map'), ('Colour-blind Add-on', 'fps_map_colorblind'),
            ('Calm Water Add-on', 'fps_map_calmwater')]
OURS = [os.path.join(ROOT, folder) for _, folder in OUR_MODS]
# Conflicts we document instead of fixing (description says "don't combine").
KNOWN = {('fps_map_calmwater', 'Millennium Dawn')}
GAME = r'C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV'
args = sys.argv[1:]
if '--game' in args:
    i = args.index('--game')
    GAME = args[i + 1]
    del args[i:i + 2]
DOCS = os.path.join(os.path.expanduser('~'), 'Documents', 'Paradox Interactive', 'Hearts of Iron IV', 'mod')
WORKSHOP = os.path.join(os.path.dirname(os.path.dirname(GAME)), 'workshop', 'content', '394360')
RELATED_DIRS = ('gfx/FX/', 'gfx/maparrows/', 'map/terrain/')


def rel_files(root):
    for d, _, fs in os.walk(root):
        for f in fs:
            yield os.path.relpath(os.path.join(d, f), root).replace('\\', '/')


def dds_size(p):
    h = open(p, 'rb').read(20)
    return struct.unpack_from('<II', h, 12)[::-1] if h[:4] == b'DDS ' else None


def is_cube(p):
    h = open(p, 'rb').read(128)
    return h[:4] == b'DDS ' and bool(struct.unpack_from('<I', h, 112)[0] & 0x200)


def squash(p):
    return re.sub(r'\s+', '', open(p, encoding='utf-8-sig', errors='replace').read())


def classify(rel, theirs_root, ours_root, their_frames):
    """Kind of overlap, assuming FPS Map loads after the other mod."""
    t, o, v = os.path.join(theirs_root, rel), os.path.join(ours_root, rel), os.path.join(GAME, rel)
    if rel.endswith('.dds'):
        a, b = dds_size(t), dds_size(o)
        if a == b:
            return 'ART'
        # cube maps have no sprite frames; ours is the cube the game expects
        if os.path.exists(v) and is_cube(o) and is_cube(v):
            return 'CUBEMAP'
        if a and b and abs(a[0] / a[1] - b[0] / b[1]) < 0.01:
            return 'RESOLUTION'
        # ours keeps the layout the game's own definitions expect, and they did
        # not redefine the sprite for theirs: loading FPS Map last restores it
        if os.path.exists(v) and b == dds_size(v) and rel.lower() not in their_frames:
            return 'VANILLA-LAYOUT'
        return 'LAYOUT'
    if os.path.exists(v) and squash(t) == squash(v):
        return 'VANILLA-COPY'
    return 'EDITED'


SAFE = {'VANILLA-COPY', 'ART', 'RESOLUTION', 'VANILLA-LAYOUT', 'CUBEMAP'}


def descriptor(text):
    get = lambda k: (re.search(rf'^\s*{k}\s*=\s*"([^"]*)"', text, re.M) or [None, None])[1]
    return {'name': get('name'), 'path': get('path'), 'id': get('remote_file_id'),
            'replace': re.findall(r'^\s*replace_path\s*=\s*"([^"]+)"', text, re.M)}


def frames(root):
    """texture path -> {frame counts} from every .gfx under root/interface."""
    out = {}
    for d, _, fs in os.walk(os.path.join(root, 'interface')):
        for f in fs:
            if not f.endswith('.gfx'):
                continue
            t = open(os.path.join(d, f), encoding='utf-8-sig', errors='replace').read()
            for m in re.finditer(r'\{([^{}]*texture[fF]ile\d?\s*=\s*"[^"]+"[^{}]*)\}', t):
                tf = re.search(r'texture[fF]ile\d?\s*=\s*"([^"]+)"', m.group(1)).group(1).replace('\\', '/').lower()
                fr = re.search(r'noOfFrames\s*=\s*(\d+)', m.group(1))
                out.setdefault(tf, set()).add(int(fr.group(1)) if fr else 1)
    return out


vanilla_frames = frames(GAME)

mods = []
for f in sorted(os.listdir(DOCS)) if os.path.isdir(DOCS) else []:
    if not f.endswith('.mod'):
        continue
    d = descriptor(open(os.path.join(DOCS, f), encoding='utf-8-sig', errors='replace').read())
    path = d['path'] if d['path'] and os.path.isdir(d['path']) else None
    if not path and d['id'] and os.path.isdir(os.path.join(WORKSHOP, d['id'])):
        path = os.path.join(WORKSHOP, d['id'])
    ours_ws = (d['name'] or '').startswith('FPS Map') or d['id'] in ('3828926440', '3828959483')  # our own items
    if path and not ours_ws and os.path.abspath(path) not in map(os.path.abspath, OURS) and 'fps_map' not in os.path.basename(path):
        inner = os.path.join(path, 'descriptor.mod')
        if os.path.exists(inner):
            d['replace'] = d['replace'] or descriptor(open(inner, encoding='utf-8-sig', errors='replace').read())['replace']
        mods.append((d['name'] or f, path, d['replace']))
for extra in args:
    inner = os.path.join(extra, 'descriptor.mod')
    d = descriptor(open(inner, encoding='utf-8-sig', errors='replace').read()) if os.path.exists(inner) else {'name': extra, 'replace': []}
    mods.append((d['name'] or extra, extra, d['replace']))

md = ['# FPS Map — compatibility report', '',
      'Generated by `tools/conflicts.py`. Load FPS Map **after** a mod to keep FPS Map\'s version of an OVERRIDE file, '
      '**before** it to keep the other mod\'s.', '']
worst = 0
scans = []
for label, folder in OUR_MODS:
    root = os.path.join(ROOT, folder)
    if not os.path.isdir(root):
        continue
    ours = {rel: folder for rel in rel_files(root) if rel not in ('descriptor.mod', 'thumbnail.png')}
    scans.append((label, folder, ours, {os.path.dirname(r) for r in ours}))

for label, folder, ours, our_dirs in scans:
  print(f'=== {label}')
  md += [f'# {label}', '']
  for name, path, replace in mods:
    theirs = set(rel_files(path))
    their_frames = frames(path)
    overlap = {}
    for r in sorted(theirs & set(ours)):
        overlap.setdefault(classify(r, path, os.path.join(ROOT, ours[r]), their_frames), []).append(r)
    wipes = sorted(p for p in replace if any(d == p or d.startswith(p.rstrip('/') + '/') for d in our_dirs))
    frame_issues = sorted(f'{tex}: vanilla {sorted(vanilla_frames.get(tex, {1}))} -> theirs {sorted(fr)}'
                          for tex, fr in their_frames.items()
                          if tex in ours and tex not in theirs and fr != vanilla_frames.get(tex, {1}))
    related = sorted(r for r in theirs if r.startswith(RELATED_DIRS) and r not in ours)
    real = [k for k in overlap if k not in SAFE]
    known = any(folder == f and name.startswith(n) for f, n in KNOWN)
    if (real or wipes or frame_issues) and known:
        level, advice = 'KNOWN', "documented conflict - the description says not to combine them"
    elif real or wipes or frame_issues:
        level, advice = 'CONFLICT', 'needs a compatibility patch or a manual choice (see below)'
    elif overlap:
        level, advice = 'COMPATIBLE', f'load FPS Map **after** {name}'
    else:
        level, advice = 'COMPATIBLE', 'any load order'
    worst = max(worst, level == 'CONFLICT')
    summary = ', '.join(f'{len(v)} {k}' for k, v in sorted(overlap.items())) or 'no shared files'
    print(f'{level:10} {name}  ({len(theirs)} files; {summary})')
    md += [f'## {name}', '', f'**{level}** — {advice}. {len(theirs)} files scanned; shared: {summary}.', '']
    groups = [(f'{k} (shared file)', v) for k, v in sorted(overlap.items(), key=lambda kv: kv[0] in SAFE)]
    groups += [('WIPE (replace_path removes a folder FPS Map uses)', wipes),
               ('FRAMES (sprite redefined with a different frame count)', frame_issues),
               ('RELATED (interacts with FPS Map, no direct overlap)', related)]
    for title, items in groups:
        if items:
            md.append(f'- {title}:')
            md += [f'  - `{i}`' for i in items[:40]] + ([f'  - … {len(items) - 40} more'] if len(items) > 40 else [])
            if not title.split()[0] in SAFE | {'RELATED'}:
                for i in items[:12]:
                    print(f'           {title.split()[0]:12} {i}')
    md.append('')

out = os.path.join(ROOT, 'workshop', 'compatibility.md')
with open(out, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md))
print(f'\n{len(mods)} mods scanned -> {out}')
sys.exit(1 if worst else 0)
