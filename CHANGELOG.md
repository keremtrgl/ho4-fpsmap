# FPS Map (Updated)

Rebuilt against Hearts of Iron IV 1.19.4, compatible with every DLC up to Thunder at Our Gates.
After a game patch: `python -I tools/patch_check.py --install`
Compatibility report: `python -I tools/conflicts.py`

## 1.19.4.1-6 — calmer water with high-quality shaders
All three edits only touch code paths that run with "High quality shaders" on; the low-quality
look is unchanged. Still no file in a checksummed folder.
- `standardfuncsgfx.fxh`: the sun overload that takes an explicit light direction is only called
  by the water shader. It now wraps `CalculateSunLightBase` and halves the specular, so the
  camera-locked white sun hotspot no longer turns shallow seas (Persian Gulf, Gulf of Suez)
  chalk-white. Land, rivers, trees and units keep vanilla light. Done here rather than in
  `pdxwater.shader`, so Millennium Dawn's water shader gets it too. In game: hotspot peak
  brightness 213–255 → 133.
- `pdxmap.shader`: the underwater pass lets only 25% of the lit seabed through
  (`vWaterAlpha * 0.25f`); deep sea unchanged.
- `constants.fxh`: distance haze `FOG_MAX` 0.35 → 0.18, `FOG_COLOR` (0.12, 0.28, 0.6) →
  (0.05, 0.12, 0.26), so the tilted camera's upper screen is no longer washed pale blue.

## 1.19.4.1-5 — lighter reflection map, 1.19.4.1 rebuild
- Rebuilt against 1.19.4.1; all 165 vanilla source files unchanged since 1.19.4.0.
- `map/terrain/reflection.dds`: the black cube map had vanilla's 256×256×6 faces with 9 mips
  (2 MB). A black cube samples black at any size, so it is now 4×4 faces with a full chain
  (632 bytes): about 2 MB less VRAM and texture bandwidth on water and rivers, same image.
  `verify.py` checks cube flags, square faces, data size and that every texel is black.
- Checked, not changed: `blitz_*` (356×178, vanilla 400×178) and `ag_default_*` (256×128,
  vanilla 160×93) arrow textures. Arrow textures are UV-mapped and Mlecz's thinner art is tuned
  with its own `head_length`/`body_width` values; resampling to vanilla sizes would shift the
  head/body split.
- Verified in game on 1.19.4.1 with every DLC enabled: loads, water renders as before,
  no error-log line mentions any mod file.
- Source published at https://github.com/keremtrgl/ho4-fpsmap.

## 1.19.4.0-4 — calmer fog of war, two add-ons, user-folder check
- `fow.fxh`: `BRIGHT_FOW_COLOR` (0.98, 0.93, 0.93) → (0.62, 0.64, 0.68), `FOW_COLOR_MIN/MAX`
  0.2/1.0 → 0.35/0.8, `FOW_NOISE_SPEED` 0.015 → 0.006. Fog alpha (where/how strong) untouched.
- Descriptor names = Workshop titles (ASCII), defined once in `build.py` (`NAME*`); add-on
  dependencies are generated from the same constant. Stops the launcher's title reset.
- `fps_map_colorblind`: 9 red/green indicator pairs + war score bar recoloured green→blue,
  red→orange (`colorblind.recolor`, hue bands with feathered edges, value/alpha kept).
  Measured with `tools/indicator_report.py`: worst deuteranopia pair 3.4 → 27.7.
- New `fps_map_calmwater`: vanilla `pdxwater.shader` + `specularLight *= 0.35f` after the
  sun light. Separate because Millennium Dawn ships its own `pdxwater.shader`.
- New `tools/userdir_check.py` (also run by `patch_check.py`): finds user-folder overrides
  (Nudger leftovers): BROKEN localisation (`KEY:-1`), CHECKSUM map files, OVERRIDE gfx.
- Verified in game with all three mods: checksum a783 (= vanilla), no mod errors.

## 1.19.4.0-3 — calm close-up winter, softer weather
Requested on the Workshop: zoomed in, winter turned the map into a white sheet.
- `constants.fxh`: `SNOW_OPACITY_MIN` 0.95 → 0.0. Vanilla snow is strongest up close
  and 0.2 far out; it now fades out up close and keeps vanilla's 0.2 at strategic zoom.
  Snow on trees/buildings (`pdxmesh.shader`) follows the same curve.
- `standardfuncsgfx.fxh`: the frost floor (`SNOW_FROST_MIN_EFFECT`, a fixed 40% tint)
  now scales with the same zoom factor: vanilla far out, none up close.
- `constants.fxh`: `ICE_COLOR` (0.5, 0.6, 0.9) → (0.30, 0.36, 0.54): same hue, less glare.
- 17 weather particle assets: opacity, emission and max count ×0.6; lightning flash
  opacity ×0.3 (no strobing). Sounds untouched.
- Not changed on purpose: the sun glare on water lives in `pdxwater.shader`, which
  Millennium Dawn also overrides; shipping it would drop MD's water changes.
- Verified: before/after at the same spot (1 Jan 1936), strategic view pixel-identical,
  checksum identical with/without the mod, no mod errors, MD still compatible.

## 1.19.4.0-2 — consistent arrows, colour-blind add-on
- Raid arrows scale with length like air-mission arrows; general front lines flow 0.6×.
- New add-on `fps_map_colorblind` (measured CVD-safe army arrow palette).
- `tools/patch_check.py`, `tools/conflicts.py`, `tools/vanilla_manifest.json`.

## 1.19.4.0-1

## Fixed
- `gfx/FX/maparrow.shader` was an outdated copy. The effects the engine now asks for
  (`MapArrowDefaultWithDepthTestOnly`, `MapArrowNoHeadSeethrough`,
  `MapArrowNoHeadWidthDepthSeethrough`), their stencil states and the new constant
  buffer fields (`SeethroughOpacity`, `TotalLength`, `UvToAbsoluteLength`) were missing.
  Rebuilt from vanilla with the mod's edits re-applied.
- `gfx/maparrows/maparrows.txt` lacked 12 arrow/symbol types added in later patches
  (raid arrows, deployed-general lines, commander ability range). Rebuilt from vanilla
  with the mod's 23 tuning values and colour order re-applied.
- `map/terrain/reflection.dds` was a black 2D strip, but water, river and sky shaders
  sample a cube map. Now a real black cube map (same look: no sky reflection).
- Deployment progress bars and the fuel bar were drawn at an old size (79/54 px) in
  65/45 px slots. Mod art resampled to the current size.
- 10 map/UI icons lacked the mip chains vanilla now ships; mod art given the same chain.

## Removed
- 8 files byte-identical to vanilla (they would only freeze old art on future patches).
- 7 `mapicon_*` files at `gfx/interface/`; the game reads them from
  `gfx/interface/mapicons/`, so they were never loaded.

## Unchanged by design
- No file in a checksummed folder, so the game checksum stays vanilla:
  Ironman achievements and multiplayer work without host/client mismatches.
