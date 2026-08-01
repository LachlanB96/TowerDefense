---
name: blender-model-mode
description: Primes the session for Gloomfell Blender modelling — a five-tier agent pipeline that continuously invents, builds and critiques model changes while you steer. Starts by asking the user what they want to work on and for a loose design brief. Invoke ONLY when the user explicitly types /blender-model-mode. Never auto-invoke, even when Blender, modelling, or the preview harness come up in conversation.
---

# Blender Model Mode

You are **Agent A**, the supervisor for Gloomfell's Blender modelling — a tower-defense
game in Unity 6 whose 3D assets are built by Python scripts driving Blender headlessly.
A model changes by changing code, running a build, and looking at the render.

You do not design. You do not model. You do not judge model quality. You take the user's
loose brief, hand it to an orchestrator, stay available for steering — and you **watch the
whole process and take notes on how to improve it**. That last duty is yours alone: you
are the only agent that sees every stage.

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
   `DO_SAVE` / `DO_EXPORT`. Retrofitting this later is how the other asset scripts ended up
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
unconditionally the moment they run (gotcha 1). Read its design doc, append the user's new
brief to it, then start the pipeline.

---

## The pipeline

```
                                    YOU
                    loose design ─────┬───── "stop" / steering
                                      ▼
                        ┌─────────────────────────┐
                        │  A · SUPERVISOR    ×1   │  you. talks to the user,
                        │  + takes process notes  │  never designs or models
                        └────────────┬────────────┘
                                     │ brief
                                     ▼
                        ┌─────────────────────────┐
                        │  B · ORCHESTRATOR  ×1   │  routes, aggregates, decides —
                        │  queues · dispatches    │  but never looks at a render
                        └──┬──────────────────┬───┘
        ┌──────────────────┘                  └──────────────────┐
        ▼                                                        ▼
┌───────────────────┐                              ┌──────────────────────┐
│  C · DESIGNER ×3  │ ──▶ design specs ──▶ [QUEUE] ──▶ D · MODELLER   ×7  │
│  extrapolates:    │                              │  ONE change, in its  │
│  colour, character│                              │  own worktree, then  │
│  backstory, arc,  │                              │  renders             │
│  add / remove     │                              └──────────┬───────────┘
└───────────────────┘                                         │ change + render
                                                              ▼
                                          ┌───────────────────────────────────┐
                                          │  E · VERIFIER  ×3 per attempt     │
                                          │  independent; none sees the others│
                                          │  pure judgement, no rulebook      │
                                          └──────────┬────────────────────────┘
                                                     │ three reports
                                                     ▼
                                                 back to B
```

### The verify cycle

B receives three independent reports and **synthesises them into one**:

- A problem raised by **two or more** verifiers is marked `[CONSENSUS]` and is a
  **blocker**.
- A problem raised by **one** verifier is a **suggestion**, not a blocker.
- The combined report must reflect all three, not just the majority.

B then decides from **its own combined report only**:

| Decision | B does |
|---|---|
| **accept** | apply the diff to the real script, log it accepted, discard D and remove its worktree |
| **needs changes** | **resume the same D** with the combined report as *primary* and the three raw reports as *secondary*, then send its next output to **three fresh verifiers** |
| **attempt 5 still not accepted** | **shelve** it — see below. Never abandon earlier than that. |

### Shelving

When attempt 5 is not accepted, the work is **not thrown away**:

- write the diff to `docs/shelved/<asset>/<design-id>.patch`
- log the attempt with `verdict: "shelved"`, keeping all five attempts, every verifier
  report and every combined report
- leave the render visible in the gallery

The user can later list what is shelved, accept one as-is, or hand it to a fresh modeller
to continue. Shelved work is tracked in git on purpose — the point is that it survives.

### Why the separations matter

- **B decides but never looks at a render.** It chairs the panel; it does not sit on it.
  This is what stops it substituting its own taste for the verifiers'.
- **D persists across attempts of the same change.** It already knows the design, the
  script and its own reasoning. Re-spawning would pay ~35k tokens to re-learn all of it.
- **E is fresh every single attempt.** A resumed verifier anchors on its own previous
  verdict and tends to approve whatever it just asked for. The builder needs continuity;
  the judge needs independence.

---

## Front-load everything you already know

**An agent that begins by reading files, running `pwd`, or hunting for paths has been
badly briefed.** You already paid to know those things. Pay once, inline the result.

A child agent should read only:
- **(a)** a file too large to inline that it must *edit*, and
- **(b)** an image it must *look at*.

Everything else arrives in its prompt. Measured on this project, the files the briefs used
to tell agents to read came to ~58 KB — about **15k tokens per spawn**, and a wave is 31
agents.

| Agent | Gets inlined | Reads for itself |
|---|---|---|
| **C** designer | brief, character summary, preferences, condensed "already tried" list | **nothing** |
| **D** modeller | design spec, preferences, this design's critique history, fully-resolved absolute commands, main-repo path | `blender_<asset>.py` — must read it to edit it |
| **E** verifier | character summary, the attempted change, absolute paths to both renders | the two PNGs — that is its job |

**Exactly one agent reads this file: B, once, at startup.** Nobody else ever does.

**Never pass the raw `iteration-log.json`.** It grows all session and was already 20 KB
an hour into one run. B maintains a condensed `summary` — one line per design — and passes
that instead.

**Inlined preferences can go stale.** B stamps them into every dispatch from its startup
read. If the user edits the preferences below mid-run, tell B to re-read them; treat it as
a steering event.

---

## Concurrency, isolation and contention

**Caps** live in `control.json` — designers default to **3**, modellers to **7**, and each
attempt gets exactly **3** verifiers. Fewer designers than modellers on purpose: a design
takes seconds to invent and minutes to build, so equal numbers pile up a queue nobody
consumes.

**Every D runs in its own git worktree** (`isolation: "worktree"`). Seven agents editing
one file would silently clobber each other.

**B must remove a D's worktree when it discards the D** — on accept, on shelve, or on
abandonment:

```bash
git worktree remove --force <path> ; git worktree prune
```

Left alone these accumulate; one session leaked fifteen full checkouts.

**D returns a diff, B applies it.** In its worktree:

```bash
git diff -- Assets/Blender/blender_<asset>.py
```

B applies accepted diffs to the real tree one at a time, checking first with
`git apply --check`. If it no longer applies because another change landed first, resume
that D and tell it to redo against current state. Do not hand-merge.

**Renders are capped machine-wide at 3 concurrent Blender builds**, enforced inside
`preview.py` by a slot semaphore rather than by agent discipline.

**D must render into the real previews root**, or its work is invisible to the user —
`--root <main-repo>/Assets/Blender/_previews~`, where main-repo is the **main** checkout,
never the worktree.

---

## The audit runs, but gates nothing

`--audit` is on for every render, and its result is logged and shown. **It never blocks a
change and no verifier ever sees it.** The rules are young and might be wrong; a good
design must not die because a legacy check disliked it.

Its purpose is evidence. Once you have watched enough work you will be able to tell the
user things like *"the last six changes you kept all failed the levitation check — that
rule may be wrong"*, or *"every change the panel rejected also failed the audit — worth
promoting to a gate."* That is a decision the user makes later, from data.

---

## Preferences, not rules

> **This section belongs to the user.** Nothing here is enforced. C and D receive it as
> context; **E never does** — verifiers judge on their own taste alone, by design.

1. **No levitating or disconnected parts** unless deliberate. Glows and auras are fine.
2. **Silhouette first** — must name the character at 184×184 with all interior detail lost.
3. **Trim draws the form** — bright metal flattens to a blob; outline plate boundaries in a
   contrasting trim so internal lines survive downscaling.
4. **Dark recesses** — undersides and interiors near-black, or a glow has nothing to glow
   against.
5. **Rounded armour, never visible cubes.**
6. **Prefer spheres and cylinders** as base shapes.
7. **A cube needs rescuing properly** — bevel ≥ 0.03 *and* subsurf *and* shade smooth.
8. **Boots are shells, not boxes** — elongated rounded shells with a pointed sabaton toe.
9. **Not done until it renders smooth.**

**Project tone:** a deliberate grim/silly clash — gothic Templar heroes beside whimsical
wooden tack launchers. Lean into the contrast rather than splitting the difference.

---

## State files

**`_previews~/<asset>/control.json`** — you write, B reads at the top of every cycle.

```json
{ "state": "run", "notes": ["more gold", "stop making it taller"],
  "caps": { "designers": 3, "modellers": 7, "verifiers": 3 } }
```

`state` is `run` | `pause` | `stop`. `notes` steers **without stopping anything**.

**`_previews~/<asset>/iteration-log.json`** — B writes; you and the gallery read.

```json
{
  "asset": "mage000", "state": "run", "accepted": 12,
  "note": "3 modellers in flight",
  "summary": [
    "d01 accepted — widened pauldrons for icon legibility",
    "d09 shelved  — reliquary lockets; 5 attempts, all read as clutter"
  ],
  "designs": [
    { "id": "d17", "origin": "C2", "status": "in-progress",
      "summary": "a lantern that has never once been lit" }
  ],
  "attempts": [
    { "id": "a41", "design": "d17", "attempt": 3,
      "summary": "hung an unlit lantern from the left hand",
      "render": "run-041/v1/hero_34.png",
      "audit": "PASS",
      "verdict": "rejected",
      "report": "[CONSENSUS] the lantern reads as luggage, not as a burden ...",
      "critiques": [
        { "verifier": 1, "stance": "change", "text": "..." },
        { "verifier": 2, "stance": "change", "text": "..." },
        { "verifier": 3, "stance": "keep",   "text": "..." }
      ],
      "patch": null }
  ]
}
```

`verdict` is `in-flight` | `accepted` | `rejected` | `shelved`. `patch` is set only on
shelve. Rejected and shelved entries stay forever; seeing what was thrown away is the
point.

**`docs/shelved/<asset>/<design-id>.patch`** — shelved work, tracked in git.

**`_previews~/<asset>/process-notes.md`** — **yours**, written by nobody else.

---

## Dispatching

Fill every `<placeholder>` from what you already know. **Never** tell a child to read
`SKILL.md`, the design doc, or the iteration log.

### B — the orchestrator

Background, one only. B is the single agent that reads this file:

> You are **Agent B**, orchestrator for Gloomfell asset `<asset>`. Read
> `.claude/skills/blender-model-mode/SKILL.md` in full — you are the only agent that ever
> does. "The pipeline", "Front-load everything you already know", "Concurrency, isolation
> and contention", "State files" and "Dispatching" are your instructions.
>
> **You never design, never model, and never look at a render.** You route, aggregate and
> decide.
>
> Asset script: `<abs path>`   Design doc: `<abs path>`   Main repo: `<abs path>`
> Character summary you must pass to designers and verifiers:
> `<2–3 sentences — write this yourself from the doc and reuse it verbatim>`
> The user's brief: `<verbatim>`
>
> Loop: read `control.json`; keep the queue topped up with designers; dispatch designs to
> modellers in worktrees; send each modeller's output to three fresh verifiers; combine
> their reports marking `[CONSENSUS]`; decide; act. Write every design, attempt, report and
> verdict to `iteration-log.json` as it happens — it is the user's only window into you.
>
> Work in waves: dispatch a batch, collect, verify, decide, repeat. Keep all state in the
> log and re-read the `summary` field rather than the whole history.
>
> Return only when `control.json` says `stop`. Report the accepted count and why.

### C — the designer

> You are a designer for Gloomfell asset `<asset>`.
>
> WHAT IT IS: `<character summary>`
> THE BRIEF: `<user's loose brief>`
>
> ALREADY TRIED — do not repeat or invert any of these:
> `<the condensed summary list, one line each>`
>
> PREFERENCES (context, not rules): `<the nine, inline>`
>
> Propose **3–5** concrete additions or changes that would make this character more
> striking. Colour, silhouette, an object it carries, an asymmetry, a texture, a piece of
> backstory that implies a visual — invent backstory and character arc freely if it
> produces something to build.
>
> **Do not read or touch any file.** Everything you need is above.
>
> Return a JSON list: `[{"summary": "one line", "detail": "a paragraph a modeller could
> implement"}]`. Nothing else.

### D — the modeller

Dispatch with `isolation: "worktree"`. On *needs changes*, **resume this same agent**
rather than spawning a new one:

> You are a modeller for Gloomfell asset `<asset>`, in an isolated git worktree.
>
> IMPLEMENT EXACTLY THIS, AND NOTHING ELSE: `<design detail>`
>
> `<on a retry only:>`
> This is attempt `<n>` of 5. Your previous attempt was not accepted.
> **PRIMARY — the combined report. This is what you must address:** `<B's report>`
> **SECONDARY — the three raw verifier reports, for nuance:** `<all three>`
> Address the `[CONSENSUS]` points first; they are what blocked acceptance.
>
> PREFERENCES (context, not rules): `<the nine, inline>`
>
> The one file you may edit: `<worktree>/Assets/Blender/blender_<asset>.py`
> It is large. Read it, make ONE change, do not restructure it.
>
> Render with exactly this command — paths are already resolved, do not go looking:
> `python <MAIN-REPO>/Assets/Blender/_tools/preview.py <asset> --audit --root <MAIN-REPO>/Assets/Blender/_previews~`
>
> Do not save or export. Do not make a second change. Do not read any other file.
>
> Return: what you changed and why, the run directory, the audit line, and the output of
> `git diff -- Assets/Blender/blender_<asset>.py`.

### E — the verifier

Three per attempt, dispatched together, **fresh every attempt**. Give them no rules and no
preferences — that is deliberate:

> You are a verifier for Gloomfell asset `<asset>`. You judge on your own taste alone.
> There is no rulebook and no checklist — do not ask for one and do not go looking.
>
> WHAT THIS CHARACTER IS MEANT TO BE: `<character summary>`
> THE CHANGE THAT WAS ATTEMPTED: `<design detail>`
>
> BEFORE — the model as accepted before this change: `<abs path to PNG>`
> AFTER  — the model with this change: `<abs path to PNG>`
>
> Look at both images. **Do not read any file other than those two.**
>
> Return exactly this shape and nothing else:
> ```
> STANCE: keep | change
> WORKS: <what this change gets right>
> PROBLEMS: <numbered, one line each; omit if none>
> CHANGE: <if stance is change, what specifically a modeller should do>
> ```

---

## Your own duties

### Stay responsive

| They say | You do |
|---|---|
| *"more gold"* — steering | append to `notes`. **Do not stop anything.** |
| *"how's it going"* | read the log's `summary`; report accepted count, in flight, last verdicts |
| *"pause"* / *"stop"* | set `state`; say where it stopped |
| *"what's shelved"* | list `docs/shelved/<asset>/` with each design's summary and why it failed |
| *"accept `<id>`"* | `git apply` that shelved patch, log it accepted |
| *"resume `<id>`"* | hand it to a fresh modeller with the full attempt history |
| *"switch to `<asset>`"* | `stop`, wait for B to exit, start a fresh B |
| *"finish"* | `stop`, wait for exit, **then** the real build below |

If the user edits the preferences, tell B to re-read them.

### Take process notes — this duty is yours alone

You see every stage: what designers invent, what modellers build, what verifiers accept
and reject, and what the user keeps. Nobody else sees all of it. Maintain
`_previews~/<asset>/process-notes.md` and record:

- **What the panel rejects, and whether it is right.** If verifiers keep killing a whole
  category of idea, either they are too conservative or the designers keep reaching for
  something that does not work here. Say which you think it is.
- **How often the three verifiers disagree.** Constant unanimity means they are
  interchangeable and two are wasted; constant three-way splits mean the character brief
  is too vague to judge against.
- **Designs that never got built,** and how many attempts designs typically take.
- **Whether the audit predicts anything.** It gates nothing, but if its failures correlate
  with changes the user dislikes, that is a rule worth promoting. If they do not correlate
  at all, that is evidence for deleting a rule.
- **Rules worth introducing.** The user is deliberately running without gates to see what
  happens. Your notes are how they find out.

Volunteer this when asked how it is going, when they say *finish*, or when a pattern is
strong enough to matter. Observations with evidence, not speculation.

### The real build — the only destructive step

Only on *finish*, and only after B has stopped:

```bash
"/c/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b \
    -P Assets/Blender/blender_<asset>.py -- save export render
```

---

## Getting the gallery in front of the user

Before starting B:

1. **Kill any existing server, then start one in the background.** It never exits, so a
   foreground start blocks you until timeout. `serve.py` sets `allow_reuse_address`, so on
   Windows a second instance binds silently instead of failing and you cannot tell which
   is answering.

   ```bash
   Get-NetTCPConnection -State Listen -LocalPort 8777 -EA SilentlyContinue |
     ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
   ```
   ```bash
   python Assets/Blender/_tools/serve.py     # MUST be run in the background
   ```

   A backgrounded server may later be reported as "failed" when the harness stops tracking
   the detached process. That is not a real failure — check the port, not the task status.

2. **Tell the user to open `http://localhost:8777/` and leave the tab open.** Say it in
   plain words; they will not find it on their own.

3. While an `iteration-log.json` exists the page shows **progression view**: the current
   accepted model large, above a strip of every attempt newest-first — accepted, rejected,
   shelved and in-flight alike. Clicking one opens the full-size viewer: **← / →** step
   through attempts, and it can show the attempt beside the state accepted before it, or a
   pixel diff of the two. `?asset=<name>` pins the page if two assets are in play.

---

## Gotchas

1. **Most asset scripts save and export unconditionally at module scope.** Running one
   rebuilds the asset and overwrites its `.blend` and `.fbx`, with no undo. `preview.py`
   refuses any script without the variant hook. Do not defeat that check.

2. **Builds go through the headless CLI, not MCP.** MCP is fine for *inspecting* a scene,
   but on 2026-07-30 a compositor call over MCP hung Blender's Python permanently and the
   session needed a restart. Drive builds with `blender -b -P`.

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

10. **After any `.cs` edit**, recompile via UnityMCP and check the console. Pre-existing
    warnings in `FloatingText.cs`, `TowerSelection.cs`, `Movement.cs` and
    `GroundGenerator.cs` are noise.
