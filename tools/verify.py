"""Check a built FPS Map mod against the installed game.

Usage: python -I verify.py <mod dir> <game dir>
Exits non-zero on any problem.
"""
import os, re, struct, sys

MOD, GAME = sys.argv[1], sys.argv[2]
problems = []


def rel_files(root):
    for d, _, fs in os.walk(root):
        for f in fs:
            yield os.path.relpath(os.path.join(d, f), root).replace('\\', '/')


def dds(p):
    h = open(p, 'rb').read(128)
    if h[:4] != b'DDS ':
        return None
    hgt, wid = struct.unpack_from('<II', h, 12)
    return wid, hgt, max(1, struct.unpack_from('<I', h, 28)[0]), struct.unpack_from('<I', h, 112)[0] & 0xFE00


# 1. Checksum: Ironman achievements and multiplayer need the vanilla checksum.
manifest = open(os.path.join(GAME, 'checksum_manifest.txt'), encoding='utf-8-sig').read()
rules = re.findall(r'name\s*=\s*(\S+)\s+sub_directories\s*=\s*\w+\s+file_extension\s*=\s*(\S+)', manifest)
for rel in rel_files(MOD):
    for d, ext in rules:
        if rel.startswith(d + '/') and rel.lower().endswith(ext.lower()):
            problems.append(f'checksummed file (breaks Ironman/MP checksum): {rel}')

# 2. Every texture overrides a vanilla texture with the same size, mips and type.
for rel in rel_files(MOD):
    if not rel.lower().endswith('.dds'):
        continue
    v = os.path.join(GAME, rel)
    m = dds(os.path.join(MOD, rel))
    if m is None:
        problems.append(f'not a DDS: {rel}')
    elif not os.path.exists(v):
        problems.append(f'overrides nothing (dead file): {rel}')
    elif not rel.startswith('gfx/maparrows/') and rel != 'map/terrain/reflection.dds' and m != dds(v):
        # map arrow textures are UV-mapped, so their size is free; the black
        # reflection cube is checked on its own below
        problems.append(f'texture layout {m} != vanilla {dds(v)}: {rel}')

# 3. Text overrides keep every vanilla definition.
for rel in [r for r in ['gfx/maparrows/maparrows.txt'] if os.path.exists(os.path.join(MOD, r))]:
    a = open(os.path.join(GAME, rel), encoding='utf-8-sig').read()
    b = open(os.path.join(MOD, rel), encoding='utf-8-sig').read()
    names = lambda t: sorted(re.findall(r'name\s*=\s*"([^"]+)"', t))
    if b.count('{') != b.count('}'):
        problems.append(f'unbalanced braces: {rel}')
    if names(a) != names(b):
        problems.append(f'definitions differ from vanilla: {rel}: {set(names(a)) ^ set(names(b))}')

for rel in [r for r in rel_files(MOD) if r.endswith('.asset')]:
    a = open(os.path.join(GAME, rel), encoding='utf-8-sig').read()
    b = open(os.path.join(MOD, rel), encoding='utf-8-sig').read()
    if b.count('{') != b.count('}') or a.count('subsystem') != b.count('subsystem'):
        problems.append(f'particle structure differs from vanilla: {rel}')

ADDON = '--addon' in sys.argv  # add-ons ship only some of FPS Map's files
for rel in [r for r in rel_files(MOD) if r.endswith(('.shader', '.fxh'))]:
    a = open(os.path.join(GAME, rel), encoding='utf-8-sig').read()
    b = open(os.path.join(MOD, rel), encoding='utf-8-sig').read()
    for kw in ('Effect', 'DepthStencilState', 'BlendState', 'ConstantBuffer', 'static const'):
        ra = re.findall(rf'^[ \t]*{kw}\b.*$', a, re.M)
        rb = re.findall(rf'^[ \t]*{kw}\b.*$', b, re.M)
        if len(ra) != len(rb):
            problems.append(f'{rel}: {kw} count {len(rb)} != vanilla {len(ra)}')
    if b.count('{') != b.count('}'):
        problems.append(f'unbalanced braces: {rel}')

# 4. The reflection cube map is a real cube map, fully black.
p = os.path.join(MOD, 'map/terrain/reflection.dds')
if ADDON and not os.path.exists(p):
    pass
elif dds(p)[3] != 0xFE00:
    problems.append('reflection.dds is not a 6-face cube map')
if os.path.exists(p):
    d = open(p, 'rb').read()
    if any(d[i] or d[i + 1] or d[i + 2] for i in range(128, len(d), 4)):
        problems.append('reflection.dds is not black')
    h, w = struct.unpack_from('<II', d, 12)
    mips = struct.unpack_from('<I', d, 28)[0]
    face = sum(max(1, w >> i) * max(1, h >> i) * 4 for i in range(max(mips, 1)))
    if w != h or len(d) != 128 + 6 * face:
        problems.append('reflection.dds: faces not square or data size wrong')
elif not ADDON:
    problems.append('reflection.dds missing')

for p in problems:
    print('PROBLEM:', p)
print(f'{len(list(rel_files(MOD)))} files checked, {len(problems)} problems')
sys.exit(1 if problems else 0)
