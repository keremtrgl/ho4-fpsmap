"""One command after a Hearts of Iron IV patch.

    python -I tools/patch_check.py [--game DIR] [--install]

1. Compares every vanilla file FPS Map is built from (tools/vanilla_manifest.json)
   with the installed game and reports what the patch changed: text diffs as
   +/- line counts, textures as old -> new size/mips, removed files.
2. Rebuilds fps_map/ and fps_map_colorblind/ from the current game.
   build.py stops with a clear message if one of the mod's edits no longer
   applies to the new vanilla file.
3. Verifies both outputs (checksum safety, texture layouts, every vanilla
   arrow/shader definition kept).
4. --install copies both mods into Documents/Paradox Interactive/Hearts of Iron IV/mod.

The report is also written to tools/patch_report.txt. Exit code 0 means the
mod is ready to upload.
"""
import difflib, hashlib, json, os, re, shutil, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'original_2404689961')
OUT = os.path.join(ROOT, 'fps_map')
OUT_CB = OUT + '_colorblind'
SNAPSHOT = os.path.join(HERE, 'vanilla_snapshot')  # text copies, for diffs
GAME = r'C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV'
if '--game' in sys.argv:
    GAME = sys.argv[sys.argv.index('--game') + 1]

lines = []


def say(s=''):
    print(s)
    lines.append(s)


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def dds_info(p):
    h = open(p, 'rb').read(128)
    hgt, wid = struct.unpack_from('<II', h, 12)
    return [wid, hgt, max(1, struct.unpack_from('<I', h, 28)[0])]


def text(p):
    return open(p, encoding='utf-8-sig', errors='replace').read().splitlines()


def run(*args):
    r = subprocess.run([sys.executable, '-I', *args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    for s in (r.stdout + r.stderr).strip().splitlines():
        say('    ' + s)
    return r.returncode == 0


manifest = json.load(open(os.path.join(HERE, 'vanilla_manifest.json'), encoding='utf-8'))
ver = re.search(r'rawVersion"\s*:\s*"([^"]+)"', open(os.path.join(GAME, 'launcher-settings.json'), encoding='utf-8-sig').read()).group(1)
say(f'FPS Map patch check: built for {manifest["game_version"]}, installed game {ver}')
say()

# ------------------------------------------------------------ 1. what changed
changed, removed = [], []
for rel, old in manifest['files'].items():
    p = os.path.join(GAME, rel)
    if not os.path.exists(p):
        removed.append(rel)
    elif sha(p) != old['sha256']:
        changed.append(rel)

if not changed and not removed:
    say(f'All {len(manifest["files"])} vanilla source files are unchanged.')
for rel in removed:
    say(f'  REMOVED   {rel}  (the mod overrides a file the game no longer has)')
for rel in changed:
    p = os.path.join(GAME, rel)
    if rel.endswith('.dds'):
        old, new = manifest['files'][rel].get('dds'), dds_info(p)
        what = f'texture {old[0]}x{old[1]} {old[2]} mips -> {new[0]}x{new[1]} {new[2]} mips' if old != new else 'texture art only'
    elif os.path.exists(os.path.join(SNAPSHOT, rel)):
        d = list(difflib.unified_diff(text(os.path.join(SNAPSHOT, rel)), text(p), lineterm='', n=0))
        what = f'+{sum(l.startswith("+") and not l.startswith("+++") for l in d)} ' \
               f'-{sum(l.startswith("-") and not l.startswith("---") for l in d)} lines'
    else:
        what = 'content changed'
    say(f'  CHANGED   {rel}  ({what})')
say()

# ------------------------------------------------------------ 2. rebuild
say('Rebuilding fps_map and fps_map_colorblind ...')
ok = run(os.path.join(HERE, 'build.py'), SRC, GAME, OUT)
say()

# ------------------------------------------------------------ 3. verify
if ok:
    say('Verifying fps_map ...')
    ok = run(os.path.join(HERE, 'verify.py'), OUT, GAME)
    say('Verifying fps_map_colorblind ...')
    main = open(os.path.join(OUT, 'gfx/maparrows/maparrows.txt'), encoding='utf-8').read()
    cb = open(os.path.join(OUT_CB, 'gfx/maparrows/maparrows.txt'), encoding='utf-8').read()
    strip = lambda t: re.sub(r'colors\s*=\s*\{.*?\n\}\n', '', t, count=1, flags=re.S)
    count = lambda t: len(re.findall(r'leader_group\s*=', t))
    if strip(main) != strip(cb) or count(main) != count(cb):
        say('    PROBLEM: colour-blind maparrows.txt differs from FPS Map outside the palette')
        ok = False
    else:
        say(f'    identical to FPS Map except the {count(cb)} leader_group colours')
    ok = run(os.path.join(HERE, 'verify.py'), OUT_CB, GAME, '--addon') and ok
    say('Verifying fps_map_calmwater ...')
    ok = run(os.path.join(HERE, 'verify.py'), OUT + '_calmwater', GAME, '--addon') and ok
    w = open(os.path.join(OUT + '_calmwater', 'gfx/FX/pdxwater.shader'), encoding='utf-8-sig').read().splitlines()
    v = open(os.path.join(GAME, 'gfx/FX/pdxwater.shader'), encoding='utf-8-sig').read().splitlines()
    extra = [l for l in w if l not in v]
    if len(w) != len(v) + 1 or len(extra) != 1 or 'specularLight *=' not in extra[0]:
        say('    PROBLEM: pdxwater.shader differs from vanilla by more than the glare line')
        ok = False
    else:
        say(f'    pdxwater.shader = vanilla + 1 line: {extra[0].strip()}')
    say()

# Keep text copies of the vanilla files for the next patch's line diffs.
if ok:
    shutil.rmtree(SNAPSHOT, ignore_errors=True)
    for rel in json.load(open(os.path.join(HERE, 'vanilla_manifest.json'), encoding='utf-8'))['files']:
        if not rel.endswith('.dds'):
            dst = os.path.join(SNAPSHOT, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(GAME, rel), dst)

# ------------------------------------------------------------ 4. install
if ok and '--install' in sys.argv:
    mods = os.path.join(os.path.expanduser('~'), 'Documents', 'Paradox Interactive', 'Hearts of Iron IV', 'mod')
    for src, folder in ((OUT, 'fps_map_updated'), (OUT_CB, 'fps_map_colorblind'), (OUT + '_calmwater', 'fps_map_calmwater')):
        dst = os.path.join(mods, folder)
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst)
        desc = open(os.path.join(src, 'descriptor.mod'), encoding='utf-8').read()
        with open(os.path.join(mods, folder + '.mod'), 'w', encoding='utf-8', newline='') as f:
            f.write(desc + f'path="{dst.replace(os.sep, "/")}"\n')
        say(f'Installed {folder}')
    say()

say('Checking the user folder for overrides (Nudger leftovers etc.) ...')
run(os.path.join(HERE, 'userdir_check.py'), '--game', GAME)  # warning only
say()

say('RESULT: ready to upload' if ok else 'RESULT: FAILED - see messages above')
with open(os.path.join(HERE, 'patch_report.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
sys.exit(0 if ok else 1)
