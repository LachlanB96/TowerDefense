---
name: blender-model-mode
description: Primes the session for Gloomfell Blender modelling — the modelling rules, the render-and-pick workflow, and the Blender traps that have actually bitten. Starts by asking the user what they want to work on. Invoke ONLY when the user explicitly types /blender-model-mode. Never auto-invoke, even when Blender, modelling, or the preview harness come up in conversation.
---

# Blender Model Mode

You are now the modeller for **Gloomfell**, a tower-defense game in Unity 6. Its 3D
assets are not sculpted by hand — they are *built by Python scripts* that drive Blender
headlessly. You change a model by changing code, running a build, and looking at the
render.

---

## STOP. Ask before you do anything.

**Your first action after reading this file is a question to the user. Not a tool call.**

Ask which they want:

> **1.** Start a new model
> **2.** Work on an existing model

Then follow route 1 or route 2 below.

Until they answer, do **not**:

- read or list asset scripts, `.blend` files, or design docs
- run a build, a preview, or an audit
- go looking for defects, or report any problem you happen to notice

This matters. This skill is not about any one asset. A previous version of it was
written around the knight, and a freshly-primed agent went straight to auditing the
knight and reported a defect the user had not asked about. Assume nothing about which
model is in play, and do not volunteer findings. If you spot something alarming while
doing requested work, mention it in one line and let the user decide whether to chase it.

---

## Route 1 — starting a new model

1. **Ask what it is.** A hero, an enemy unit, a tower, a prop, a piece of environment?
   What is it called? What should it read as at a glance?

2. **Agree the code name.** Heroes and units are `<name>000` (`knight000`). Towers use a
   3-digit path-tier code — each digit is the tier in paths 1/2/3, so `tack000` is the
   base and `tack210` is tier 2 in path 1 and tier 1 in path 2. Confirm the name before
   creating files; it becomes the script name, the folder name and the Unity prefab key.

3. **Find or write the design doc.** Look for `Obsidian/TD/Heroes/<Name>.md` or
   `Obsidian/TD/Towers/<Name>/Base.md`. If one exists it is the intent — read it before
   writing any geometry. If not, ask the user enough to work from, and offer to write the
   doc first so the intent is recorded somewhere other than the code.

4. **Create the script, conforming from the start.**
   `Assets/Blender/blender_<asset>.py`. Copy the skeleton from
   `Assets/Blender/_tools/_selftest_asset.py` — it is the shortest complete example of a
   conforming script. Four requirements:
   - every tunable value is a module-level global, set before the build runs
   - a single top-level build call
   - the `# --- variant hook ---` block immediately before that call
   - `render_view()` honours `RENDER_ONLY`, and save/export sit behind `DO_SAVE` /
     `DO_EXPORT`

   Get this right on day one. Retrofitting it later is how the other eight scripts ended
   up unusable by the harness.

5. **Create the audit.** `Assets/Blender/_<asset>/audit_<asset>.py`. Start with the four
   checks that apply to any asset — non-manifold meshes, geometry below the floor,
   left/right mirror symmetry, and the rule-1 levitation check. Copy them from
   `Assets/Blender/_knight000/audit_knight000.py`. If a third asset ever needs them,
   extract a shared module instead of copying a third time.

6. **Blockout, then iterate.** Build the rough forms, render it, and go round the loop
   below. Do not try to land the finished model in one pass.

---

## Route 2 — working on an existing model

1. **Show the user what exists and let them pick.** Enumerate live — do not work from a
   list in this file, it will go stale:

   ```bash
   for f in Assets/Blender/blender_*.py; do
     n=$(basename "$f" .py); n=${n#blender_}
     grep -q "variant hook ---" "$f" && echo "  $n  [conforming]" || echo "  $n"
   done
   ```

2. **Check whether it conforms.** Only a script marked `[conforming]` can be driven by
   the preview harness. The rest save and export unconditionally the moment they run, so
   the harness refuses them outright — see gotcha 1. Opting one in is a small, separate
   job; ask the user before doing it.

3. **Read the design doc, then the script.** The doc in `Obsidian/TD/` is the intent; the
   code may lag behind it. Entries marked TBD are common and normal.

4. **Ask what they want changed.** Then do that. Do not audit the model, hunt for
   defects, or report unrelated problems unless asked.

---

## The rules

> **This section belongs to the user. Edit it freely — it is the whole point of this file.**
> `[checked]` means a script verifies it and a violation fails the build.
> `[craft]` means it relies on your judgement.

**1. No levitating or disconnected parts.** `[checked]`
Every part must touch or overlap another part. Nothing hovers unless I say so
explicitly. A pauldron floating 4cm off the shoulder is a defect even if it looks fine
from the front. Deliberate exceptions — glows, auras, floating runes — are listed in
`FLOATERS_OK` in the asset's audit script; ask me before adding one.

**2. Silhouette first.** `[craft]`
The model must still name the character at 184×184 — Steam app-icon size — with every
interior detail lost. Spikes, plumes, flares and stance do that work. If the outline
reads as a blob, the model has failed regardless of how good the detail is.

**3. Trim draws the form.** `[craft]`
Bright metal alone flattens into a featureless blob under any key light. Outline plate
boundaries in a contrasting trim so the internal lines survive downscaling the way an
inked drawing does. On the Silent Knight that trim is gold.

**4. Dark recesses.** `[craft]`
Undersides, interiors and mail voiders use a near-black material. Without them a glowing
element has nothing to glow *against* and just reads as a smudge.

**5. Rounded armour, never visible cubes.** `[craft]`
Everything reads as forged armour, not as the primitives it was built from. This is the
difference between a finished asset and a blockout.

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

## The loop

### Always render variants and let the user pick

**Do not commit a visual change the user has not seen and chosen.** Every change comes
back as 2–4 numbered options, rendered side by side.

For an open aesthetic question the variants are genuine alternatives (barbute vs great
helm vs sallet). For a defect with one obvious outcome they are *different approaches to
the fix* (rotate the wrist, shrink the guard, move the grip) — the user still sees the
result rendered before it lands, which is the point.

Number them 1/2/3 and ask by number. The gallery numbers its columns the same way.

### Getting the gallery in front of the user

The user sees renders in a browser tab, not in the terminal. Before the first preview of
a session:

1. **Start the server in the background.** It runs forever and never exits — starting it
   in the foreground will block you until the call times out.

   ```bash
   python Assets/Blender/_tools/serve.py     # MUST be run in the background
   ```

   **Kill any existing server before starting one.** `serve.py` sets
   `allow_reuse_address`, and on Windows that means a second instance binds to 8777
   silently instead of failing — you then cannot tell which process is answering, and a
   "restart" leaves the old one serving the old page. Check first:

   ```bash
   # PowerShell: find anything already on 8777, and stop it before restarting
   Get-NetTCPConnection -State Listen -LocalPort 8777 -EA SilentlyContinue |
     ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
   ```

   A server left running from an earlier session is otherwise harmless — reuse it rather
   than starting a second, unless `gallery/index.html` has changed (gotcha 7).

2. **Tell the user to open `http://localhost:8777/` and leave the tab open.** Say it in
   plain words — they will not find it on their own. The page polls once a second and
   redraws itself, so they open it once per session and never touch it again.

3. Only then run a preview. The page follows whichever asset was built most recently, so
   a brand-new asset appears on its own with no configuration.

### Commands

Replace `<asset>` with the code name agreed above.

```bash
# Render variants in parallel (3 ≈ 20s)
python Assets/Blender/_tools/preview.py <asset> --variants v.json

# Objective geometry check
python Assets/Blender/_tools/preview.py <asset> --audit

# Only once the user has picked: the real build
"/c/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b \
    -P Assets/Blender/blender_<asset>.py -- save export render
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

Previews are non-destructive: they never write the `.blend` or the `.fbx`. Only the last
command does, and only after the user has chosen.

### Adding a checked rule

When the user gives a rule that can be verified mechanically, add the check to that
asset's audit script, append it to the `fails` list so it turns the result to FAIL, and
tag the rule `[checked]` in the rules section. Do not invent a separate rules file — this
file is the only config.

---

## Gotchas

These have all actually cost time. They are not hypothetical.

1. **Seven of the nine asset scripts save and export unconditionally at module scope.**
   Simply running one rebuilds the asset and overwrites its `.blend` and `.fbx`, with no
   undo. `preview.py` refuses any script without the variant hook for exactly this
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

5. **Axes:** characters face **-Y** in Blender (the front orthographic view), so forward
   is `-Y` and the character's right is `-X`. With the export axes in the scripts this
   lands facing `+Z` in Unity. Z-up, origin on the ground between the feet.

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
