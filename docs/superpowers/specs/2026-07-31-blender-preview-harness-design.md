# Blender Preview Harness

**Status:** Design
**Date:** 2026-07-31
**Scope:** `Assets/Blender/_tools/` (new), one hook block in `blender_knight000.py`, `.gitignore`

## Problem

The Blender pipeline settled on 2026-07-30 works, but only for one participant. A build
is `blender -b -P blender_knight000.py -- save export render`: ~15 s for a 330-object
character plus ten renders into `Assets/Blender/_knight000/`. Claude then reads those
PNGs with the Read tool and reports back in prose.

Two things are missing, and neither is a small convenience:

1. **Lachlan never sees the renders.** They land in a folder nothing is watching. The
   only channel from the model back to the person deciding what the model should look
   like is Claude's description of it. Describing a silhouette is a poor substitute for
   showing one, and silhouette legibility is the explicit design constraint the knight
   rebuild exists to satisfy.
2. **There is no way to compare alternatives.** Every run produces exactly one variant.
   Offering "three helmets" today means three sequential builds that overwrite each
   other, described one at a time from memory. So alternatives are effectively never
   offered, and design choices get made by whoever describes them first.

The pipeline is also single-asset. Nine `blender_*.py` scripts exist; only
`blender_knight000.py` has the modern shape (argv flag parser, named per-part builder
functions). More heroes are planned, so anything built here should not be knight-shaped.

## Goal

A build harness where:

- Every build's renders appear on Lachlan's second monitor within about a second of the
  build finishing, with no action on his part.
- Claude can render N variants of an asset side by side, numbered, and ask which one —
  answered in the terminal by number, per the `CLAUDE.md` numbering convention.
- Build history is visible, so the model can be watched changing across builds rather
  than only inspected in its current state.
- Any `blender_*.py` script can opt in for roughly one line of change.

## Non-goals

- **No live MCP-driven Blender GUI.** Rejected explicitly. Driving the build through
  MCP is what froze Blender permanently on 2026-07-30 (compositor node-group calls never
  returned, and `TaskStop` cannot interrupt a blocked Blender thread). Headless CLI stays
  the build path; MCP stays reserved for probing API shapes in a scratch scene.
- **No click-to-choose in the browser.** The gallery is view-only. The terminal remains
  the single control surface, which removes the need for a write-back endpoint, a choice
  file, and any polling for the user's answer.
- **No retrofitting of the other eight scripts.** They opt in when next touched, and
  until they do the harness refuses to run them (see "Opting in another script").
  `blender_boat000.py` in particular has uncommitted work in progress.
- **No test framework.** The repo has none; verification is a defined smoke run (below).

## Architecture

```
Lachlan                Claude                       disk                    browser
───────                ──────                       ────                    ───────
                  _tools/preview.py ─┬─ blender -b ──▶ _previews~/knight000/
                  (system Python)    ├─ blender -b ──▶   run-014/
                                     └─ blender -b ──▶     v1/*.png ────────┐
                                        (parallel,          v2/*.png        │
                                         ~15 s each)        v3/*.png        ▼
                                                            manifest.json  gallery
   ◀──────── "1 / 2 / 3 ?" ────────                                        (polls 1 s)
   "2, shorter plume" ──────────▶
```

Three components, each independently understandable and independently testable.

### 1. `_tools/preview.py` — the runner (system Python)

The only entry point Claude calls. Responsibilities:

- Accept an asset name and one or more variant specs. The asset name resolves to
  `Assets/Blender/blender_<asset>.py` by convention — `knight000` → `blender_knight000.py`.
  No registry to maintain; a script that does not follow the naming can be passed by
  explicit path instead.
- Allocate a run directory `_previews~/<asset>/run-NNN/`, `NNN` monotonic per asset,
  zero-padded to three digits.
- Spawn **one `blender -b` process per variant, in parallel.** Variants are independent,
  so three cost about 20 s of wall clock rather than 45 s.
- Write `manifest.json` **once at run start** with every variant marked `"exit": null`
  (pending), then **rewrite it as each variant finishes.** The gallery therefore fills in
  column by column rather than staying blank for the whole run — which matters most when
  one variant is much slower than its siblings.

Parallelism is capped at 4 concurrent Blender processes. Each is a full Blender instance;
beyond four they contend for cores and the wall-clock win flattens.

**One process per variant is required, not an optimisation.** The asset scripts build into
`bpy.context.scene` at module scope and create named collections (`COL_KNIGHT`, `COL_FX`,
`COL_RIG`). Two builds in one process would collide on both.

`manifest.json` schema:

```json
{
  "asset": "knight000",
  "run": 14,
  "started": "2026-07-31T14:22:03",
  "done": false,
  "audit": null,
  "variants": [
    {
      "n": 1,
      "label": "barbute",
      "diff": {"HELM_STYLE": "barbute", "PLUME_LEN": 0.34},
      "renders": ["v1/hero_34.png", "v1/front.png", "v1/icon_184.png"],
      "exit": 0,
      "seconds": 14.8,
      "stderr_tail": ""
    }
  ]
}
```

This is a contract with `index.html`, which reads exactly these fields and nothing else;
`selftest.py` asserts the key sets on both levels, because a rename here breaks the page
silently rather than loudly.

`exit` is `null` while a variant is still building, the process exit code once it
finishes, or the string `"timeout"` if it was killed. The gallery renders those three
states as a spinner, a result, and a red card respectively.

`diff` holds only the keys that differ between variants — empty for a single-variant
run — and is what the gallery prints under each column — so the visual difference always has its cause next to it. `audit` is
run-level, not per variant (the audit script only ever sees the baseline): `null` until
an audit is run, then the PASS/FAIL summary string. `done` flips true when every variant
has landed.

### 2. `_tools/build_one.py` — the in-Blender bootstrap

Invoked as `blender -b -P _tools/build_one.py -- --script <path> --variant <json> --out <dir>`.
Runs inside Blender. It:

1. Reads the variant JSON.
2. Builds a namespace pre-seeded with `VARIANT`, `RENDER_DIR` (the variant's out dir),
   `DO_RENDER = True`, and `DO_SAVE = DO_EXPORT = False`.
3. `exec`s the target asset script in that namespace.

This is the same mechanism `_knight000/audit_knight000.py` already uses, so it is an
existing repo pattern rather than a new one.

**Variants never write `knight000.blend` or `knight000.fbx`.** Save and export stay off
for every preview build. Promoting a chosen variant to a real save/export is a separate,
explicit run.

### 3. `_tools/gallery/index.html` + a stock file server

Served by `python -m http.server 8777 -d Assets/Blender/_previews~`, started once as a
background task and left running. No server code is written or maintained.

`index.html` is a single static file that polls `manifest.json` every second and
re-renders whenever the fetched body differs from the last one — not merely when `run`
changes, since the manifest is rewritten several times *within* a run as variants land.
Image URLs carry an mtime cache-buster (`?t=<mtime>`);
without it the browser serves a stale image for a filename it has already seen, which is
the standard failure mode of auto-refreshing galleries.

Layout:

- **Latest run at the top.** Variants as columns numbered **1 / 2 / 3**, matching how
  the question is asked in chat. Each column shows its label, its `diff` keys, and its
  renders stacked.
- **Earlier runs below, collapsed, newest first.** This is the "watch it change" half of
  the goal: the model's history across builds, not just its current state.
- Click any image for full size.

A single-variant build is just a run with one column, so the ordinary
build-look-adjust loop uses the same path as a comparison — there is no separate mode.

## The variant hook

The whole per-script cost. Inserted in `blender_knight000.py` immediately before the
existing top-level `build_knight()` call (currently line 2296):

```python
# Variant hook. A runner can pre-seed VARIANT in this namespace before exec'ing
# the file; entries are applied after every default is set but before anything is
# built. Because the builders read module globals at call time, a variant can
# override any tuning constant, any material, or any builder function.
_v = globals().get("VARIANT", {})
globals().update({k: v for k, v in _v.items() if not k.startswith("_")})
if _v.get("_patch"):
    # Structural variants arrive as SOURCE, not as function objects. A function
    # defined in the runner carries the runner's __globals__ and cannot see
    # revolve(), M_GOLD, or anything else here — it fails at call time, deep in
    # the build, for a reason that looks nothing like its cause. exec'ing the
    # source here binds it to this namespace instead.
    exec(_v["_patch"], globals())
build_knight()
```

Two override channels, deliberately distinct:

| Channel | Carries | Use for |
|---------|---------|---------|
| plain `VARIANT` keys | JSON scalars, lists | tuning constants — `Z_CROWN`, `W_CHEST`, plume length, material colours |
| `_patch` | Python source text | replacing a whole builder — `build_helmet`, `build_cape` — or anything needing the script's own helpers |

No upfront parameterisation of the 2,500 lines is required. The script already documents
namespace pre-seeding in its `_flag()` docstring, so the hook extends an existing
convention rather than introducing one.

### Opting in another script

A script qualifies if it (a) has a single top-level build call, (b) reads its tuning
values from module globals, (c) carries the `# --- variant hook ---` block immediately
above that build call, and (d) puts its own save and export behind `DO_SAVE` /
`DO_EXPORT`.

**Only `blender_knight000.py` conforms today.** The other eight write their real output
unconditionally at module scope with no flag to switch off — seven call both
`bpy.ops.wm.save_as_mainfile()` and `bpy.ops.export_scene.fbx()`, and
`blender_walk_anim.py` exports the FBX. `build_one.py` seeding `DO_SAVE = False` is inert
against a script that never reads it, so previewing one of them would rebuild the asset
and overwrite the real `.blend` and `.fbx`, with no warning and no undo — over
uncommitted work, in `blender_boat000.py`'s case.

**Both `preview.py` and `build_one.py` therefore refuse outright to run a script that
does not contain the hook marker** — `preview.py` before any Blender is launched,
`build_one.py` before it exec's anything, since it is directly invocable and cannot
assume the runner's gate ran at all. `--audit` is gated the same way, because it spawns
Blender on the audit script directly and so bypasses `build_one.py` entirely. The marker
is a safety interlock, not a style convention: adopting the hook is also the moment a
script's save/export get put behind flags, so its presence is the cheapest reliable proof
that the script is safe to drive.

Older tack scripts are flat imperative code and would need light restructuring first —
deferred until they are next touched.

## Error handling

- **A failed variant does not block its siblings.** Each Blender process is waited on
  independently; a non-zero exit records `exit` and the last 20 lines of stderr in the
  manifest and leaves `renders` empty.
- **The gallery renders a failed variant as a red card carrying its stderr tail**, in
  place of images — never a broken `<img>`, which reads as a gallery bug rather than a
  build failure.
- **A build that hangs** is killed at a 180 s per-variant timeout and recorded as
  `exit: "timeout"`. The 15 s typical build gives this a wide margin; the timeout exists
  so one wedged process cannot strand a run.
- **A build that renders nothing is a failure**, whatever its exit code says. The
  realistic cause is a view name no `render_view()` call uses — a typo in `--views`, or
  the knight-shaped `DEFAULT_VIEWS` meeting an asset that names its views differently —
  which otherwise yields a green column with a label, a diff, a duration and no pictures.
  That reads as a gallery bug rather than as the caller's typo, so it is routed to the
  red card with the requested view names in the message.
- **A malformed or missing `manifest.json`** leaves the gallery showing the last good
  run with a staleness notice, rather than blanking.

## Cost control

Preview builds render **three views** — `hero_34`, `front`, `icon_184` — at reduced
sample counts. That is what a silhouette comparison needs, and it keeps a three-variant
round at roughly 20 s. The full ten-view set, including the 320-sample `poster` plate,
stays opt-in for a chosen winner.

## `_previews~` and the trailing tilde

The tilde is required, not stylistic. Unity imports everything under `Assets/`, so a
plain `_previews/` would give every preview PNG across every run an importer pass and a
`.meta` file, bloating `Library/` for images that are pure scratch. Unity skips
directories whose name ends in `~`. The path is also added to `.gitignore`.

`_knight000/` has this problem today. It is left alone: `RENDER_DIR` and
`audit_knight000.py` both reference it by name, and renaming is unrelated to this work.

## Verification

No test framework exists in the repo, so verification is a defined smoke run rather than
an assertion suite:

1. **Two-variant run** on `knight000` with a deliberate difference (e.g. `PLUME_LEN`).
   Confirm: `manifest.json` has two entries, both `exit: 0`; all six PNGs exist; the two
   `hero_34.png` files differ by byte size.
2. **Deliberately-broken third variant** (a `_patch` that raises). Confirm the run still
   completes, the other two variants render, and the manifest carries the traceback in
   `stderr_tail`.
3. **Gallery** loads all three, shows two columns of images and one red card, and picks
   up a fresh run without a manual reload.
4. **Non-destructive check:** `knight000.blend` and `knight000.fbx` mtimes are unchanged
   across all of the above.

Step 2 is not optional. The failure path is the one most likely to be quietly broken,
and the one whose breakage is most confusing when it eventually matters.
