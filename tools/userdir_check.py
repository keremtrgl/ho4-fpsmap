"""Find files in the HoI4 user folder that silently override the game and mods.

    python -I tools/userdir_check.py [--userdir DIR] [--game DIR] [--fix]

Hearts of Iron IV also loads content from Documents/Paradox Interactive/
Hearts of Iron IV/ (above vanilla AND all mods). Leftovers there - most often
from the debug-mode Nudger map editor - cause bugs that look like mod bugs:

  BROKEN    localisation the game rejects (no UTF-8 BOM, wrong l_<lang> header,
            or a bad version number such as KEY:-1). The whole file is ignored,
            so its keys show raw in game, e.g. "STRATEGICREGION_49".
  CHECKSUM  map/script files in checksummed folders: the game checksum changes,
            Ironman achievements and multiplayer are affected.
  OVERRIDE  graphics/interface/other content that hides what mods change.

--fix moves every finding to _override_backup_<date>/ (nothing is deleted).
Exit code 1 if anything was found.
"""
import datetime, os, re, shutil, sys

GAME = r'C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV'
USER = os.path.join(os.path.expanduser('~'), 'Documents', 'Paradox Interactive', 'Hearts of Iron IV')
args = sys.argv[1:]
if '--userdir' in args:
    USER = args[args.index('--userdir') + 1]
if '--game' in args:
    GAME = args[args.index('--game') + 1]

# folders the engine reads as content; everything else in the user dir is
# settings, saves, logs, caches or mods
CONTENT = ('common', 'events', 'history', 'map', 'localisation', 'gfx', 'interface',
           'music', 'sound', 'portraits', 'tutorial', 'tests')
LOC_LINE = re.compile(r'^\s*[A-Za-z0-9_.\-]+:\d*\s+"')
BAD_VERSION = re.compile(r'^\s*([A-Za-z0-9_.\-]+):(-\d+|\D[^ "]*)\s')


def checksum_rules():
    p = os.path.join(GAME, 'checksum_manifest.txt')
    text = open(p, encoding='utf-8-sig').read() if os.path.exists(p) else ''
    return re.findall(r'name\s*=\s*(\S+)\s+sub_directories\s*=\s*\w+\s+file_extension\s*=\s*(\S+)', text)


def check_loc(path, rel):
    raw = open(path, 'rb').read()
    lang = re.search(r'_l_(\w+)\.yml$', rel)
    issues = []
    if not raw.startswith(b'\xef\xbb\xbf'):
        issues.append('no UTF-8 BOM (the game ignores the file)')
    text = raw.decode('utf-8-sig', errors='replace')
    first = next((l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith('#')), '')
    if lang and first != f'l_{lang.group(1)}:':
        issues.append(f'header is "{first[:30]}", expected "l_{lang.group(1)}:"')
    bad = [m.group(1) for l in text.splitlines() if (m := BAD_VERSION.match(l))]
    if bad:
        issues.append(f'{len(bad)} keys with an invalid version number (e.g. {bad[0]}:...) - '
                      f'the whole file is rejected, so these keys show raw in game')
    return issues


rules = checksum_rules()
findings = []
for top in CONTENT:
    base = os.path.join(USER, top)
    for d, _, files in os.walk(base):
        for f in files:
            p = os.path.join(d, f)
            rel = os.path.relpath(p, USER).replace('\\', '/')
            created = datetime.datetime.fromtimestamp(os.path.getctime(p)).strftime('%Y-%m-%d %H:%M')
            if any(rel.startswith(n + '/') and rel.lower().endswith(e.lower()) for n, e in rules):
                findings.append(('CHECKSUM', rel, created, 'changes the game checksum: Ironman achievements and multiplayer affected'))
            elif rel.endswith('.yml') and top == 'localisation':
                issues = check_loc(p, rel)
                if issues:
                    findings.append(('BROKEN', rel, created, '; '.join(issues)))
                else:
                    findings.append(('OVERRIDE', rel, created, 'valid, but replaces this localisation for every mod'))
            else:
                findings.append(('OVERRIDE', rel, created, 'replaces this file for vanilla and every mod'))

print(f'User folder: {USER}')
if not findings:
    print('Clean: no content overrides in the user folder.')
for kind, rel, created, why in findings:
    print(f'{kind:9} {rel}  (created {created})\n          {why}')
if findings:
    print('\nThese usually come from the debug-mode Nudger map editor. Move them out with --fix.')
    if '--fix' in args:
        dest = os.path.join(USER, '_override_backup_' + datetime.date.today().isoformat())
        for _, rel, _, _ in findings:
            target = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.move(os.path.join(USER, rel), target)
        print(f'Moved {len(findings)} file(s) to {dest}')
sys.exit(1 if findings and '--fix' not in args else 0)
