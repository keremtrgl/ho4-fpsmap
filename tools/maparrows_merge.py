"""Port the mod's #SVA edits in maparrows.txt onto the current vanilla file.

Usage: arrows.py <vanilla maparrows.txt> <mod maparrows.txt> [out]
Without [out] it only reports.
"""
import re, sys
from collections import Counter

van_p, mod_p = sys.argv[1], sys.argv[2]
out_p = sys.argv[3] if len(sys.argv) > 3 else None
van = open(van_p, encoding='utf-8-sig').read().split('\n')
mod = open(mod_p, encoding='utf-8-sig').read().split('\n')

def blocks(lines):
    """Top-level blocks: list of (kind, name, start, end) with line indices (end inclusive)."""
    res, depth, start, kind = [], 0, None, None
    for i, ln in enumerate(lines):
        code = ln.split('#', 1)[0]
        if depth == 0:
            m = re.match(r'\s*(\w+)\s*=\s*\{', code)
            if m:
                start, kind = i, m.group(1)
        depth += code.count('{') - code.count('}')
        if depth == 0 and start is not None:
            name = None
            for j in range(start, i + 1):
                m = re.match(r'\s*name\s*=\s*"([^"]+)"', lines[j])
                if m:
                    name = m.group(1)
                    break
            res.append((kind, name, start, i))
            start = None
    return res

vb, mb = blocks(van), blocks(mod)
vmap = {(k, n): (s, e) for k, n, s, e in vb}
mmap = {(k, n): (s, e) for k, n, s, e in mb}

print('vanilla-only blocks:', [n for (k, n) in vmap if (k, n) not in mmap])
print('mod-only blocks    :', [n for (k, n) in mmap if (k, n) not in vmap])

# colors: is the mod's leader_group list a pure reordering of vanilla's?
def colors(lines, bm):
    s, e = bm[('colors', None)]
    return s, e, [l.strip() for l in lines[s:e + 1] if 'leader_group' in l]
vs, ve, vc = colors(van, vmap)
ms, me, mc = colors(mod, mmap)
print('colors reorder only:', Counter(vc) == Counter(mc), len(vc), len(mc))

key_re = re.compile(r'^(\s*)(\w+)\s*=')
patched = list(van)
for (k, n), (s, e) in mmap.items():
    sva = [l for l in mod[s:e + 1] if 'SVA' in l]
    if not sva or (k, n) not in vmap:
        continue
    vs_, ve_ = vmap[(k, n)]
    for l in sva:
        key = key_re.match(l).group(2)
        hits = [i for i in range(vs_, ve_ + 1) if key_re.match(patched[i]) and key_re.match(patched[i]).group(2) == key]
        assert len(hits) == 1, (n, key, hits)
        print(f'  {k} {n}: {patched[hits[0]].strip()}  ->  {l.strip()}')
        patched[hits[0]] = l.rstrip('\r')

if Counter(vc) == Counter(mc):
    mod_colors = [l.rstrip('\r') for l in mod[ms:me + 1]]
    patched[vs:ve + 1] = mod_colors

if out_p:
    with open(out_p, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(patched))
    print('written', out_p)
