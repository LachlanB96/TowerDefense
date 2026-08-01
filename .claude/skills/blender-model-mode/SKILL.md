---
name: blender-model-mode
description: Primes the session for Gloomfell Blender modelling — the modelling rules, a continuously-iterating modeller subagent you supervise, and the Blender traps that have actually bitten. Starts by asking the user what they want to work on. Invoke ONLY when the user explicitly types /blender-model-mode. Never auto-invoke, even when Blender, modelling, or the preview harness come up in conversation.
---

# Blender Model Mode

You are the **supervisor** for Gloomfell's Blender modelling, a tower-defense game in
Unity 6. Its 3D assets are not sculpted by hand — they are *built by Python scripts* that
drive Blender headlessly. A model changes by changing code, running a build, and looking
at the render.

You do not do the modelling yourself. You set it up, hand it to an **iterator subagent**
that works continuously in the background, and stay free to take the user's steering
while it runs. Your job is to remain responsive; its job is to keep making the model
better.

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

This matters. This skill is not about any one asset. A previous version of it was written
around the knight, and a freshly-primed agent went straight to auditing the knight and
reported a defect the user had not asked about. Assume nothing about which model is in
play, and do not volunteer findings. If you spot something alarming while doing requested
work, mention it in one line and let the user decide whether to chase it.

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
   doc first. **The iterator reads this doc every round**, so anything not written down
   there is something it cannot aim at.

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

6. **Build a rough blockout yourself**, so the iterator has something to work on rather
   than a blank file. Then start the iterator.

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

4. **Ask what they want the iterator to focus on**, then start it. Do not audit the
   model, hunt for defects, or report unrelated problems unless asked.

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

## How work happens: an iterator you supervise

The model improves through a background subagent running one round at a time,
indefinitely, until told otherwise. You stay in the conversation and steer it.

```
user ──▶ you (supervisor)        never blocked; always able to answer
              │
              │ write control.json          read iteration-log.json
              ▼                                      ▲
        ┌──────────────────────────────────────────────┐
        │  iterator subagent  —  one round at a time    │
        └──────────────────────────────────────────────┘
                             │ renders
                             ▼
                       gallery tab (1s poll)
```

### Two files are the whole interface

**`_previews~/<asset>/control.json`** — you write it, the iterator reads it at the top of
every round.

```json
{ "state": "run", "notes": ["wider hat brim", "leave the boots alone"], "cap": 20 }
```

`state` is `run` | `pause` | `stop`. `notes` is how the user steers *without stopping
anything* — append and the next round picks it up. `cap` is how many rounds it may run
before pausing for a check-in.

**`_previews~/<asset>/iteration-log.json`** — the iterator writes it. It does three jobs:
it is the memory that stops the iterator repeating itself, the status you read to tell
the user what is happening, and the data the gallery renders.

```json
{
  "asset": "knight000", "round": 14, "state": "run",
  "note": "working: cape chain links do not interlock",
  "rounds": [
    { "n": 14, "summary": "reconnected cape chain to the gorget",
      "reasoning": "rule 1 — audit flagged 4 orphaned links",
      "render": "run-014/v1/hero_34.png", "audit": "PASS", "reverted": false }
  ]
}
```

Because all state is on disk, **the iterator is disposable**. If it dies or fills its
context, start a fresh one — it reads the log and carries on mid-stream. Do not try to
keep one alive forever.

### Starting the iterator

Dispatch it in the **background** so you stay responsive. Give it the asset, and let it
read this file for the rules rather than copying them into the prompt:

> You are the iterator for Gloomfell asset `<asset>`. Read
> `.claude/skills/blender-model-mode/SKILL.md` — "The rules" and "What one round is"
> are your instructions. Read `Obsidian/TD/<path-to-design-doc>` — that is the intent
> you are working toward.
>
> Loop indefinitely, one round at a time, following "What one round is" exactly. Your
> control file is `Assets/Blender/_previews~/<asset>/control.json` and your log is
> `Assets/Blender/_previews~/<asset>/iteration-log.json`. Honour the control file at
> the top of every round without exception.
>
> The user's current focus: `<what they said>`.
>
> Return only when the control file says `stop`, when you have hit the round cap, or
> when the plateau rule fires. Report the last round number and why you stopped.

### What one round is

1. **Read `control.json`.** `pause` → wait, re-check, do nothing else. `stop` → write the
   log and exit cleanly. New entries in `notes` outrank everything below.
2. **Read the tail of `iteration-log.json`** — what has been tried, what got reverted.
3. **Look at the newest render.** Actually read the PNG. Do not reason from the code.
4. **Critique, in this priority order:** unaddressed user notes → the design doc → the
   nine rules. Pick the single worst problem.
5. **Make exactly one change.** One per round keeps cause and effect legible in the
   gallery strip and makes a revert cheap.
6. **Render:** `python Assets/Blender/_tools/preview.py <asset> --audit`
7. **If the audit went from PASS to FAIL, revert the change.** Record it as
   `"reverted": true` with the reason.
8. **Append the round to the log** — summary, reasoning, render path, audit, reverted.
9. **Plateau check** (below).

A round is roughly 60–90 seconds: the preview render plus the audit's own build, plus
thinking. Say so if the user asks why it is not instant.

### The three safeguards

These are what make open-ended self-critique hold up instead of drifting.

1. **Log before edit.** Check whether the log already shows this change or its inverse.
   If it does, you may not simply repeat it — either leave that area alone, or record
   explicitly why the new value differs. **A parameter touched in the last 3 rounds is
   off-limits** unless a user note names it. This is what stops widen / narrow / widen.
2. **Audit is a hard gate.** Every round runs it. A round that introduces a FAIL is
   reverted, so drift cannot erode rule 1 or the geometry checks.
3. **Plateau detector.** Three consecutive reverts, or the same area churned with no
   user note, means you are out of ideas. Set `state` to `needs-input` in the log, write
   what you are stuck on into `note`, and stop. That is a useful signal, not a failure.

Plus the **round cap** in `control.json` (default 20): pause and report rather than
running silently forever. The user can raise, lower, or remove it.

### The user's four commands

| They say | You do |
|---|---|
| *"make the brim wider"* — steer | append to `notes`. **Do not stop the iterator.** |
| *"pause"* / *"stop"* | set `state`. Confirm which round it stopped on. |
| *"switch to <other asset>"* | set `stop`, wait for it to exit, start a fresh iterator |
| *"finish"* | set `stop`, then run the real save/export build (below) |

Report progress in one or two lines when asked — read the log, do not guess. If the log's
`state` is `needs-input`, tell the user immediately and say what it is stuck on.

### The real build — the only destructive step

Only on *finish*, and only after the iterator has stopped:

```bash
"/c/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b \
    -P Assets/Blender/blender_<asset>.py -- save export render
```

Everything before this is non-destructive: previews never write the `.blend` or the FBX.

### When to render variants instead

The old default was to offer 2–4 numbered variants for every change. That is no longer
the default — it spent most of the render budget on candidates nobody wanted and turned
every change into a stop.

Use variants only when the **user explicitly asks for options**, or when a genuinely
forked aesthetic decision cannot be resolved from the design doc and you need them to
choose a direction. Then:

```bash
python Assets/Blender/_tools/preview.py <asset> --variants v.json
```

```json
[
  {"label": "barbute",  "vars": {"HELM_STYLE": "barbute"}},
  {"label": "sallet",   "vars": {"HELM_STYLE": "sallet"}},
  {"label": "reshaped", "patch": "def build_helmet():\n    ..."}
]
```

`vars` overrides any module-level global. `patch` is Python **source text** replacing a
whole builder — it must be source, not a function object, because it has to bind to the
asset script's own globals. Number the options 1/2/3; the gallery numbers its columns the
same way.

---

## Getting the gallery in front of the user

The user watches in a browser tab, not the terminal. Before starting the iterator:

1. **Kill any existing server, then start one in the background.** It runs forever and
   never exits — starting it in the foreground will block you until the call times out.
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

2. **Tell the user to open `http://localhost:8777/` and leave the tab open.** Say it in
   plain words — they will not find it on their own. The page polls once a second.

3. The page follows whichever asset was built most recently. While an
   `iteration-log.json` exists it switches to **progression view**: the current model
   large with the round's summary, and a strip of previous rounds beneath, newest first,
   reverted ones dimmed and marked `↩`. That strip is how the user tells iteration from
   churn. `?asset=<name>` pins it to one asset if two are in play.

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
