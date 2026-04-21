# Water Surface System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single authored lake to the game map and introduce a `SurfaceType { Land, Water }` abstraction so water-placed towers can be built later.

**Architecture:** The lake is a Blender-authored mesh (`lake.fbx`) dropped into `game.unity` on Unity's built-in `Water` layer (layer 4). A small `WaterLake` MonoBehaviour animates the surface (vertex-bob + color lerp). `TowerCosts` gains a `SurfaceType` enum per tower; `TowerPlacer` picks the raycast layer-mask accordingly. No boat or water tower is shipped in this sub-project.

**Tech Stack:** Unity 6 (URP), C#, Blender Python (for asset authoring).

---

## Ground truth (relevant state you won't guess)

- **No test framework.** Project has no NUnit / PlayMode suite. "Verify the test passes" in this plan means either (a) compile cleanly via `mcp__UnityMCP__read_console` or (b) manually observe the behaviour in Unity's Play Mode.
- **Existing noise in `read_console`:** `CLAUDE.md` lists pre-existing warnings in `FloatingText.cs`, `TowerSelection.cs`, `Movement.cs`, `GroundGenerator.cs`, `SilentKnightSetup.cs` (all `CS0618` deprecations + `CS0414` unused fields). Ignore these when scanning for new breakage.
- **Ground layer is layer 8** (hardcoded in `TowerPlacer.CheckOverlap`: `if (col.gameObject.layer == 8) continue; // Ground layer`).
- **Water layer is Unity's built-in layer 4** ("Water"). Do not create a new user layer — use the default one. Verify via `Edit → Project Settings → Tags and Layers` or by inspecting the `LayerMask` inspector popup.
- **UI is code-built**, not scene-authored. Do NOT look for placement panels in the scene hierarchy — they live in `TowerPlacer.BuildShopPanel`.
- **Blender scripts use hardcoded absolute paths** starting `C:\Users\LachlanB\TD\...`. Keep this convention.
- **UnityMCP tools drive the editor.** After any `.cs` edit: call `mcp__UnityMCP__refresh_unity` then `mcp__UnityMCP__read_console` with `{"action":"get","types":["error","warning"]}`.

---

## Task 1: Add `SurfaceType` to `TowerCosts`

**Files:**
- Modify: `Assets/Scripts/TowerCosts.cs`

- [ ] **Step 1: Add the enum, extend `TowerInfo`, and add the accessor**

Edit `Assets/Scripts/TowerCosts.cs`. Add the enum just below the `using` line, replace the `TowerInfo` struct, and add a `GetSurface` method.

At top of file (inside the `TowerCosts` class body, before `TowerInfo`):

```csharp
public enum SurfaceType { Land, Water }
```

Replace the existing `TowerInfo` struct with:

```csharp
public struct TowerInfo
{
    public int cost;
    public string iconPath;
    public float range;
    public SurfaceType surface;

    public TowerInfo(int cost, string iconPath, float range, SurfaceType surface = SurfaceType.Land)
    {
        this.cost = cost;
        this.iconPath = iconPath;
        this.range = range;
        this.surface = surface;
    }
}
```

Add next to the other public static accessors (after `GetRange`):

```csharp
public static SurfaceType GetSurface(string towerType)
{
    return _towerInfo.TryGetValue(towerType, out var info) ? info.surface : SurfaceType.Land;
}
```

Do NOT change any existing `_towerInfo` entries — they continue to use the default `SurfaceType.Land` via the optional constructor parameter.

- [ ] **Step 2: Compile-check**

Call `mcp__UnityMCP__refresh_unity`, then `mcp__UnityMCP__read_console` with `{"action":"get","types":["error","warning"]}`.
Expected: no new errors. Pre-existing warnings listed under "Ground truth" above are acceptable.

- [ ] **Step 3: Commit**

```bash
git add Assets/Scripts/TowerCosts.cs
git commit -m "add SurfaceType to TowerCosts"
```

---

## Task 2: Route `TowerPlacer` raycast by surface

**Files:**
- Modify: `Assets/Scripts/TowerPlacer.cs`

- [ ] **Step 1: Add the `_waterLayer` serialized field**

In `Assets/Scripts/TowerPlacer.cs`, just below the existing `_groundLayer` declaration (around line 11), add:

```csharp
[SerializeField] private LayerMask _waterLayer;
```

- [ ] **Step 2: Pick the raycast mask per tower's surface**

In `TowerPlacer.Update()` (around line 334), replace:

```csharp
if (Physics.Raycast(ray, out RaycastHit hit, 500f, _groundLayer))
```

with:

```csharp
LayerMask mask = TowerCosts.GetSurface(_placingType) == TowerCosts.SurfaceType.Water
    ? _waterLayer
    : _groundLayer;
if (Physics.Raycast(ray, out RaycastHit hit, 500f, mask))
```

Leave `CheckOverlap` unchanged. The path-collision and tower-overlap checks still apply, which is what we want.

- [ ] **Step 3: Compile-check**

Call `mcp__UnityMCP__refresh_unity`, then `mcp__UnityMCP__read_console` with `{"action":"get","types":["error","warning"]}`.
Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add Assets/Scripts/TowerPlacer.cs
git commit -m "route tower placement raycast by surface type"
```

---

## Task 3: Write the Blender authoring script

**Files:**
- Create: `Assets/Blender/blender_lake.py`

- [ ] **Step 1: Create `Assets/Blender/blender_lake.py`**

Write this exact content:

```python
import bpy
import math
import random
from mathutils import Vector

# ── Paths ─────────────────────────────────────────────────────────────────────
BLEND_DST = r"C:\Users\LachlanB\TD\Assets\Blender\lake.blend"
FBX_PATH  = r"C:\Users\LachlanB\TD\Assets\Models\lake.fbx"

# ── Parameters (hand-tune here, then re-run the script) ──────────────────────
LAKE_RADIUS      = 2.5
BOUNDARY_VERTS   = 32      # polygon count around the rim before noise
BOUNDARY_NOISE   = 0.35    # +/- fraction of radius applied per rim vertex
SUBDIVISIONS     = 4       # extra cuts for bob animation granularity
SEED             = 7

random.seed(SEED)

# ── Start with an empty scene ─────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)

# ── Build the blob ────────────────────────────────────────────────────────────
bpy.ops.mesh.primitive_circle_add(
    vertices=BOUNDARY_VERTS,
    radius=LAKE_RADIUS,
    fill_type='NGON',
)
lake = bpy.context.active_object
lake.name = "Lake"

# Jitter each rim vertex radially to produce an irregular outline.
mesh = lake.data
for v in mesh.vertices:
    d = v.co.length
    if d > 0.01:
        factor = 1.0 + (random.random() - 0.5) * BOUNDARY_NOISE
        v.co.x *= factor
        v.co.y *= factor

# Subdivide the interior so per-vertex bob is smooth at runtime.
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
for _ in range(SUBDIVISIONS):
    bpy.ops.mesh.subdivide()
bpy.ops.object.mode_set(mode='OBJECT')

# ── Material (starting colour; WaterLake component lerps it at runtime) ──────
mat = bpy.data.materials.new(name="LakeWater")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.15, 0.45, 0.75, 1.0)
bsdf.inputs["Roughness"].default_value  = 0.20
bsdf.inputs["Metallic"].default_value   = 0.0
lake.data.materials.clear()
lake.data.materials.append(mat)

bpy.ops.object.shade_smooth()

# ── Save and export ───────────────────────────────────────────────────────────
bpy.ops.wm.save_as_mainfile(filepath=BLEND_DST)
print(f"Saved: {BLEND_DST}")

bpy.ops.export_scene.fbx(
    filepath=FBX_PATH,
    use_selection=False,
    object_types={'MESH'},
    bake_anim=False,
    add_leaf_bones=False,
    axis_forward='-Z',
    axis_up='Y',
    global_scale=1.0,
)
print(f"Exported lake: {FBX_PATH}")
print("Done!")
```

- [ ] **Step 2: Commit the script (FBX produced in next task)**

```bash
git add Assets/Blender/blender_lake.py
git commit -m "add blender script to author lake mesh"
```

---

## Task 4: Run the Blender script to produce `lake.fbx`

This task is a developer action outside Unity. Blender must be installed.

**Files:**
- Create: `Assets/Blender/lake.blend` (script output, committed)
- Create: `Assets/Models/lake.fbx` (script output, committed)

- [ ] **Step 1: Run Blender headless with the script**

From a shell:

```bash
blender --background --python "C:/Users/LachlanB/TD/Assets/Blender/blender_lake.py"
```

If `blender` is not on PATH, invoke the full install path (typical: `"C:/Program Files/Blender Foundation/Blender 4.x/blender.exe"`).

Expected tail of stdout:
```
Saved: C:\Users\LachlanB\TD\Assets\Blender\lake.blend
Exported lake: C:\Users\LachlanB\TD\Assets\Models\lake.fbx
Done!
```

- [ ] **Step 2: Verify outputs exist**

```bash
ls Assets/Blender/lake.blend Assets/Models/lake.fbx
```

Expected: both files listed.

- [ ] **Step 3: Let Unity import the FBX**

Call `mcp__UnityMCP__refresh_unity`, then `mcp__UnityMCP__read_console` with `{"action":"get","types":["error","warning"]}`.
Expected: no import errors for `lake.fbx`.

- [ ] **Step 4: Commit the produced assets**

```bash
git add Assets/Blender/lake.blend Assets/Models/lake.fbx Assets/Models/lake.fbx.meta
git commit -m "generate lake mesh"
```

---

## Task 5: Create `WaterLake.cs` animation component

**Files:**
- Create: `Assets/Scripts/WaterLake.cs`

- [ ] **Step 1: Write the component**

Create `Assets/Scripts/WaterLake.cs` with this exact content:

```csharp
using UnityEngine;

[RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
public class WaterLake : MonoBehaviour
{
    [SerializeField] private float bobAmplitude = 0.05f;
    [SerializeField] private float bobFrequency = 1.2f;
    [SerializeField] private Color colorA = new Color(0.15f, 0.45f, 0.75f);
    [SerializeField] private Color colorB = new Color(0.20f, 0.55f, 0.85f);
    [SerializeField] private float colorFrequency = 0.5f;

    private Mesh _mesh;
    private Vector3[] _originalVerts;
    private Vector3[] _workingVerts;
    private Material _materialInstance;

    void Start()
    {
        var mf = GetComponent<MeshFilter>();
        if (mf == null || mf.sharedMesh == null) return;

        // Per-instance mesh copy so vertex mutation doesn't leak to the asset.
        _mesh = Instantiate(mf.sharedMesh);
        mf.mesh = _mesh;

        _originalVerts = _mesh.vertices;
        _workingVerts = new Vector3[_originalVerts.Length];

        _materialInstance = GetComponent<MeshRenderer>().material;
    }

    void Update()
    {
        if (_mesh == null) return;

        float t = Time.time;
        for (int i = 0; i < _originalVerts.Length; i++)
        {
            var o = _originalVerts[i];
            float phase = o.x * 0.8f + o.z * 1.2f;
            _workingVerts[i] = new Vector3(
                o.x,
                o.y + bobAmplitude * Mathf.Sin(t * bobFrequency + phase),
                o.z);
        }
        _mesh.vertices = _workingVerts;
        _mesh.RecalculateNormals();

        if (_materialInstance != null)
        {
            float k = 0.5f + 0.5f * Mathf.Sin(t * colorFrequency);
            _materialInstance.color = Color.Lerp(colorA, colorB, k);
        }
    }
}
```

- [ ] **Step 2: Compile-check**

Call `mcp__UnityMCP__refresh_unity`, then `mcp__UnityMCP__read_console` with `{"action":"get","types":["error","warning"]}`.
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add Assets/Scripts/WaterLake.cs Assets/Scripts/WaterLake.cs.meta
git commit -m "add WaterLake animation component"
```

---

## Task 6: Add the `Lake` GameObject to `game.unity`

This task edits the scene. Use UnityMCP tools (they're the canonical way per `CLAUDE.md`). The scene file (`Assets/game.unity`) is YAML; do not edit it directly.

**Files:**
- Modify: `Assets/game.unity`

- [ ] **Step 1: Ensure `game.unity` is the loaded scene**

Call `mcp__UnityMCP__manage_scene` with `{"action":"load","name":"game","path":"Assets"}` (or equivalent for your MCP version — check `manage_scene`'s docstring via the tool).

- [ ] **Step 2: Create the `Lake` GameObject**

Call `mcp__UnityMCP__manage_gameobject`:
- action: `create`
- name: `Lake`
- Position: somewhere outside the enemy path. A safe default for the current map is `(5, 0.01, 3)`. The small Y offset keeps the water fractionally above the ground plane. Adjust later if it clips through a terrain feature.
- Layer: `4` (built-in Water layer)

- [ ] **Step 3: Add `MeshFilter` and assign `lake.fbx`**

Call `mcp__UnityMCP__manage_components`:
- target: `Lake`
- action: `add`
- component type: `MeshFilter`

Then set its `sharedMesh` to the mesh inside `Assets/Models/lake.fbx`. If the tool can't set sub-asset references directly, fall back to opening the scene in Unity and dragging the mesh onto the slot. The mesh object inside `lake.fbx` will be named `Lake` (from the Blender script's `lake.name = "Lake"`).

- [ ] **Step 4: Add `MeshRenderer`**

Call `mcp__UnityMCP__manage_components`:
- target: `Lake`
- action: `add`
- component type: `MeshRenderer`

Material is assigned automatically from the FBX import (the `LakeWater` material the script created). `WaterLake.Start()` will instance it at runtime.

- [ ] **Step 5: Add `MeshCollider`**

Call `mcp__UnityMCP__manage_components`:
- target: `Lake`
- action: `add`
- component type: `MeshCollider`
- properties: `convex = false`

The `MeshCollider.sharedMesh` should auto-populate from the `MeshFilter`; if it does not, set it explicitly to the same mesh used in Step 3.

- [ ] **Step 6: Add the `WaterLake` component**

Call `mcp__UnityMCP__manage_components`:
- target: `Lake`
- action: `add`
- component type: `WaterLake`

Leave the inspector values at their defaults — they're already tuned in the script.

- [ ] **Step 7: Save the scene**

Call `mcp__UnityMCP__manage_scene` with `{"action":"save"}`.

- [ ] **Step 8: Commit**

```bash
git add Assets/game.unity
git commit -m "add Lake scene object"
```

---

## Task 7: Wire `_waterLayer` on the `TowerPlacer` inspector

The `_waterLayer` field was added in Task 2 but no Unity component instance has a value set for it yet.

**Files:**
- Modify: `Assets/game.unity`

- [ ] **Step 1: Find the `TowerPlacer` component instance**

Call `mcp__UnityMCP__find_gameobjects` searching by component type `TowerPlacer`. Note the GameObject name it returns (likely the scene's main manager object).

- [ ] **Step 2: Set `_waterLayer` to the `Water` layer (layer 4)**

Call `mcp__UnityMCP__manage_components` on that GameObject:
- action: `modify`
- component: `TowerPlacer`
- property: `_waterLayer`
- value: a LayerMask covering only layer 4. In LayerMask integer form that's `1 << 4 = 16`.

Also confirm `_groundLayer` remains set to its existing value (ground layer = 8 → mask `256`). Do not change it.

- [ ] **Step 3: Save the scene**

Call `mcp__UnityMCP__manage_scene` with `{"action":"save"}`.

- [ ] **Step 4: Commit**

```bash
git add Assets/game.unity
git commit -m "wire water layer on TowerPlacer"
```

---

## Task 8: Manual play-mode verification (positive path)

No automated test. Drive Unity via MCP to run Play Mode and observe.

- [ ] **Step 1: Enter Play Mode**

Call `mcp__UnityMCP__manage_editor` with `{"action":"play"}`.

- [ ] **Step 2: Observe**

- Lake renders in blue near `(5, 0, 3)` and its surface visibly bobs.
- The colour lerps gently between `colorA` and `colorB` over a few seconds.
- Due to `DEV_AUTO_PLACE` in `TowerPlacer`, `tack000`, `sniper000`, and `knight000` spawn at their dev positions. Confirm they spawn on land and none spawn inside the lake.
- Click the Tack or Sniper shop button and move the mouse. The preview follows the cursor over ground. Move the cursor over the lake: the preview should stop following (no ray hit on land layer there) — i.e. placement refuses over water.

- [ ] **Step 3: Stop Play Mode**

Call `mcp__UnityMCP__manage_editor` with `{"action":"stop"}`.

- [ ] **Step 4: Read the console for new errors**

`mcp__UnityMCP__read_console` with `{"action":"get","types":["error"]}`.
Expected: no new runtime errors introduced by Lake/WaterLake.

No commit in this step — observation only. If the verification fails, fix the responsible task before proceeding.

---

## Task 9: Manual verification of the water-placement code path

The spec requires verifying that a `SurfaceType.Water` tower actually follows the lake. The simplest way without prematurely building the boat is to flip `tack000` to `Water` temporarily.

**Files:**
- Modify: `Assets/Scripts/TowerCosts.cs` (will be reverted)

- [ ] **Step 1: Temporarily mark `tack000` as `Water`**

In `Assets/Scripts/TowerCosts.cs`, change the `tack000` entry from:

```csharp
{ "tack000", new TowerInfo(300, "UI/tack_icon", 3f) },
```

to:

```csharp
{ "tack000", new TowerInfo(300, "UI/tack_icon", 3f, SurfaceType.Water) },
```

- [ ] **Step 2: Also disable the dev auto-place temporarily**

In `Assets/Scripts/TowerPlacer.cs`, change:

```csharp
private static readonly bool DEV_AUTO_PLACE = true;
```

to:

```csharp
private static readonly bool DEV_AUTO_PLACE = false;
```

(Otherwise `DevPlaceTower("tack000", DEV_TACK_POS)` will place the tack tower on land regardless of surface type; dev auto-place bypasses the raycast.)

- [ ] **Step 3: Compile, enter Play Mode, verify**

Call `mcp__UnityMCP__refresh_unity`, then `mcp__UnityMCP__manage_editor` with `{"action":"play"}`.

- Click the Tack shop button.
- Move the cursor over land: preview does NOT follow (no hit on water layer).
- Move the cursor over the lake: preview DOES follow the cursor and snaps to the water surface.
- Click on the lake — Tack tower places on the water. This is obviously silly visually (tack tower on water) — it's only confirming the layer plumbing works.

Then call `mcp__UnityMCP__manage_editor` with `{"action":"stop"}`.

- [ ] **Step 4: Revert the two changes**

Revert the `tack000` entry in `TowerCosts.cs` back to the original `Land` (omit the `SurfaceType.Water` argument).

Revert `DEV_AUTO_PLACE` in `TowerPlacer.cs` back to `true`.

Verify via `git diff` that both files now match what was committed at the end of Tasks 1 and 2.

- [ ] **Step 5: Final compile-check**

Call `mcp__UnityMCP__refresh_unity`, then `mcp__UnityMCP__read_console` with `{"action":"get","types":["error","warning"]}`.
Expected: no new errors.

No commit. This task only produces evidence that the plumbing is correct; the reverts leave the repo identical to the end of Task 8.

---

## Done criteria

- `lake.fbx` exists in `Assets/Models/` and imports without errors.
- `Lake` GameObject is in `game.unity`, on layer 4, with `WaterLake` animating.
- `TowerCosts.SurfaceType` exists; `tack000` and `sniper000` both remain `Land`.
- `TowerPlacer._waterLayer` is serialised and wired to layer 4 in the scene.
- Existing play-mode behaviour for `tack000`, `sniper000`, and `knight000` is unchanged.
- Task 9 evidence confirmed water routing works end-to-end.

Final state leaves no feature flags or partial implementations. Sub-project 2 (Boat 000) builds on top by adding the first real `SurfaceType.Water` tower.
