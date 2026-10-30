"""Rebuild the FPS Map mod against the installed Hearts of Iron IV version.

Usage:
    python -I build.py <original mod dir> <game dir> <output dir>

Every file that also exists in vanilla is rebuilt from the *current* vanilla
file with only the mod's own edits re-applied, so new engine features (new
shader effects, constant buffer fields, arrow/symbol types) are never lost.

Outputs:
    <output dir>              FPS Map
    <output dir>_colorblind   optional sub-mod: colour-blind army arrow palette
    tools/vanilla_manifest.json   hashes of every vanilla file the build read,
                                  used by patch_check.py after a game patch
"""
import hashlib, json, os, re, shutil, struct, subprocess, sys
from PIL import Image

SRC, GAME, OUT = sys.argv[1:4]
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import colorblind

OUT_CB = OUT.rstrip('/\\') + '_colorblind'
OUT_WATER = OUT.rstrip('/\\') + '_calmwater'
# Descriptor names ARE the Workshop titles: the launcher overwrites the title
# with this name on every upload, and add-ons depend on it by name.
# ASCII only: some tools read descriptors as ANSI and would mangle an en dash.
NAME = 'FPS Map - Updated for 1.19 (Ironman & MP Safe)'
NAME_CB = 'FPS Map - Colour-blind Add-on'
NAME_WATER = 'FPS Map - Calm Water Add-on'
WORKSHOP_ID = '3828926440'
WORKSHOP_ID_CB = '3828959483'
WORKSHOP_ID_WATER = '3829377291'
REVISION = 5 # bump for every Workshop update on the same game version

# Files dropped from the build:
#  - byte-identical to vanilla: overriding them only freezes old vanilla art
#  - shipped at gfx/interface/ while the game reads gfx/interface/mapicons/,
#    so they were never loaded (and the combat frame no longer matches the
#    2-frame vanilla sprite)
IDENTICAL_TO_VANILLA = {
    'gfx/interface/factory_item_bg.dds',
    'gfx/interface/prod_progress_bar2_red.dds',
    'gfx/interface/prod_progress_bar2_yellow.dds',
    'gfx/interface/prod_progress_bar3.dds',
    'gfx/interface/naviesview/ship_activity_engaged.dds',
    'gfx/maparrows/blitz_line.dds',
    'gfx/maparrows/blitz_line_mask.dds',
    'gfx/maparrows/blitz_line_unassigned_mask.dds',
}
DEAD_PATH = {
    'gfx/interface/mapicon_bar_bg.dds',
    'gfx/interface/mapicon_bar_org.dds',
    'gfx/interface/mapicon_bar_org_sprite.dds',
    'gfx/interface/mapicon_bar_str.dds',
    'gfx/interface/mapicon_bar_str_sprite.dds',
    'gfx/interface/mapicon_land_combat.dds',
    'gfx/interface/mapicon_land_combat_frame.dds',
}
# Generated below instead of copied.
GENERATED = {
    'descriptor.mod',
    'thumbnail.png',
    'gfx/FX/constants.fxh',
    'gfx/FX/river.shader',
    'gfx/FX/maparrow.shader',
    'gfx/maparrows/maparrows.txt',
    'map/terrain/reflection.dds',
}
# Vanilla resized these sprites; the mod's art is resampled to the new size.
RESIZE = {
    'gfx/interface/deployment_entry_progressbar.dds',
    'gfx/interface/deployment_entry_stalled_progressbar.dds',
    'gfx/interface/fuel_bar.dds',
}
# Vanilla now ships these with mip chains (map-space / scaled UI); the mod's
# art gets the same chain so it behaves identically when scaled.
REMIP = {
    'gfx/interface/battle_indicator_direction.dds',
    'gfx/interface/onmap_mission_unit_counter_types.dds',
    'gfx/interface/mapicons/mapicon_naval_mission_mines_planting.dds',
    'gfx/interface/mapicons/mapicon_naval_mission_mines_sweeping.dds',
    'gfx/interface/mapicons/mapicon_naval_mission_naval_invasion_support.dds',
    'gfx/interface/naviesview/all_missions.dds',
    'gfx/interface/naviesview/btn_mines_planting.dds',
    'gfx/interface/naviesview/btn_mines_sweeping.dds',
    'gfx/interface/strategicair/progress_bad.dds',
    'gfx/interface/strategicair/progress_good.dds',
}


def rel_files(root):
    for d, _, fs in os.walk(root):
        for f in fs:
            yield os.path.relpath(os.path.join(d, f), root).replace('\\', '/')


def read(p):
    with open(p, encoding='utf-8-sig', newline='') as f:
        return f.read()


def write(rel, text):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def patch(text, edits, name):
    """Apply (old, new) edits; each old string must occur exactly once."""
    for old, new in edits:
        n = text.count(old)
        if n != 1:
            sys.exit(f'{name}: expected 1 match, found {n}: {old!r}')
        text = text.replace(old, new)
    return text


# ---------------------------------------------------------------- DDS helpers

def dds_info(p):
    h = open(p, 'rb').read(128)
    hgt, wid = struct.unpack_from('<II', h, 12)
    mips = struct.unpack_from('<I', h, 28)[0]
    return wid, hgt, max(mips, 1)


def mip_chain(im, levels):
    out, cur = [im], im.convert('RGBa')  # premultiplied: no dark fringes
    for _ in range(levels - 1):
        w, h = max(1, cur.width // 2), max(1, cur.height // 2)
        cur = cur.resize((w, h), Image.BOX)
        out.append(cur.convert('RGBA'))
    return out


def write_dds(rel, faces, levels, cube=False, root=None):
    """Uncompressed A8R8G8B8 DDS, same header layout vanilla uses."""
    w, h = faces[0].size
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | (0x20000 if levels > 1 else 0) | (0 if cube else 0x8)
    caps = 0x1000 | (0x400008 if levels > 1 else 0) | (0x2 if cube else 0)
    hdr = struct.pack('<4s7I44x', b'DDS ', 124, flags, h, w, 0 if cube else w * 4, 0, levels)
    hdr += struct.pack('<2I4s5I', 32, 0x41, b'\0\0\0\0', 32, 0xFF0000, 0xFF00, 0xFF, 0xFF000000)
    hdr += struct.pack('<4I4x', caps, 0xFE00 if cube else 0, 0, 0)
    assert len(hdr) == 128
    data = bytearray(hdr)
    for face in faces:
        for lvl in mip_chain(face.convert('RGBA'), levels):
            data += lvl.tobytes('raw', 'BGRA')
    p = os.path.join(root or OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'wb').write(data)


def full_chain(w, h):
    n = 1
    while w > 1 or h > 1:
        w, h, n = max(1, w // 2), max(1, h // 2), n + 1
    return n


# ---------------------------------------------------------------- build

if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)

copied = 0
for rel in rel_files(SRC):
    if rel in IDENTICAL_TO_VANILLA | DEAD_PATH | GENERATED | RESIZE | REMIP:
        continue
    dst = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(os.path.join(SRC, rel), dst)
    copied += 1

# constants.fxh: brighter-free water, solid borders, stronger mud overlay
write('gfx/FX/constants.fxh', patch(read(os.path.join(GAME, 'gfx/FX/constants.fxh')), [
    ('MUD_TILING \t\t\t\t\t= 0.09;', 'MUD_TILING \t\t\t\t\t= 0.07; // FPS Map'),
    ('WATER_COLOR_LIGHTNESS = 0.5;', 'WATER_COLOR_LIGHTNESS = 0.25; // FPS Map'),
    ('COLORMAP_MUD_OVERLAY_STRENGTH = 0.5f;', 'COLORMAP_MUD_OVERLAY_STRENGTH = 0.7f; // FPS Map'),
    ('GB_CAM_MAX_FILLING_CLAMP = 0.8f;', 'GB_CAM_MAX_FILLING_CLAMP = 1.0f; // FPS Map'),
    ('GB_OPACITY_FAR = 0.85f;', 'GB_OPACITY_FAR = 1.0f; // FPS Map'),
    ('GB_FIRST_LAYER_PRIORITY = 0.4;', 'GB_FIRST_LAYER_PRIORITY = 0.8; // FPS Map'),
    # Close-up calm: vanilla snow is strongest when zoomed IN (0.95) and faint
    # zoomed out (0.2). Fade it out up close; the strategic view keeps vanilla's
    # 0.2 so winter stays readable. Trees/buildings use the same curve.
    ('SNOW_OPACITY_MIN\t\t\t= 0.95f;', 'SNOW_OPACITY_MIN\t\t\t= 0.0f; // FPS Map: no snow up close'),
    # Sea ice: same hue, about 40% less glare.
    ('ICE_COLOR \t\t\t\t\t= float3( 0.5f, 0.6f, 0.9f );', 'ICE_COLOR \t\t\t\t\t= float3( 0.30f, 0.36f, 0.54f ); // FPS Map'),
], 'constants.fxh'))

# standardfuncsgfx.fxh: the frost tint ignored zoom entirely (a 40% floor on
# every wintry tile). Scale it like the snow itself: vanilla at the strategic
# zoom (vOpacity == SNOW_OPACITY_MAX), none up close.
write('gfx/FX/standardfuncsgfx.fxh', patch(read(os.path.join(GAME, 'gfx/FX/standardfuncsgfx.fxh')), [
    ('( SNOW_FROST_MIN_EFFECT * vMinSnow )',
     '( SNOW_FROST_MIN_EFFECT * vMinSnow * saturate( vOpacity / SNOW_OPACITY_MAX ) ) /* FPS Map */'),
], 'standardfuncsgfx.fxh'))

# fow.fxh: fog of war keeps WHERE and HOW STRONG it is (alpha untouched), but
# its near-white wisps become a soft cool grey with a narrower bright range,
# and drift at 40% speed.
write('gfx/FX/fow.fxh', patch(read(os.path.join(GAME, 'gfx/FX/fow.fxh')), [
    ('FOW_COLOR_MIN = 0.2;', 'FOW_COLOR_MIN = 0.35; // FPS Map'),
    ('FOW_COLOR_MAX = 1.0;', 'FOW_COLOR_MAX = 0.8; // FPS Map'),
    ('FOW_NOISE_SPEED = 0.015;', 'FOW_NOISE_SPEED = 0.006; // FPS Map: calmer drift'),
    ('BRIGHT_FOW_COLOR = float3(0.98, 0.93, 0.93);', 'BRIGHT_FOW_COLOR = float3(0.62, 0.64, 0.68); // FPS Map: soft grey, no glare'),
], 'fow.fxh'))

# Weather particles: ~36% of vanilla intensity (opacity x0.6, density x0.6),
# lightning flashes x0.3 so they glow instead of strobing. Sounds untouched.
WEATHER = [f'gfx/particles/environment/{n}.asset' for n in (
    'rain', 'rain_clouds', 'rain_small', 'rain_small_clouds',
    'lightning_storm', 'lightning_storm_clouds', 'lightning_storm_small', 'lightning_storm_small_clouds',
    'snow', 'snow_clouds', 'snow_small', 'snow_small_clouds',
    'snow_storm', 'snow_storm_clouds', 'snow_storm_small', 'snow_storm_small_clouds', 'sandstorm')]


def calm_particles(text):
    out, sub = [], ''
    for line in text.split('\n'):
        cr = '\r' if line.endswith('\r') else ''
        line = line[:len(line) - len(cr)]
        m = re.match(r'\s*name\s*=\s*"([^"]*)"', line)
        if m:
            sub = m.group(1)
        flash = 'flash' in sub or sub == 'lightning'
        key = re.match(r'\s*(alpha|emission|max_amount)\s*=', line)
        if key:
            k = key.group(1)
            f = 0.3 if (k == 'alpha' and flash) else 0.6
            if k == 'max_amount':
                line = re.sub(r'\d+', lambda n: str(-(-int(n.group()) * 6 // 10)), line, count=1)
            else:
                line = re.sub(r'\d+\.\d+', lambda n: f'{float(n.group()) * f:.3f}', line)
            line += '\t# FPS Map'
        out.append(line + cr)
    return '\n'.join(out)


for rel in WEATHER:
    write(rel, calm_particles(read(os.path.join(GAME, rel))))

# river.shader: no snow on rivers
write('gfx/FX/river.shader', patch(read(os.path.join(GAME, 'gfx/FX/river.shader')), [
    ('vOpacity = SNOW_OPACITY_MIN + vOpacity * ( SNOW_OPACITY_MAX - SNOW_OPACITY_MIN );',
     'vOpacity = 0.0f; // FPS Map: no snow on rivers'),
], 'river.shader'))

# maparrow.shader: flat, unlit, unsaturated arrows; discard masked pixels early
ma = read(os.path.join(GAME, 'gfx/FX/maparrow.shader'))
ma = patch(ma, [
    ('clip( vMaskValue <= 0 ? 0 : 1 );', 'clip( vMaskValue <= 0 ? -1 : 1 ); // FPS Map'),
    ('vArrowColor.g *= 1.5; //S bump up the saturation and light', 'vArrowColor.g *= 1.0; //S // FPS Map'),
    ('vArrowColor.g *= 2.0; //S bump up the saturation and light', 'vArrowColor.g *= 1.0; //S // FPS Map'),
    ('vArrowColor.b *= 1.5; //V', 'vArrowColor.b *= 1.0; //V // FPS Map'),
], 'maparrow.shader')
n = ma.count('vColor.rgb = lerp(vColor.rgb, vColor2, 0.5);')
if n != 2:
    sys.exit(f'maparrow.shader: expected 2 lighting lerps, found {n}')
ma = ma.replace('vColor.rgb = lerp(vColor.rgb, vColor2, 0.5);', '//vColor.rgb = lerp(vColor.rgb, vColor2, 0.5); // FPS Map')
# symbol shader: unlit and unfogged
ma = patch(ma, [
    ('\t\t\tvColor.rgb = CalculateLighting( Input.prepos, Input.vScreenCoord, vNormal, vColor );\n'
     '\t\t\tvColor.rgb = ApplyDistanceFog( vColor.rgb, Input.prepos );\n'
     '\t\t\t//vColor.rgb = DayNight(',
     '\t\t\t//vColor.rgb = CalculateLighting( Input.prepos, Input.vScreenCoord, vNormal, vColor ); // FPS Map\n'
     '\t\t\t//vColor.rgb = ApplyDistanceFog( vColor.rgb, Input.prepos ); // FPS Map\n'
     '\t\t\t//vColor.rgb = DayNight('),
], 'maparrow.shader (symbol)')
write('gfx/FX/maparrow.shader', ma)

# maparrows.txt: vanilla + the mod's #SVA tuning + bright-first colour order
os.makedirs(os.path.join(OUT, 'gfx/maparrows'), exist_ok=True)
subprocess.run([sys.executable, '-I', os.path.join(HERE, 'maparrows_merge.py'),
                os.path.join(GAME, 'gfx/maparrows/maparrows.txt'),
                os.path.join(SRC, 'gfx/maparrows/maparrows.txt'),
                os.path.join(OUT, 'gfx/maparrows/maparrows.txt')], check=True,
               stdout=subprocess.DEVNULL)

# Arrow types added to the game after the original mod already get its flat,
# unlit look from maparrow.shader; only their geometry/flow was never tuned.
#  - raid arrows copy air_mission_direction but lack its arrow-length scaling
#  - general front lines get the mod's calmer flow (ag_move_thick 0.17 -> 0.1)
STYLE = {
    **{name: {'global_scale_min_size': '0.1', 'global_scale_max_points': '40'}
       for name in ('active_raid_line', 'active_raid_ballistic', 'active_raid_air',
                    'active_raid_naval', 'active_raid_land')},
    **{name: {'texture_anim_speed': 0.6}
       for name in ('deployed_general_front_line_on_front', 'deployed_general_front_line_close',
                    'deployed_general_front_line_medium', 'deployed_general_front_line_far')},
}


def style_arrow(text, name, values):
    """Set keys inside the top-level block called `name`. A str value replaces or
    adds the key; a float scales the existing number."""
    m = re.search(r'\n(arrowType|symbolType)\s*=\s*\{\s*\n\s*name\s*=\s*"' + re.escape(name) + r'".*?\n\}', text, re.S)
    if not m:
        sys.exit(f'maparrows.txt: no block named {name}')
    block = m.group(0)
    for key, value in values.items():
        km = re.search(rf'\n(\s*){key}\s*=\s*([\d.]+)[^\n]*', block)
        if isinstance(value, float):
            if not km:
                sys.exit(f'maparrows.txt: {name} has no {key} to scale')
            value = f'{float(km.group(2)) * value:g}'
        line = f'\n\t{key} = {value}\t# FPS Map'
        block = block.replace(km.group(0), line, 1) if km else block[:-2] + line + '\n}'
    return text[:m.start()] + block + text[m.end():]


arrows_path = os.path.join(OUT, 'gfx/maparrows/maparrows.txt')
arrows = read(arrows_path)
for name, values in STYLE.items():
    arrows = style_arrow(arrows, name, values)
with open(arrows_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(arrows)

# Resized sprites: mod art at the new vanilla size and mip count
for rel in sorted(RESIZE):
    w, h, levels = dds_info(os.path.join(GAME, rel))
    im = Image.open(os.path.join(SRC, rel)).convert('RGBA').resize((w, h), Image.LANCZOS)
    write_dds(rel, [im], levels)

for rel in sorted(REMIP):
    w, h, levels = dds_info(os.path.join(GAME, rel))
    assert levels == full_chain(w, h), rel
    im = Image.open(os.path.join(SRC, rel)).convert('RGBA')
    assert im.size == (w, h), rel
    write_dds(rel, [im], levels)

# reflection.dds: the mod wants no sky reflection (pure black), but shipped a
# 2D strip where the water/river/sky shaders sample a cube map. Emit a real
# black cube map. A black cube samples black at any size, so 4x4 faces replace
# vanilla's 256x256 (2 MB of VRAM and texture bandwidth saved, same image).
REFLECTION_SIZE = 4
black = Image.new('RGBA', (REFLECTION_SIZE, REFLECTION_SIZE), (0, 0, 0, 255))
write_dds('map/terrain/reflection.dds', [black] * 6, full_chain(REFLECTION_SIZE, REFLECTION_SIZE), cube=True)

ver = re.search(r'rawVersion"\s*:\s*"([^"]+)"', read(os.path.join(GAME, 'launcher-settings.json'))).group(1)
major_minor = '.'.join(ver.split('.')[:2])
write('descriptor.mod', (
    f'version="{ver}-{REVISION}"\n'
    'tags={\n\t"Map"\n\t"Graphics"\n}\n'
    f'name="{NAME}"\n'
    f'supported_version="{major_minor}.*"\n'
    f'remote_file_id="{WORKSHOP_ID}"\n'
))

# Our own thumbnail (workshop/images, made by make_images.py); the original
# mod's art is only a fallback.
images = os.path.join(HERE, '..', 'workshop', 'images')
thumb = os.path.join(images, 'thumbnail.png')
shutil.copy2(thumb if os.path.exists(thumb) else os.path.join(SRC, 'thumbnail.png'),
             os.path.join(OUT, 'thumbnail.png'))

# ------------------------------------------------- colour-blind sub-mod
# Only maparrows.txt differs from FPS Map, so the sub-mod ships that one file
# and loads after FPS Map through its dependency.
if os.path.exists(OUT_CB):
    shutil.rmtree(OUT_CB)
os.makedirs(os.path.join(OUT_CB, 'gfx/maparrows'))
cb_text = colorblind.apply(arrows, colorblind.palette(len(colorblind.read_leader_groups(arrows))))
with open(os.path.join(OUT_CB, 'gfx/maparrows/maparrows.txt'), 'w', encoding='utf-8', newline='\n') as f:
    f.write(cb_text)
with open(os.path.join(OUT_CB, 'descriptor.mod'), 'w', encoding='utf-8', newline='') as f:
    f.write(f'version="{ver}-{REVISION}"\n'
            'tags={\n\t"Graphics"\n\t"Map"\n}\n'
            f'name="{NAME_CB}"\n'
            f'dependencies={{\n\t"{NAME}"\n}}\n'
            f'supported_version="{major_minor}.*"\n'
            f'remote_file_id="{WORKSHOP_ID_CB}"\n')
# Red/green status indicators -> blue/orange. Start from FPS Map's own version
# where it ships one (the add-on loads after it), else from vanilla.
import numpy as np
for rel in colorblind.INDICATORS:
    src = os.path.join(OUT, rel) if os.path.exists(os.path.join(OUT, rel)) else os.path.join(GAME, rel)
    w, h, levels = dds_info(src)
    arr = np.asarray(Image.open(src).convert('RGBA'), float) / 255
    out = Image.fromarray((colorblind.recolor(arr) * 255 + 0.5).astype(np.uint8), 'RGBA')
    assert out.size == (w, h), rel
    write_dds(rel, [out], levels, root=OUT_CB)

cb_thumb = os.path.join(images, 'thumbnail_colorblind.png')
if os.path.exists(cb_thumb):
    shutil.copy2(cb_thumb, os.path.join(OUT_CB, 'thumbnail.png'))

# ------------------------------------------------- calm water add-on
# Separate because Millennium Dawn replaces pdxwater.shader too: shipping it in
# FPS Map would drop MD's water changes. Only the sun's specular contribution
# on water is scaled; colour, waves, ice and borders are untouched.
WATER_GLARE = 0.35
if os.path.exists(OUT_WATER):
    shutil.rmtree(OUT_WATER)
os.makedirs(os.path.join(OUT_WATER, 'gfx/FX'))
water = patch(read(os.path.join(GAME, 'gfx/FX/pdxwater.shader')), [
    ('CalculateSunLight( lightingProperties, fShadowTerm, SunDirWater, diffuseLight, specularLight );',
     'CalculateSunLight( lightingProperties, fShadowTerm, SunDirWater, diffuseLight, specularLight );\n'
     f'\t\t\tspecularLight *= {WATER_GLARE}f; // FPS Map Calm Water: softer sun glare'),
], 'pdxwater.shader')
with open(os.path.join(OUT_WATER, 'gfx/FX/pdxwater.shader'), 'w', encoding='utf-8', newline='') as f:
    f.write(water)
with open(os.path.join(OUT_WATER, 'descriptor.mod'), 'w', encoding='utf-8', newline='') as f:
    f.write(f'version="{ver}-{REVISION}"\n'
            'tags={\n\t"Graphics"\n\t"Map"\n}\n'
            f'name="{NAME_WATER}"\n'
            f'dependencies={{\n\t"{NAME}"\n}}\n'
            f'supported_version="{major_minor}.*"\n'
            + (f'remote_file_id="{WORKSHOP_ID_WATER}"\n' if WORKSHOP_ID_WATER else ''))
water_thumb = os.path.join(images, 'thumbnail_calmwater.png')
if os.path.exists(water_thumb):
    shutil.copy2(water_thumb, os.path.join(OUT_WATER, 'thumbnail.png'))

# ------------------------------------------------- vanilla manifest
# Every vanilla file the build read or overrides; patch_check.py compares these
# hashes after a game patch to say exactly what changed.
def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def entry(rel):
    p = os.path.join(GAME, rel)
    e = {'sha256': sha(p)}
    if rel.endswith('.dds'):
        e['dds'] = list(dds_info(p))
    return e


used = {rel for root in (OUT, OUT_CB, OUT_WATER) for rel in rel_files(root)
        if os.path.exists(os.path.join(GAME, rel))}
used |= {'checksum_manifest.txt'}
with open(os.path.join(HERE, 'vanilla_manifest.json'), 'w', encoding='utf-8') as f:
    json.dump({'game_version': ver, 'files': {rel: entry(rel) for rel in sorted(used)}}, f, indent=1)

print(f'game {ver}: copied {copied}, rebuilt {len(GENERATED) + len(RESIZE) + len(REMIP)}, '
      f'dropped {len(IDENTICAL_TO_VANILLA) + len(DEAD_PATH)}, styled {len(STYLE)} arrow types, '
      f'manifest {len(used)} vanilla files')
