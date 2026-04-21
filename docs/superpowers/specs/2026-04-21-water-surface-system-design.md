# Water Surface System — Design

**Date:** 2026-04-21
**Status:** Spec approved, pending implementation plan
**Parent project:** Boat tower family. This is sub-project 1 of 3; sub-projects 2 (Boat 000) and 3 (Boat 100) follow in separate specs.

## Purpose

Add a single lake to the game map so water-placed towers (starting with the planned Boat family) have somewhere to go. Introduce a minimal surface-type abstraction in the tower data model so a tower can declare "I go on water" without duplicating the placement system.

## Scope (what this sub-project delivers)

1. A single authored lake in `game.unity`, visible with gentle vertex-bob animation.
2. A new Unity `Water` layer, tagged on the lake's collider.
3. A `SurfaceType { Land, Water }` declaration per tower in `TowerCosts`, defaulted so existing towers continue to place on land unchanged.
4. `TowerPlacer` routes the placement raycast against the matching surface layer per tower type.

No boat, no boat art, no attack components — those are sub-projects 2 and 3.

## Non-goals (YAGNI)

- Multiple lakes, rivers, or coastline.
- Foam or edge effects where water meets land.
- Reflections, caustics, refraction.
- Amphibious towers (any tower placeable on both surfaces).
- Enemy interaction with water (swimming, water paths, water-only enemies).
- Procedural / randomised lake shape. The lake is authored once per map.

## Architecture

### New files

- **`Assets/Blender/blender_lake.py`** — authoring script. Follows the existing Blender-pipeline convention (hardcoded absolute paths, exports `.fbx` to `Assets/Models/`). Generates the lake mesh by:
  1. Creating a filled disk.
  2. Deforming the boundary with hand-tuned noise parameters to produce an irregular blob outline.
  3. Subdividing the interior finely enough that per-vertex bob animation looks smooth (~400–900 verts is plenty).
  4. Exporting `Assets/Models/lake.fbx`.
  The script is deterministic — running it twice produces the same mesh. Re-run only if the author wants a different shape.

- **`Assets/Scripts/WaterLake.cs`** — pure animation component. No mesh generation.
  - `Start()`: copy the MeshFilter's vertex buffer into a cached array of original positions. Grab the MeshRenderer's material instance.
  - `Update()`: for each vertex `v`, compute `y = originalY + bobAmplitude * sin(time * bobFrequency + phase(v.x, v.z))`. Write back to a working vertex array and `mesh.vertices = working` (assigning to `.vertices` reuploads; that's fine for a small mesh). Update material color via `Color.Lerp(colorA, colorB, 0.5 + 0.5*sin(time*colorFrequency))` on `_BaseColor`.
  - Inspector fields: `bobAmplitude`, `bobFrequency`, `colorA`, `colorB`, `colorFrequency`.

### Modified files

- **`Assets/Scripts/TowerCosts.cs`**
  - Add `public enum SurfaceType { Land, Water }`.
  - Extend `TowerInfo` with a `SurfaceType surface` field.
  - New constructor overload; existing entries keep default `Land`.
  - Add `public static SurfaceType GetSurface(string towerType)`.

- **`Assets/Scripts/TowerPlacer.cs`**
  - Add `[SerializeField] private LayerMask _waterLayer;` alongside `_groundLayer`.
  - In the placement `Update()`, replace the single-mask `Physics.Raycast(..., _groundLayer)` with a mask chosen from `TowerCosts.GetSurface(_placingType)`: `Land` → `_groundLayer`, `Water` → `_waterLayer`.
  - `CheckOverlap` unchanged. Path and tower-overlap checks still apply.

### Scene changes (`game.unity`)

- New GameObject `Lake`:
  - `MeshFilter` → `Assets/Models/lake.fbx`.
  - `MeshRenderer` with a URP Unlit material (blue, adjustable via `WaterLake`'s `colorA`/`colorB`).
  - `MeshCollider` (non-convex).
  - `WaterLake` component.
  - Layer: `Water`.
- The enemy path (authored in `Waypoints`) must not cross the lake area. This is an authoring constraint, not code-enforced.

### Unity project settings

- Add a user layer named `Water` (first free slot).
- The ground mesh stays on its existing ground layer.

## Data flow

1. Player clicks a tower button → `TowerPlacer.BeginPlacement(type)` stores `_placingType`.
2. `TowerPlacer.Update()` reads `TowerCosts.GetSurface(_placingType)` and picks `_groundLayer` or `_waterLayer` for the ray.
3. Raycast hits only the matching surface. Preview snaps to the hit point.
4. `CheckOverlap` still rejects: overlap with any non-ground collider, and points on the enemy path.
5. Click places the tower; rest of `PlaceTower()` is unchanged.

## Error handling

- `TowerCosts.GetSurface` on an unknown tower type returns `Land` (safe default).
- If `_waterLayer` is unset and a water tower is chosen, the raycast mask is `0` and nothing will be placeable — a visible bug, not a silent failure. No fallback needed; this is caught during manual testing.
- `WaterLake.Update()` is a no-op if the MeshFilter's mesh is null (guard with early return).

## Testing

No automated tests (project has no NUnit / PlayMode suites per `CLAUDE.md`).

Manual verification in play mode:
- Lake renders, bobs gently, colour shifts.
- `tack000` and `sniper000` still place anywhere on land. They cannot place on the lake.
- With a temporary test entry (e.g. a dummy `waterprobe000` with `SurfaceType.Water`), preview only follows the lake and rejects land.

## Open questions

None blocking. Lake position/size/shape are authoring decisions made in Blender + Unity scene; the spec does not pin them.

## Out-of-spec follow-ups

- Sub-project 2 (`Boat 000`) will introduce the first real `SurfaceType.Water` tower and exercise this system.
- Sub-project 3 (`Boat 100`) consumes the same system; no further changes to this layer expected.
