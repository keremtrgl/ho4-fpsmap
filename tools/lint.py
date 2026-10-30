"""Release lint for FPS Map: everything verify.py doesn't cover.

    python -I tools/lint.py [--game DIR]

Checks the built mods (fps_map, fps_map_colorblind) and the installed copies:
  * every text file: valid UTF-8, balanced braces, no mixed line endings
  * descriptor.mod: required keys, version matches build REVISION, Workshop id
  * thumbnail.png: square, under Steam's 1 MB limit
  * shader patches: every '// FPS Map' / '# FPS Map' edit present exactly where expected
  * installed copies in Documents/.../mod are byte-identical to the build
  * workshop texts: BBCode tags balanced, no leftover placeholders
Exit code 1 on any problem.
"""
import hashlib, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = r'C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV'
if '--game' in sys.argv:
    GAME = sys.argv[sys.argv.index('--game') + 1]
DOCS = os.path.join(os.path.expanduser('~'), 'Documents', 'Paradox Interactive', 'Hearts of Iron IV', 'mod')
MODS = {'fps_map': 'fps_map_updated', 'fps_map_colorblind': 'fps_map_colorblind', 'fps_map_calmwater': 'fps_map_calmwater'}
TEXT = ('.txt', '.fxh', '.shader', '.asset', '.mod', '.gfx', '.gui', '.lua')
problems, notes = [], []


def rel_files(root):
    for d, _, fs in os.walk(root):
        for f in fs:
            yield os.path.relpath(os.path.join(d, f), root).replace('\\', '/')


def strip_comments(t):
    return re.sub(r'#[^\n]*|//[^\n]*|/\*.*?\*/', '', t, flags=re.S)


revision = re.search(r'REVISION\s*=\s*(\d+)', open(os.path.join(HERE, 'build.py'), encoding='utf-8').read()).group(1)
game_ver = re.search(r'rawVersion"\s*:\s*"([^"]+)"', open(os.path.join(GAME, 'launcher-settings.json'), encoding='utf-8-sig').read()).group(1)

for src, installed in MODS.items():
    root = os.path.join(ROOT, src)
    files = list(rel_files(root))
    for rel in files:
        p = os.path.join(root, rel)
        if rel.endswith(TEXT):
            raw = open(p, 'rb').read()
            try:
                t = raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                problems.append(f'{src}/{rel}: not valid UTF-8')
                continue
            crlf, lf = t.count('\r\n'), t.count('\n') - t.count('\r\n')
            if crlf and lf:
                problems.append(f'{src}/{rel}: mixed line endings ({crlf} CRLF, {lf} LF)')
            s = strip_comments(t)
            if s.count('{') != s.count('}'):
                problems.append(f'{src}/{rel}: unbalanced braces ({s.count("{")} vs {s.count("}")})')
    # descriptor
    desc = open(os.path.join(root, 'descriptor.mod'), encoding='utf-8').read()
    for key in ('version', 'name', 'supported_version'):
        if not re.search(rf'^{key}\s*=', desc, re.M):
            problems.append(f'{src}/descriptor.mod: missing {key}')
    if not re.search(r'^remote_file_id\s*=', desc, re.M):
        notes.append(f'{src}: no remote_file_id yet (first upload creates a new Workshop item)')
    if not desc.isascii():
        problems.append(f'{src}/descriptor.mod: non-ASCII characters (launcher may mangle the title)')
    main_name = re.search(r'^name="([^"]+)"', open(os.path.join(ROOT, 'fps_map', 'descriptor.mod'), encoding='utf-8').read(), re.M).group(1)
    dep = re.search(r'dependencies\s*=\s*\{\s*"([^"]+)"', desc)
    if src != 'fps_map' and (not dep or dep.group(1) != main_name):
        problems.append(f'{src}/descriptor.mod: dependency must be exactly "{main_name}"')
    if f'version="{game_ver}-{revision}"' not in desc:
        problems.append(f'{src}/descriptor.mod: version is not {game_ver}-{revision}')
    # thumbnail
    th = os.path.join(root, 'thumbnail.png')
    if not os.path.exists(th):
        problems.append(f'{src}: thumbnail.png missing')
    else:
        from PIL import Image
        im = Image.open(th)
        if im.width != im.height or os.path.getsize(th) >= 1024 * 1024:
            problems.append(f'{src}: thumbnail {im.size} {os.path.getsize(th)} bytes (must be square, < 1 MB)')
    # installed copy identical to the build
    inst = os.path.join(DOCS, installed)
    if os.path.isdir(inst):
        sha = lambda q: hashlib.sha256(open(q, 'rb').read()).hexdigest()
        built, there = set(files), set(rel_files(inst))
        if built ^ there:
            problems.append(f'installed {installed}: file set differs from build: {sorted(built ^ there)[:5]}')
        for rel in built & there:
            if rel != 'descriptor.mod' and sha(os.path.join(root, rel)) != sha(os.path.join(inst, rel)):
                problems.append(f'installed {installed}/{rel}: differs from build')
        notes.append(f'installed {installed}: {len(built & there)} files match the build')
    notes.append(f'{src}: {len(files)} files linted')

# every documented edit is in place, exactly once per expected count
EXPECT = {
    'gfx/FX/constants.fxh': 8, 'gfx/FX/river.shader': 1, 'gfx/FX/maparrow.shader': 8,
    'gfx/FX/standardfuncsgfx.fxh': 1, 'gfx/maparrows/maparrows.txt': 14, 'gfx/FX/fow.fxh': 4,
}
for rel, n in EXPECT.items():
    t = open(os.path.join(ROOT, 'fps_map', rel), encoding='utf-8-sig').read()
    found = t.count('FPS Map')
    if found != n:
        problems.append(f'fps_map/{rel}: {found} FPS Map edits, expected {n}')
particles = [r for r in rel_files(os.path.join(ROOT, 'fps_map')) if r.endswith('.asset')]
for rel in particles:
    t = open(os.path.join(ROOT, 'fps_map', rel), encoding='utf-8-sig').read()
    v = open(os.path.join(GAME, rel), encoding='utf-8-sig').read()
    want = len(re.findall(r'^\s*(alpha|emission|max_amount)\s*=', v, re.M))
    if t.count('# FPS Map') != want:
        problems.append(f'fps_map/{rel}: {t.count("# FPS Map")} tuned lines, expected {want}')
notes.append(f'{len(particles)} weather particle files fully tuned')

# workshop texts
for f in os.listdir(os.path.join(ROOT, 'workshop')):
    if not f.endswith(('.bbcode', '.txt')):
        continue
    t = open(os.path.join(ROOT, 'workshop', f), encoding='utf-8').read()
    for tag in ('b', 'i', 'url', 'list', 'olist', 'table', 'tr', 'td', 'th', 'h1', 'h2'):
        o = len(re.findall(rf'\[{tag}(=[^\]]*)?\]', t))
        c = t.count(f'[/{tag}]')
        if o != c:
            problems.append(f'workshop/{f}: [{tag}] opened {o}x, closed {c}x')
    if re.search(r'TODO|XXX|\?\?\?|lorem|CALMWATER_ID', t, re.I):
        problems.append(f'workshop/{f}: placeholder text left')

for n in notes:
    print('  ok  ', n)
for p in problems:
    print('PROBLEM:', p)
print(f'lint: {len(problems)} problems')
sys.exit(1 if problems else 0)
