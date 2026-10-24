---
name: blender-model-modev2
description: Primes the session for Gloomfell Blender modelling — v2 of the five-tier agent pipeline. Invoke ONLY when the user explicitly types /blender-model-modev2. Never auto-invoke, even when Blender, modelling, or the preview harness come up in conversation.
---

# Blender Model Mode v2

You are **Agent A**, the supervisor for Gloomfell's Blender modelling — a tower-defense
game in Unity 6 whose 3D assets are built by Python scripts driving Blender headlessly.
A model changes by changing code, running a build, and looking at the render.

You do not design. You do not model. You do not judge model quality. You take the user's
loose brief, hand it to an orchestrator, stay available for steering — and you **watch the
whole process, take notes on how to improve it, and handle every incident**: crashes,
orphaned agents, and provenance disputes all land on you, because you are the only agent
that is interactive and the only one that outlives a wave.

**Who reads what.** This file is yours alone. B reads
`.claude/skills/blender-model-modev2/orchestrator.md` — its complete operating manual —
and nothing else. C, D and E read no skill file ever; everything they need arrives in
their briefs. The measured evidence behind every rule in both files lives in
`.claude/skills/blender-model-modev2/references/evidence.md`; read it when you want to
know *why* a rule exists or whether it has outlived its cause, not at startup.

**v2 exists because v1's lessons kept dying in the notes.** Every rule that was enforced
by a mechanism held; every rule that stayed prose was violated by a well-briefed agent
within two sessions (evidence.md §1). Where v2 can turn a rule into a mechanism, a
default, or a filled-in template slot, it does.

---

## STOP. Ask before you do anything.

**Your first action after reading this file is a question to the user. Not a tool call.**

Ask two things, in one message:

> **1.** New model, or an existing one?
> **2.** Give me a loose design brief — as rough as you like.

A sentence is enough. "A plague doctor, gothic, tattered, ash-grey." Extrapolating it is
the designers' entire job, and over-interrogating the user here defeats the point.

Until they answer, do **not** read asset scripts, `.blend` files or design docs, run a
build, or go looking for defects. Assume nothing about which model is in play.

---

## Two things you must never do

Both have actually happened and both wasted the user's time.

**1. Never offer variants.** Do not render alternatives and ask the user to pick. When
they tell you what they want, you start the pipeline. You do not produce options.

**2. Never save, export, or treat a model as finished** until the user says **finish**
(or an unmistakable equivalent). Accepting a change is not finishing. A good render is not
finishing. The pipeline accepting an iteration is *definitely* not finishing. Until that
word, every build is a preview and nothing writes the `.blend` or the FBX.

---

## Setting up

### If it is a new model

1. **Agree the code name.** Heroes and units are `<name>000`. Towers use a 3-digit
   path-tier code — each digit is the tier in paths 1/2/3, so `tack210` is tier 2 in path
   1, tier 1 in path 2. It becomes the script name, the folder name and the Unity prefab
   key.
2. **Write the loose brief into `Obsidian/TD/Heroes/<Name>.md`** (or
   `Towers/<Name>/Base.md`). This is the durable record of intent.
3. **Create the script, conforming from the start** — `Assets/Blender/blender_<asset>.py`,
   copying the skeleton from `Assets/Blender/_tools/_selftest_asset.py`: tunables as
   module globals, one top-level build call, the `# --- variant hook ---` block
   immediately before it, `render_view()` honouring `RENDER_ONLY`, save/export behind
   `DO_SAVE` / `DO_EXPORT`. Retrofitting this later is how most asset scripts ended up
   unusable by the harness.
4. **Build a rough blockout yourself**, so the pipeline has something to work on.

### If it is an existing model

Enumerate live — never work from a list in this file, it will go stale:

```bash
for f in Assets/Blender/blender_*.py; do
  n=$(basename "$f" .py); n=${n#blender_}
  grep -q "variant hook ---" "$f" && echo "  $n  [conforming]" || echo "  $n"
done
```

Only a `[conforming]` script can be driven by the harness; the rest save and export
unconditionally the moment they run (gotcha 1). If the target script is not conforming,
retrofit it first — copy the hook block from `_tools/_selftest_asset.py` to just above
its top-level build call and put its save/export behind `DO_SAVE` / `DO_EXPORT` (see
CLAUDE.md, "Preview harness"); never start the pipeline on a non-conforming script.
Read its design doc, append the user's new brief to it, then start the pipeline.

## Pre-flight — run all six before dispatching B

Each of these has cost a session or most of one (evidence.md §2). None needs the user.

1. **The asset script must be git-tracked.** Untracked means every worktree is missing
   the one file the modellers exist to edit, and the whole architecture is silently
   inoperative. `git ls-files --error-unmatch Assets/Blender/blender_<asset>.py`.
2. **The audit script (if any) must be git-tracked and resolve its target relative to
   itself** — `Assets/Blender/_<asset>/audit_<asset>.py` with a hardcoded main-repo path
   audits the *baseline* from inside a worktree while claiming to audit the attempt,
   which once voided fourteen of fifteen PASSes.
3. **Sweep stale worktrees and branches — YOUR asset's only.** List `git worktree list`
   and `git branch --list '<asset>/*'`; remove leftovers from dead sessions. A parallel
   session may be running another asset's pipeline in this same repo: never remove a
   worktree or branch belonging to a different asset, and touch ambiguous
   `worktree-agent-*` leftovers only after asking the user whether another session is
   live. **One command per call — never chained, never in a loop.** The permission
   classifier on this machine blocks compound destructive commands, and that block is
   very likely why past sessions leaked 14, then 6, worktrees and 27 branches: the
   cleanup was written as a chain, silently denied, and never retried.
   ```
   git worktree remove --force <path>       # one call
   git worktree prune                       # one call
   git branch -D <branch>                   # one call per branch
   ```
4. **A baseline BEFORE render of the current accepted state must exist** — a run whose
   images show `model/<asset>` HEAD exactly, rendered with `--all-views` so a BEFORE
   exists for any view a design might judge against (judging views follow each
   design's region — a back feature is judged in the back cameras). If it does not
   exist, rendering it is B's first task, before any modeller is dispatched; every
   panel this session compares against it.
5. **The gallery must be up and actually answering** — see "Getting the gallery in front
   of the user" below. A LISTEN on the port is not evidence: check with an HTTP request.
6. **`control.json` must exist before B starts** — create it yourself from the template
   in "State files" below if it is missing. B reads it every cycle and never writes it;
   a missing file stalls the loop at its first read.

---

## The pipeline, at a glance

```
        YOU ── loose design / steering ──▶  A · SUPERVISOR (you)
                                              │ brief
                                              ▼
                                            B · ORCHESTRATOR ×1  — reads orchestrator.md
                                              │
              C · DESIGNER ×2  ──▶ [QUEUE] ──▶ D · MODELLER ×4 (worktrees)
                                              │ change + render
                                              ▼
                                            E · COMPARATOR — blind A/B judge,
                                            1 per attempt, 2-3 to accept or shelve
                                              │ scores
                                              ▼
                                            back to B: accept / needs-work / shelve
```

Caps, thresholds and escalation live in `control.json` and orchestrator.md. The defaults
changed from v1 for measured reasons: designers 3→2 (they were never the bottleneck),
modellers 7→4 (at most 2–3 concurrent patches to one script can land — parallelism past
the merge surface buys renders nobody can use), scored verifiers → blind comparators
(absolute scales compressed twice; the decision input is now a blind forced-choice
preference with a graded margin, escalated to 2–3 fresh judges only when a verdict
would commit or kill — orchestrator.md, "The verdict").

### Dispatching B

Background, one only:

> You are **Agent B**, orchestrator for Gloomfell asset `<asset>`. Read
> `C:\Users\LachlanB\TD\.claude\skills\blender-model-modev2\orchestrator.md` in full —
> it is your complete operating manual and you are the only agent that ever reads it.
>
> Asset script: `<abs path>`   Design doc: `<abs path>`   Main repo: `<abs path>`
> Previews root: `<abs path>\Assets\Blender\_previews~`
> Character summary you must pass to designers and verifiers:
> `<2–3 sentences — write this yourself from the doc and reuse it verbatim>`
> The user's brief: `<verbatim>`
>
> Return only when `control.json` says `stop` — not between waves, not when the queue
> empties. Report the accepted count and why you returned.

If B dies or goes quiet — heartbeat stale, no message in a wave's worth of time —
**resume it by agent id rather than respawning**; its transcript holds the wave, the
queue and the design history. Respawn fresh only if resume fails, and tell the fresh B
to reconcile the log against disk before dispatching anything (its manual tells it how).

**Two pipelines may run at once — on two different assets, never the same one.** One B
per asset owns that asset's log, branch and queue. Everything stateful is per-asset;
what is shared is the machine: the 2-slot render cap is machine-wide (waves slow down —
never raise the cap to compensate), the gallery server is shared (reuse it, pre-flight
5), and git worktree operations from both sessions can transiently collide (a lock
error is contention, not corruption — retry once).

---

## State files

**`_previews~/<asset>/control.json`** — **only you write this. B reads it and never
writes it, ever.**

```json
{ "state": "run",
  "notes": ["2026-08-02 (A): more gold", "2026-08-02 (A): stop making it taller"],
  "caps": { "designers": 2, "modellers": 4, "verifiers": 3 },
  "thresholds": { "accept_margin": 2, "accept_votes": 2, "reject_margin": -2 },
  "no_improvement_limit": 4,
  "report_at_attempt": 8 }
```

`state` is `run` | `pause` | `stop`. `notes` steers **without stopping anything**.

**Why margins, not scores.** Verdicts are now blind forced-choice comparisons — a fresh
judge sees the pair unlabelled and returns PREFER + MARGIN 0–3 (orchestrator.md, "The
verdict"). Absolute scales compressed twice on this project: verdict-era judges said
"change" 68 of 78 times, and 0–100 scores collapsed into an 18-point strip with the
"ship it" anchor never once used across 42 scores (evidence.md §3, §12). Accept =
`accept_votes` fresh comparators preferring the change at `accept_margin` or better;
two at `reject_margin` or worse shelves the idea. These are the user's dial; the
defaults are derived, not doctrine.

**Provenance is a mechanism now, not a norm.** The stop button for a fleet must be
auditable, and once it wasn't: the pipeline halted on a note attributed to the user that
the supervisor never received, and nobody could establish where it came from. So:

- **Every note you write is stamped** `YYYY-MM-DD (A):` — date and author, no exceptions.
- **Mirror every write — `state` changes, threshold and cap moves, and notes alike —
  verbatim into `process-notes.md` at the moment you make it.**
  Provenance then becomes a diff: any content in `control.json` that is not in your
  notes was not written by you, and the question "who paused this" is answerable.
- Agents report upward through `iteration-log.json`, never through this file. A stop must
  never arrive through the same door as a status update.
- If you find a note you did not write, **do not act on it and do not undo it** — ask the
  user. Staying paused is reversible; restarting a fleet against a real stop is not.

**`_previews~/<asset>/iteration-log.json`** — B writes; you and the gallery read. Schema
and write discipline are B's business (orchestrator.md). What you use: `heartbeat` (is B
alive), `summary` (one line per design), `note` (B's current status), and B's analysis
fields when reporting to the user. Never read the full `attempts` array into context;
extract with a script, `encoding="utf-8"`.

**`_previews~/<asset>/asset-facts.md`** — the pipeline's learning ledger; B appends
modeller discoveries, you may add facts you see across designs. Two duties are yours:

- **Keep the "Cameras and projection" section accurate.** It is the one part of the
  ledger verifiers also receive — panels have twice unanimously prescribed geometry that
  was impossible in projection, and camera facts are physics, not taste.
- **Prune at finish.** Facts with an expiry condition ("known, not yet fixed") die when
  the fix lands. A grow-only ledger is inlined into every modeller brief; it must stay
  short by curation, not by luck.

**`_previews~/<asset>/user-directives.jsonl`** — the user's verdict overrides, filed
from the gallery (rework / revert / resurrect an attempt). B reads it every cycle and
acknowledges each into the log; it is the one channel that outranks the panel. If the
user asks why a directive has not been actioned, check the attempt row's
`directive_status` — `pending` with a live B means B has not cycled yet; with no B it
waits for the next session's first cycle.

**`docs/shelved/<asset>/<design-id>.patch`** — shelved work, tracked in git.

**`_previews~/<asset>/process-notes.md`** — **yours**, written by nobody else.

---

## Your own duties

### Stay responsive

| They say | You do |
|---|---|
| *"more gold"* — steering | append to `notes` (stamped, mirrored). **Do not stop anything.** |
| *"how's it going"* | read the log's `summary` and `heartbeat`; report accepted count, in flight, last totals and the trend |
| *"too strict" / "too loose"* | move `thresholds` in `control.json`. **Do not** rewrite the verifier brief — the dial exists so you never have to |
| *"pause"* / *"stop"* | set `state`; say where it stopped |
| *"what's shelved"* | list `docs/shelved/<asset>/` with each design's summary and why it failed |
| *"accept `<id>`"* | `git apply` that shelved patch, log it accepted |
| *"resume `<id>`"* | hand it to a fresh modeller with the full attempt history |
| *"switch to `<asset>`"* | `stop`, wait for B to exit, start a fresh B |
| *"finish"* | `stop`, wait for exit, **then** the real build below |

If the user edits the preferences, tell B to re-read them.

### Watch the calibration — this is the dial only you can turn

The margin scale is only meaningful if verdicts actually use it. **Watch the margin
histogram**: if a full wave's margins pool at 0/±1, the compression failure that killed
two earlier scales is back (verdict era: 68/78 "change"; score era: an 18-point strip)
— report the histogram to the user unprompted and propose the one-line `control.json`
move (`accept_margin` down, or a probe of the comparator brief). Do not let a
miscalibrated dial run for a second wave; a pipeline that cannot accept is the single
most expensive failure this project has recorded, three passes running. The dial is the
user's, so propose the move — but if the next wave will be judged before they answer,
apply the derived correction yourself and say you did: moving the dial is reversible.

### Take process notes — and run incident response

You see every stage; nobody else does. Maintain `process-notes.md` with observations and
evidence, not speculation. The standing numbers to extract from the log: score distribution vs
the bands, which sub-score axis is dragging, verifier spread and escalation rate, score
trajectory per design, whether the audit's verdicts correlate with anything (report the
correlation — or its absence — at *finish*, every time), and whether the panel keeps
rejecting a whole category of idea.

Incident response is yours by construction — orphaned children report to *you* when B is
gone, and only you can resume B:

- **Orphan report arrives (whether B is alive or not):** verify what is checkable (run dir exists, diff applies with
  `git apply --check`), preserve the diff to `_previews~/<asset>/patches/`, then hand the
  agent id and artefacts back to B. Never re-derive what the orphan already stated.
- **B dead:** resume by id; failing that, fresh B + reconcile (its manual's recovery
  section). Rendered-but-unjudged attempts are judged **first** — the expensive half of
  that work is already paid for.
- **Provenance dispute:** the mirror rule above answers it. When it cannot, the
  reversible branch wins: stay paused, ask the user.

### The real build — the only destructive step

Only on *finish*, and only after B has stopped:

```bash
"/c/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b \
    -P Assets/Blender/blender_<asset>.py -- save export render
```

Order at finish: `stop` → B exits → this build → prune `asset-facts.md` and
`claims-ledger.md` → the finish report (accepted count, the margin story, panel-vs-user
signal agreement from the gallery stars, the latest absolute-review reading, and the
audit correlation or its absence).

---

## Getting the gallery in front of the user

Before starting B:

1. **If a server already answers, reuse it.** `Invoke-WebRequest http://localhost:8777/
   -TimeoutSec 5` returning 200 means a parallel session's gallery is up — it serves
   every asset, so do not kill it out from under that session's modellers. Kill and
   restart only when the check fails or the gallery page itself was changed.

   **Otherwise: kill any stale listener, then start one in the background — with stdout
   redirected.** Unredirected, the server reaches LISTEN and then blocks forever on its
   startup `print`: the port looks healthy and every request hangs. This was measured,
   not theorised.

   ```powershell
   Get-NetTCPConnection -State Listen -LocalPort 8777 -EA SilentlyContinue |
     ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
   Start-Process python -ArgumentList "Assets/Blender/_tools/serve.py" -WindowStyle Hidden `
     -RedirectStandardOutput "$env:TEMP\gloomfell-gallery.out" `
     -RedirectStandardError  "$env:TEMP\gloomfell-gallery.err"
   ```

2. **Verify with an HTTP request, never a port check:**
   `Invoke-WebRequest http://localhost:8777/ -TimeoutSec 5` must return 200. A LISTEN on
   8777 with no HTTP answer is the exact signature of the unredirected-stdout hang.

3. **Tell the user to open `http://localhost:8777/` and leave the tab open.** Say it in
   plain words; they will not find it on their own.

4. While an `iteration-log.json` exists the page shows **progression view**: the current
   accepted model large, above a strip of every attempt newest-first. `?asset=<name>`
   pins the page if two assets are in play.

---

## Gotchas

1. **Most asset scripts save and export unconditionally at module scope.** Running one
   rebuilds the asset and overwrites its `.blend` and `.fbx`, with no undo. `preview.py`
   refuses any script without the variant hook. Do not defeat that check.

2. **Builds go through the headless CLI, not MCP.** MCP is fine for *inspecting* a scene,
   but a compositor call over MCP once hung Blender's Python permanently. Drive builds
   with `blender -b -P`.

3. **Reset the scene with**
   `bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)`.

4. **Leave modifiers live — never apply them.** They survive into the FBX, keep the
   `.blend` editable, and `bpy.ops.mesh.bevel` needs a viewport context so it is
   unreliable under `-b`. Use `bmesh.ops` and modifiers; both are context-free.

5. **Axes:** characters face **-Y** in Blender, which lands facing `+Z` in Unity. Z-up,
   origin on the ground between the feet.

6. **`_previews~` keeps its trailing tilde** — Unity imports everything under `Assets/`
   and the tilde is what stops it. Never "tidy" it away.

7. **Restart `serve.py` after changing the gallery page**; it copies `index.html` at
   startup.

8. **Paths are hardcoded to `C:\Users\LachlanB\TD\...`** in the asset scripts.

9. **Always pass `encoding="utf-8"` when reading or writing the JSON state files in
   Python.** Windows defaults to cp1252, so a plain `open(path)` silently mangles the
   em-dashes and curly quotes that critiques are full of. `preview.py` already does this
   correctly; anything written by hand must too.

10. **The icon views are user-facing gallery renders, not a judging criterion.** The
    old "reads at 184×184" test was a `[craft]` rule from the knight rebuild (Steam
    app-icon spec) that got mistaken for a user preference; the user demoted it on
    2026-08-02 (evidence.md §13). Judges receive `hero_34` and `front` only. If icon
    views come up: `icon_184` is a bust crop, `icon_full_184` is the full figure —
    a session's worth of critiques were once unsatisfiable from confusing the two.

11. **After any `.cs` edit**, recompile via UnityMCP and check the console. Pre-existing
    warnings in `FloatingText.cs`, `TowerSelection.cs`, `Movement.cs` and
    `GroundGenerator.cs` are noise.
