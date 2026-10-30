# FPS Map — Updated for Hearts of Iron IV 1.19

A maintained continuation of [FPS Map by Mlecz](https://steamcommunity.com/sharedfiles/filedetails/?id=2404689961),
rebuilt for Hearts of Iron IV 1.19.x and every DLC. Ironman and multiplayer safe.

| Steam Workshop | |
|---|---|
| [FPS Map - Updated for 1.19 (Ironman & MP Safe)](https://steamcommunity.com/sharedfiles/filedetails/?id=3828926440) | main mod |
| [FPS Map - Colour-blind Add-on](https://steamcommunity.com/sharedfiles/filedetails/?id=3828959483) | optional |
| [FPS Map - Calm Water Add-on](https://steamcommunity.com/sharedfiles/filedetails/?id=3829377291) | optional, not with Millennium Dawn |

Players: subscribe on the Workshop. This repository is for transparency and maintenance.

## How it is built

The mod is not a hand-edited copy of old files. `tools/build.py` takes the **installed game's
current files** and applies only FPS Map's own edits to them, so nothing Paradox adds in a patch
is lost. Every edit must match exactly once, otherwise the build stops.

```
original_2404689961/   Mlecz's original mod (art source, untouched)
tools/                 build, verification and release tooling
fps_map/               built main mod            (what ships to the Workshop)
fps_map_colorblind/    built Colour-blind Add-on
fps_map_calmwater/     built Calm Water Add-on
workshop/              Workshop descriptions (all languages), changelogs, images
CHANGELOG.md           technical changelog
```

## Ironman & multiplayer safety

The game checksum covers `common/`, `events/`, `history/` and map data files. FPS Map ships none
of them, only shaders, textures, particles and arrow visuals. `tools/verify.py` fails the build if a
checksummed file ever appears, and the checksum was confirmed identical to vanilla in game.

## After a game patch

```
python -I tools/patch_check.py --install
```

1. reports which vanilla source files the patch changed,
2. rebuilds all three mods from the new game files,
3. verifies them (checksum safety, texture layouts, every vanilla arrow/shader definition kept),
4. checks the user folder for overrides (for example Nudger leftovers),
5. with `--install`, copies the mods to `Documents/Paradox Interactive/Hearts of Iron IV/mod`.

Other tools:

| Command | Purpose |
|---|---|
| `python -I tools/lint.py` | release lint: encodings, braces, descriptors, thumbnails, BBCode |
| `python -I tools/conflicts.py` | compatibility scan against every installed mod → `workshop/compatibility.md` |
| `python -I tools/userdir_check.py [--fix]` | finds user-folder files that override all mods |
| `python -I tools/indicator_report.py` | colour-vision measurements for the Colour-blind Add-on |

Requires Python 3 with Pillow and NumPy. `tools/vanilla_snapshot/` (local copies of Paradox
files used for patch diffs) is not published; the first `patch_check.py` run recreates it.

## Credits

- Original mod, art and visual design: **Mlecz**. All visual design is his work.
- 1.19 update and maintenance: [keremtrgl](https://github.com/keremtrgl).

Hearts of Iron IV is a trademark of Paradox Interactive. This project is not affiliated with Paradox.
