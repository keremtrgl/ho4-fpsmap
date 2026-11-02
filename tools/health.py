"""Quick health check: is FPS Map still working on this machine, and if not, why?

    python -I tools/health.py [--game DIR] [--userdir DIR] [--log FILE ...] [--notify]

Read-only and fast (no rebuild). Run it after a game update, after changing
a playset, or on a player's error.log from a bug report. Checks:

  GAME     installed game version and the vanilla files FPS Map is built from
           (tools/vanilla_manifest.json). A changed shader/arrow file means the
           mod may be stale: run patch_check.py --install.
  INSTALL  every installed copy of our mods (Workshop download and local copy)
           is identical to the repo build, so players get what was tested.
  PLAYSET  the last launched playset (dlc_load.json), in load order: which of
           FPS Map's files another mod hides, mods that must not be combined,
           and known load-order advice (Millennium Dawn, Globe Mod, ...).
  SAFETY   no FPS Map file is in a checksummed folder (Ironman/multiplayer).
  LOGS     error.log, graphics.log and system.log lines that mention a file
           FPS Map ships, a shader or the arrow definitions. --log adds files,
           e.g. a player's error.log attached to a comment.

--notify shows a Windows message box when something needs attention (for a
scheduled run after Steam updates). Writes tools/health_report.txt.
Exit code 1 on any FAIL, 0 otherwise (WARN does not fail).
"""
import hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = r'C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV'
args = sys.argv[1:]
if '--game' in args:
    GAME = args[args.index('--game') + 1]
EXTRA_LOGS = [args[i + 1] for i, a in enumerate(args) if a == '--log']
USER = os.path.join(os.path.expanduser('~'), 'Documents', 'Paradox Interactive', 'Hearts of Iron IV')
if '--userdir' in args:
    USER = args[args.index('--userdir') + 1]
WORKSHOP = os.path.join(os.path.dirname(os.path.dirname(GAME)), 'workshop', 'content', '394360')

OUR_MODS = [('FPS Map', 'fps_map'), ('Colour-blind Add-on', 'fps_map_colorblind'),
            ('Calm Water Add-on', 'fps_map_calmwater')]
MLECZ_ORIGINAL = '2404689961'
# Other mods we know, keyed by Workshop id: (name, FPS Map must load 'after'
# or 'before' them, why). The engine lets the mod loaded LAST win a file.
ADVICE = {
    '2777392649': ('Millennium Dawn', 'after',
                   'MD replaces constants.fxh; load FPS Map below it so the map style applies'),
    '3816496697': ('Globe Mod', 'before',
                   'Globe replaces maparrow/pdxmap/river shaders; load Globe below FPS Map so the globe works '
                   '(FPS Map then keeps everything except its arrow shading, far river snow and shallow seabed)'),
}
# (our add-on folder, their Workshop id): never combine, same water shader
NEVER = {('fps_map_calmwater', '2777392649'), ('fps_map_calmwater', '3816496697')}

results = []  # (level, section, message)


def say(level, section, msg):
    results.append((level, section, msg))


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def rel_files(root):
    for d, _, fs in os.walk(root):
        for f in fs:
            yield os.path.relpath(os.path.join(d, f), root).replace('\\', '/')


def descriptor(p):
    text = open(p, encoding='utf-8-sig', errors='replace').read()
    get = lambda k: (re.search(rf'^\s*{k}\s*=\s*"([^"]*)"', text, re.M) or [None, None])[1]
    return {k: get(k) for k in ('name', 'version', 'path', 'archive', 'remote_file_id')}


ours = {}  # folder -> {name, version, id, files: {rel: sha}}
for name, folder in OUR_MODS:
    root = os.path.join(ROOT, folder)
    if os.path.isdir(root):
        d = descriptor(os.path.join(root, 'descriptor.mod'))
        ours[folder] = {'title': name, 'name': d['name'], 'version': d['version'], 'id': d['remote_file_id'],
                        'files': {r: sha(os.path.join(root, r)) for r in rel_files(root)}}
main = ours['fps_map']

# ---------------------------------------------------------------- GAME
manifest = json.load(open(os.path.join(HERE, 'vanilla_manifest.json'), encoding='utf-8'))
settings = open(os.path.join(GAME, 'launcher-settings.json'), encoding='utf-8-sig').read()
game_ver = re.search(r'rawVersion"\s*:\s*"([^"]+)"', settings).group(1)
changed = [rel for rel, e in manifest['files'].items()
           if not os.path.exists(os.path.join(GAME, rel)) or sha(os.path.join(GAME, rel)) != e['sha256']]
if changed:
    risky = [r for r in changed if r.endswith(('.shader', '.fxh', '.txt', '.asset'))]
    say('FAIL' if risky else 'WARN', 'GAME',
        f'game {game_ver}, mod built for {manifest["game_version"]}: {len(changed)} vanilla source files changed '
        f'({", ".join((risky or changed)[:6])}{" ..." if len(changed) > 6 else ""}). '
        f'Run: python -I tools/patch_check.py --install')
else:
    note = '' if game_ver == manifest['game_version'] else f' (built on {manifest["game_version"]})'
    say('OK', 'GAME', f'game {game_ver}{note}: all {len(manifest["files"])} vanilla source files unchanged')

# ---------------------------------------------------------------- INSTALL
for folder, m in ours.items():
    places = []
    if m['id'] and os.path.isdir(os.path.join(WORKSHOP, m['id'])):
        places.append(('Workshop', os.path.join(WORKSHOP, m['id'])))
    for f in os.listdir(os.path.join(USER, 'mod')) if os.path.isdir(os.path.join(USER, 'mod')) else []:
        p = os.path.join(USER, 'mod', f)
        if f.endswith('.mod') and not f.startswith('ugc_'):
            d = descriptor(p)
            if d['name'] == m['name'] and d['path']:
                path = d['path'] if os.path.isabs(d['path']) else os.path.join(USER, d['path'])
                if os.path.isdir(path):
                    places.append(('local copy', path))
    if not places:
        say('OK', 'INSTALL', f'{m["title"]}: not installed here')
    for where, path in places:
        theirs = {r: sha(os.path.join(path, r)) for r in rel_files(path)}
        ver = descriptor(os.path.join(path, 'descriptor.mod'))['version'] if 'descriptor.mod' in theirs else '?'
        diff = sorted(r for r in set(theirs) | set(m['files'])
                      if r not in ('descriptor.mod', 'thumbnail.png') and theirs.get(r) != m['files'].get(r))
        if diff:
            say('WARN', 'INSTALL', f'{m["title"]} ({where}, {ver}) differs from the build {m["version"]} in '
                f'{len(diff)} files ({", ".join(diff[:4])}{" ..." if len(diff) > 4 else ""}): '
                f'Steam still downloading, or the build is newer than the upload')
        else:
            say('OK', 'INSTALL', f'{m["title"]} ({where}, {ver}) matches the build')

# ---------------------------------------------------------------- PLAYSET
dlc_load = os.path.join(USER, 'dlc_load.json')
enabled = json.load(open(dlc_load, encoding='utf-8-sig')).get('enabled_mods', []) if os.path.exists(dlc_load) else []
playset = []  # (name, id, root, our folder or None), in load order
for entry in enabled:
    p = os.path.join(USER, entry)
    if not os.path.exists(p):
        say('WARN', 'PLAYSET', f'{entry}: descriptor missing (mod unsubscribed?)')
        continue
    d = descriptor(p)
    root = d['path'] or ''
    if root and not os.path.isabs(root):
        root = os.path.join(USER, root)
    mine = next((f for f, m in ours.items() if d['name'] == m['name']), None)
    playset.append((d['name'] or entry, d['remote_file_id'], root, mine))

names = [n for n, *_ in playset]
say('OK', 'PLAYSET', f'last launched playset: {len(playset)} mods' + (f' ({", ".join(names[:8])})' if names else ''))
pos = {f: i for i, (_, _, _, f) in enumerate(playset) if f}
if 'fps_map' not in pos:
    if any(f for *_, f in playset):
        say('FAIL', 'PLAYSET', 'an FPS Map add-on is enabled without the main FPS Map mod')
    else:
        say('OK', 'PLAYSET', 'FPS Map is not in the last launched playset: nothing else to check there')
else:
    for f in ('fps_map_colorblind', 'fps_map_calmwater'):
        if f in pos and pos[f] < pos['fps_map']:
            say('FAIL', 'PLAYSET', f'{ours[f]["title"]} loads before FPS Map: move it below FPS Map')
    for i, (name, mid, root, mine) in enumerate(playset):
        if mine:
            continue
        if mid == MLECZ_ORIGINAL:
            say('FAIL', 'PLAYSET', f'the original FPS Map ({name}) is enabled too: disable it, both replace the same files')
            continue
        for f in ('fps_map', 'fps_map_calmwater'):
            if f in pos and (f, mid) in NEVER:
                say('FAIL', 'PLAYSET', f'{ours[f]["title"]} and {name}: do not combine (same water shader)')
        theirs = set(rel_files(root)) if os.path.isdir(root) else set()
        after = i > pos['fps_map']
        hidden = sorted(r for r in theirs & set(main['files']) if r.startswith(('gfx/', 'map/')) and after)
        if mid in ADVICE:
            known, want, why = ADVICE[mid]
            right = after == (want == 'before')
            say('OK' if right else 'WARN', 'PLAYSET',
                f'{name}: FPS Map loads {"after" if not after else "before"} it '
                f'({"recommended" if right else "move FPS Map " + want + " it"}) - {why}')
        elif hidden:
            say('WARN', 'PLAYSET', f'{name} loads after FPS Map and hides {len(hidden)} of its files '
                f'({", ".join(hidden[:4])}{" ..." if len(hidden) > 4 else ""}); move FPS Map below it '
                f'unless that mod needs them')

# ---------------------------------------------------------------- SAFETY
rules = re.findall(r'name\s*=\s*(\S+)\s+sub_directories\s*=\s*\w+\s+file_extension\s*=\s*(\S+)',
                   open(os.path.join(GAME, 'checksum_manifest.txt'), encoding='utf-8-sig').read())
for folder, m in ours.items():
    bad = [r for r in m['files'] if any(r.startswith(n + '/') and r.lower().endswith(e.lower()) for n, e in rules)]
    say('FAIL' if bad else 'OK', 'SAFETY', f'{m["title"]}: ' + (f'checksummed files {bad[:4]}' if bad else
        'no file in a checksummed folder (Ironman and multiplayer safe)'))

# ---------------------------------------------------------------- LOGS
our_names = {os.path.basename(r).lower() for m in ours.values() for r in m['files']} - {'descriptor.mod', 'thumbnail.png'}
pattern = re.compile(r'\.(shader|fxh)\b|shader|maparrow|fps[ _]?map|' + '|'.join(re.escape(n) for n in sorted(our_names)), re.I)
logs = [os.path.join(USER, 'logs', n) for n in ('error.log', 'graphics.log', 'system.log')] + EXTRA_LOGS
for log in logs:
    if not os.path.exists(log):
        continue
    hits = {}
    for line in open(log, encoding='utf-8', errors='replace'):
        if pattern.search(line):
            msg = re.sub(r'^\[[\d:]+\]\[[^\]]*\]:\s*', '', line.strip())
            hits[msg] = hits.get(msg, 0) + 1
    label = log if log in EXTRA_LOGS else os.path.basename(log)
    if hits:
        for msg, n in list(hits.items())[:10]:
            broken = re.search(r'fail|error|invalid|missing|not found|unknown|crash', msg, re.I)
            say('FAIL' if broken else 'WARN', 'LOGS', f'{label}: {msg[:160]}' + (f'  (x{n})' if n > 1 else ''))
        if len(hits) > 10:
            say('WARN', 'LOGS', f'{label}: {len(hits) - 10} more matching lines')
    else:
        say('OK', 'LOGS', f'{label}: nothing about FPS Map files, shaders or arrows')

# ---------------------------------------------------------------- report
lines = [f'{lvl:<4}  {sec:<7}  {msg}' for lvl, sec, msg in results]
worst = 'FAIL' if any(r[0] == 'FAIL' for r in results) else 'WARN' if any(r[0] == 'WARN' for r in results) else 'OK'
lines.append(f'\nhealth: {worst} ({sum(r[0] == "FAIL" for r in results)} fail, {sum(r[0] == "WARN" for r in results)} warn)')
print('\n'.join(lines))
with open(os.path.join(HERE, 'health_report.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
if '--notify' in args and worst != 'OK':
    import ctypes
    top = '\n'.join(f'{lvl} {sec}: {msg[:140]}' for lvl, sec, msg in results if lvl != 'OK')[:900]
    ctypes.windll.user32.MessageBoxW(0, top + '\n\nFull report: tools\\health_report.txt', f'FPS Map health: {worst}', 0x40030)
sys.exit(1 if worst == 'FAIL' else 0)
