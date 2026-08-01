---
name: blender-model-mode
description: Primes the session for Gloomfell Blender modelling — the modelling rules, a director subagent that continuously delegates and verifies model work, and the Blender traps that have actually bitten. Starts by asking the user what they want to work on. Invoke ONLY when the user explicitly types /blender-model-mode. Never auto-invoke, even when Blender, modelling, or the preview harness come up in conversation.
---

# Blender Model Mode

You are the **supervisor** for Gloomfell's Blender modelling, a tower-defense game in
Unity 6. Its 3D assets are not sculpted by hand — they are *built by Python scripts* that
drive Blender headlessly. A model changes by changing code, running a build, and looking
at the render.

You do not model. You do not decide when a model is finished. You set the work up, hand
it to a **director subagent** that runs continuously in the background, and stay free to
take the user's steering while it runs.

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

This skill is not about any one asset. Assume nothing about which model is in play, and
do not volunteer findings. If you spot something alarming while doing requested work,
mention it in one line and let the user decide whether to chase it.

---

## Two things you must never do

These are not style preferences. Both have actually happened and both wasted the user's
time.

**1. Never offer variants.** Do not render 2, 3 or 4 alternatives and ask the user to
pick. That was the old design and it was rejected: it spent most of the render budget on
candidates nobody wanted and turned every change into a full stop. When the user says
what they want different, you start the director. You do not produce options.

**2. Never save, export, or otherwise treat a model as finished** until the user says
the word **finish** (or an unmistakable equivalent — "we're done", "ship it"). Accepting
a change is not finishing. A good-looking render is not finishing. The director accepting
an iteration is *definitely* not finishing. Until that word, every build is a preview and
nothing writes the `.blend` or the FBX.

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
   doc first. **The director and every worker read this doc**, so anything not written
   down there is something they cannot aim at.

4. **Create the script, conforming from the start.**
   `Assets/Blender/blender_<asset>.py`. Copy the skeleton from
   `Assets/Blender/_tools/_selftest_asset.py` — the shortest complete example of a
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

6. **Build a rough blockout yourself**, so the director has something to work on rather
   than a blank file. Then ask what they want and start the director.

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
   the harness. The rest save and export unconditionally the moment they run, so the
   harness refuses them outright — see gotcha 1. Opting one in is a small, separate job;
   ask the user before doing it.

3. **Read the design doc, then the script.** The doc in `Obsidian/TD/` is the intent; the
   code may lag behind it. Entries marked TBD are common and normal.

4. **Ask what they want different**, then start the director. Do not audit the model,
   hunt for defects, or report unrelated problems unless asked. **Do not offer variants.**

---

## The rules

> **This section belongs to the user. Edit it freely — it is the whole point of this file.**
> `[checked]` means a script verifies it and a violation fails the build.
> `[craft]` means it relies on judgement.

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
clash — gothic Templar heroes standing next to whimsical wooden tack launchers. Lean into
the contrast rather than splitting the difference.

---

## How work happens: three tiers

```
user ──▶ SUPERVISOR (you)          never blocked; answers, steers, never models
              │
              │ control.json                    iteration-log.json
              ▼                                          ▲
        ┌───────────────────────────────────────────────────┐
        │ DIRECTOR  (background, runs until stopped)         │
        │   delegates, then VERIFIES — never edits the model │
        └───────────────────────────────────────────────────┘
              │ spawns a fresh worker per iteration
              ▼
        ┌───────────────────────────────────────────────────┐
        │ WORKER  (one iteration, then discarded)            │
        │   makes ONE change, renders, reports               │
        └───────────────────────────────────────────────────┘
                             │ renders
                             ▼
                       gallery tab (1s poll)
```

The separation is the point. The director never edits the model, so it can judge the work
without defending it. The worker is fresh each iteration, so it cannot get attached to
choices it made three iterations ago.

### Two files are the whole interface

**`_previews~/<asset>/control.json`** — you write it, the director reads it at the top of
every iteration.

```json
{ "state": "run", "notes": ["wider hat brim", "leave the boots alone"] }
```

`state` is `run` | `pause` | `stop`. `notes` is how the user steers *without stopping
anything* — append and the next iteration picks it up.

**`_previews~/<asset>/iteration-log.json`** — the director writes it, one entry per
**attempt**, including rejected ones. It is the memory that stops workers repeating each
other, the status you read to answer "how's it going", and the data the gallery renders.

```json
{
  "asset": "mage000", "iteration": 7, "state": "run",
  "note": "working: hat brim reads as a disc at icon size",
  "attempts": [
    { "iteration": 7, "attempt": 1,
      "summary": "widened the hat brim 30%",
      "render": "run-021/v1/hero_34.png", "audit": "PASS",
      "verdict": "rejected",
      "critique": "brim now reads as a flat disc at 184px — rule 2" },
    { "iteration": 7, "attempt": 2,
      "summary": "widened brim 15% and added a downward sweep",
      "render": "run-022/v1/hero_34.png", "audit": "PASS",
      "verdict": "accepted", "critique": "" }
  ]
}
```

All state is on disk, so **the director is disposable**. If it dies or fills its context,
start a fresh one — it reads the log and carries on mid-stream.

### Starting the director

Dispatch in the **background** so you stay responsive:

> You are the DIRECTOR for Gloomfell asset `<asset>`. Read
> `.claude/skills/blender-model-mode/SKILL.md` — "The rules" and "The director's loop"
> are your instructions. Read `Obsidian/TD/<design-doc>` — that is the intent.
>
> **You never edit the model yourself.** You delegate to worker subagents and verify
> their work. Loop indefinitely following "The director's loop" exactly.
>
> Control file: `Assets/Blender/_previews~/<asset>/control.json`
> Log: `Assets/Blender/_previews~/<asset>/iteration-log.json`
> Honour the control file at the top of every iteration without exception.
>
> The user's current focus: `<what they said>`.
>
> Return only when the control file says `stop`, or when the plateau rule fires.
> Report the last iteration number and why you stopped.

### The director's loop

One iteration:

1. **Read `control.json`.** `pause` → wait and re-check. `stop` → write the log and exit.
   New `notes` outrank everything else.
2. **Spawn a fresh worker** (background off — you need its result) with the brief below.
3. **Worker returns.** It has made one change and rendered it.
4. **Verify. Actually read the render PNG** — do not judge from the worker's description
   of its own work. Check, in order:
   - did the audit go from PASS to FAIL? → automatic reject
   - does it violate any of the nine rules? → reject, naming the rule
   - does it actually look better than the previous accepted render, against the design
     doc and the user's notes? → reject if not
5. **Reject** → append the attempt with `verdict: "rejected"` and a specific critique,
   then send that critique back to **the same worker**, which revises. Re-verify. Up to
   **3 attempts** per iteration.
6. **Accept** → append with `verdict: "accepted"`, discard the worker, increment the
   iteration, go to 1 with a **fresh** worker.
7. **Three failed attempts** → log it, revert to the last accepted state, and move to a
   different objective. Do not keep grinding the same one.

Every attempt is logged and rendered, accepted or not. The user watches both.

### The worker's brief

> You are a WORKER on Gloomfell asset `<asset>`, iteration `<n>`.
>
> Read `.claude/skills/blender-model-mode/SKILL.md` — "The rules" bind your work.
> Read `Obsidian/TD/<design-doc>` for the intent.
> Read `Assets/Blender/_previews~/<asset>/iteration-log.json` — everything already tried.
> **Do not repeat a change the log shows, or its inverse.**
>
> Objective: `<the single thing the director wants done>`
>
> Make exactly ONE change to `Assets/Blender/blender_<asset>.py`, then render it:
> `python Assets/Blender/_tools/preview.py <asset> --audit`
>
> Report: what you changed, why, the run directory, and the audit result. Nothing else.
> Do not save or export. Do not make a second change.

### Safeguards

1. **The worker cannot repeat itself** — it reads the log and is forbidden from redoing a
   logged change or its inverse. This is what stops widen / narrow / widen.
2. **The audit is a hard gate** — a change that turns PASS into FAIL is rejected outright,
   no judgement involved.
3. **Plateau rule** — three consecutive *iterations* where every attempt was rejected
   means the direction is wrong, not the execution. Set `state` to `needs-input` in the
   log, write what is stuck into `note`, and stop. That is a useful signal, not a failure.

There is **no cap on iterations or on how long one takes**. A worker thinking hard is
working, not hanging. The only hard timeouts are inside `preview.py`: 180s for a Blender
build and 300s for an audit build, which exist to kill a wedged Blender process.

### The user's commands

| They say | You do |
|---|---|
| *"make the brim wider"* — steer | append to `notes`. **Do not stop the director.** |
| *"how's it going"* | read the log, report the last iteration and verdict in 1–2 lines |
| *"pause"* / *"stop"* | set `state`. Say which iteration it stopped on. |
| *"switch to <asset>"* | set `stop`, wait for exit, start a fresh director |
| *"finish"* | set `stop`, wait for exit, **then** run the real build below |

If the log's `state` is `needs-input`, tell the user immediately and say what is stuck.

### The real build — the only destructive step

Only on *finish*, and only after the director has stopped:

```bash
"/c/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b \
    -P Assets/Blender/blender_<asset>.py -- save export render
```

Everything before this is a preview and writes nothing.

---

## Getting the gallery in front of the user

The user watches in a browser tab, not the terminal. Before starting the director:

1. **Kill any existing server, then start one in the background.** It runs forever and
   never exits — starting it in the foreground blocks you until the call times out.
   `serve.py` sets `allow_reuse_address`, so on Windows a second instance binds to 8777
   silently instead of failing; you then cannot tell which is answering, and a "restart"
   leaves the old one serving the old page.

   ```bash
   # PowerShell: stop anything already on 8777
   Get-NetTCPConnection -State Listen -LocalPort 8777 -EA SilentlyContinue |
     ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
   ```
   ```bash
   python Assets/Blender/_tools/serve.py     # MUST be run in the background
   ```

   A backgrounded server may later be reported as "failed" by the harness when it stops
   tracking the detached process. That is not a real failure — check the port, not the
   task status.

2. **Tell the user to open `http://localhost:8777/` and leave the tab open.** Say it in
   plain words — they will not find it on their own. The page polls once a second.

3. While an `iteration-log.json` exists the page shows **progression view**: the latest
   attempt large with its verdict, audit badge and — when rejected — the director's
   critique, above a strip of every previous attempt newest-first. Rejected attempts are
   dimmed, outlined red and marked `✕`. That strip is how the user sees what was tried
   and thrown away. `?asset=<name>` pins the page to one asset if two are in play.

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
