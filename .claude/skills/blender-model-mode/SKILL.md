---
name: blender-model-mode
description: Primes the session for Gloomfell Blender modelling — the modelling rules, the render-and-pick workflow, and the Blender traps that have actually bitten. Invoke ONLY when the user explicitly types /blender-model-mode. Never auto-invoke, even when Blender, modelling, or the preview harness come up in conversation.
---

# Blender Model Mode

You are now the modeller for **Gloomfell**, a tower-defense game in Unity 6. Its 3D
assets are not sculpted by hand — they are *built by Python scripts* that drive Blender
headlessly. You change a model by changing code, running a build, and looking at the
render.

Three things to internalise before you touch anything:

- **The design doc is the intent; the code may lag behind it.** Hero and tower specs live
  in `Obsidian/TD/` (`Heroes/<Name>.md`, `Towers/<Name>/`). Read the doc before the code.
- **Never change a model without showing the user first.** See "How to work" below. This
  is the standing rule, not a suggestion.
- **The rules in section 1 are the user's, not yours.** Follow them. If the user states a
  new preference, add it to that section — do not put it anywhere else.

---

## 1. My rules

> **This section belongs to the user. Edit it freely — it is the whole point of this file.**
> `[checked]` means a script verifies it and a violation fails the build.
> `[craft]` means it relies on your judgement.

**1. No levitating or disconnected parts.** `[checked]`
Every part must touch or overlap another part. Nothing hovers unless I say so
explicitly. A pauldron floating 4cm off the shoulder is a defect even if it looks fine
from the front.

**2. Silhouette first.** `[craft]`
The model must still name the character at 184×184 — Steam app-icon size — with every
interior detail lost. Spikes, plumes, flares and stance do that work. If the outline
reads as a blob, the model has failed regardless of how good the detail is.

**3. Gold draws the form.** `[craft]`
Bright steel alone flattens into a featureless blob under any key light. Outline every
plate boundary in gold trim so the internal lines survive downscaling the way an inked
drawing does.

**4. Dark recesses.** `[craft]`
Mail voiders, plate undersides and helmet interiors use a near-black material. Without
them, a red eye-glow has nothing to glow *against* and just looks like a pink smudge.

**5. Rounded armour, never visible cubes.** `[craft]`
Everything reads as forged armour, not as the primitives it was built from. This is the
difference between a finished character and a blockout.

**6. Prefer spheres and cylinders.** `[craft]`
Reach for a rounded primitive as the base shape wherever possible, rather than starting
from a cube and trying to rescue it.

**7. A cube needs rescuing properly.** `[craft]`
Where a cube is genuinely unavoidable: bevel it (width ≥ 0.03) **and** add subsurf,
**then** shade smooth. All three, not one of them.

**8. Boots are shells, not boxes.** `[craft]`
Feet and boots are elongated rounded shells with a pointed sabaton toe — a scaled sphere
or cylinder, never a box. (This rule exists because cube-based boots shipped once and
looked square.)

**9. Not done until it renders smooth.** `[craft]`
After adding any primitive, confirm it will actually render smooth. Shade smooth plus
bevel or subsurf, or it isn't finished.

**Project tone**, for when a judgement call is genuinely open: a deliberate grim/silly
clash — gothic Templar heroes standing next to whimsical wooden tack launchers. Lean
into the contrast rather than splitting the difference.

---

## 2. How to work

### Always render variants and let the user pick

**Do not commit a visual change the user has not seen and chosen.** Every change comes
back as 2–4 numbered options, rendered side by side.

For an open aesthetic question, the variants are genuine alternatives (barbute vs great
helm vs sallet). For a defect with one obvious outcome, they are *different approaches to
the fix* (rotate the wrist, shrink the guard, move the grip) — the user still sees the
result rendered before it lands, which is the point.

Number them 1/2/3 and ask by number. The gallery numbers its columns the same way.

### The loop

```bash
# 1. Gallery — start once, leave running on the second monitor
python Assets/Blender/_tools/serve.py                    # http://localhost:8777/

# 2. Render variants in parallel (3 ≈ 20s)
python Assets/Blender/_tools/preview.py knight000 --variants v.json

# 3. Objective geometry check
python Assets/Blender/_tools/preview.py knight000 --audit

# 4. Only once the user has picked: the real build
"/c/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b \
    -P Assets/Blender/blender_knight000.py -- save export render
```

A variants file is a JSON list:

```json
[
  {"label": "baseline",    "vars": {}},
  {"label": "short plume", "vars": {"Z_CROWN": 1.92}},
  {"label": "reshaped",    "patch": "def build_helmet():\n    ..."}
]
```

`vars` overrides any module-level global in the asset script. `patch` is Python **source
text** that replaces a whole builder function — it must be source, not a function object,
because it has to bind to the asset script's own globals.

Previews are non-destructive: they never write the `.blend` or the `.fbx`. Only step 4
does, and only after the user has chosen.

### Adding a checked rule

When the user gives a rule that can be verified mechanically, add the check to that
asset's audit script (`Assets/Blender/_<asset>/audit_<asset>.py`), append it to the
`fails` list so it turns the result to FAIL, and tag the rule `[checked]` in section 1.
Do not invent a separate rules file — this file is the only config.

### Making another script usable

Only `blender_knight000.py` currently works with the harness. To opt another one in:
copy the `# --- variant hook ---` block from `Assets/Blender/_tools/_selftest_asset.py`
to sit immediately before the script's top-level build call, put its save/export behind
`DO_SAVE`/`DO_EXPORT`, and make `render_view()` honour `RENDER_ONLY`.

Until then the harness **refuses** to run it, on purpose — see gotcha 1.

---

## 3. Gotchas

These have all actually cost time. They are not hypothetical.

1. **Seven of the nine `blender_*.py` scripts save and export unconditionally at module
   scope.** Simply running one rebuilds the asset and overwrites its `.blend` and `.fbx`,
   with no undo. `preview.py` refuses any script without the variant hook for exactly this
   reason. Do not defeat that check.

2. **Builds go through the headless CLI, not MCP.** The Blender MCP tools are fine for
   *inspecting* a scene. But on 2026-07-30 a compositor call over MCP hung Blender's
   Python permanently — it could not be interrupted, and the session needed a restart. So
   drive builds with `blender -b -P`, and keep MCP for looking, not building.

3. **Reset the scene with**
   `bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)`.
   `read_factory_settings` is blocked inside the MCP sandbox.

4. **Leave modifiers live — never apply them.** They survive into the FBX (the exporter
   evaluates the depsgraph), they keep the `.blend` editable, and `bpy.ops.mesh.bevel`
   and friends need a 3D-viewport context, so they are unreliable under `blender -b`.
   Build with `bmesh.ops` and modifiers instead; both are entirely context-free.

5. **Axes:** the knight faces **-Y** in Blender (the front orthographic view), so forward
   is `-Y`, his right is `-X`. With the export axes in the script this lands facing `+Z`
   in Unity. Z-up, origin between the feet.

6. **`_previews~` keeps its trailing tilde.** Unity imports everything under `Assets/`,
   and the tilde is what stops it generating a `.meta` for every scratch render. Never
   "tidy" it away.

7. **Restart `serve.py` after changing the gallery page.** It copies `index.html` at
   startup, so a long-running instance keeps serving the old version.

8. **Paths are hardcoded to `C:\Users\LachlanB\TD\...`** throughout the asset scripts.
   That matters if the repo ever moves.

9. **After any `.cs` edit**, use the UnityMCP tools to recompile and check the console.
   Pre-existing warnings in `FloatingText.cs`, `TowerSelection.cs`, `Movement.cs` and
   `GroundGenerator.cs` are noise — filter them out when looking for new breakage.
