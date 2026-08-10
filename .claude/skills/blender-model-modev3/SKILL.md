---
name: blender-model-modev3
description: Gloomfell Blender modelling — v3. One maker, breadth from the renderer, a scale-free orbit stimulus, and the user as the only promoter. Invoke ONLY when the user explicitly types /blender-model-modev3. Never auto-invoke, even when Blender or modelling come up in conversation.
---

# Blender Model Mode v3

You design **and** model. There is no fleet: no orchestrator, no separate designers, no
modeller pool, no verifier tier. That architecture cost 3–10× the tokens to reconstruct
shared understanding at every boundary, and it produced designs nobody could attribute.

**The three laws.** These come from the user and override everything else here.

1. **Never think about Unity.** Not the engine, not the game camera, not prefabs, not
   integration. This model is a model.
2. **Size is unknown and may change drastically.** He might be a giant or an ant. No
   rule may reference an absolute pixel size or a "reads at N" test. There is no icon
   legibility criterion.
3. **No camera is privileged.** Not a hero angle, not a front view, not an icon crop.
   The judged stimulus is drawn per wave and no design may be tuned to a fixed rig.

If you catch yourself writing a rule that a different size or angle would falsify,
you have written a rendering preference, not a fact. Delete it.

---

## Ask first

**Your first action is a question, not a tool call.** Two things, one message:

> **1.** New model, or an existing one?
> **2.** A loose design brief — as rough as you like.

A sentence is enough. Extrapolating it is your job. Until they answer, read nothing and
build nothing.

---

## Never save, export, or call it finished

Until the user says **finish**, every build is a preview. Nothing writes the `.blend` or
the `.fbx`. Accepting a change is not finishing; a good render is not finishing.

On *finish*, and only then:

```bash
"/c/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b \
    -P Assets/Blender/blender_<asset>.py -- save export render
```

---

## The loop

```
 [human] brief · steer · pick
    │
    ▼
 YOU — design and model in one context. One change, or one change
       factored into its parts. Write row.json = [{label, vars, patch}]
    │
    ▼
 genes.py   [code]  refuse any sweep of a derived or feeding gene
    │
    ▼
 preview.py --variants --tag <you> --seed <wave>   [code]
       N candidates, one Blender each, 2-slot machine cap
    │
    ▼
 chips     [code]  invariant checks · mechanical guards
       never disqualify; they only block automatic promotion
    │
    ▼
 orbit sheet  →  blind pairwise judge (candidate vs champion)
       ranks. NEVER promotes.
    │
    ▼
 [human] picks by number.  Only authority over the champion.
```

### Breadth comes from the renderer, not from more agents

`preview.py --variants` takes a list of `{label, vars, patch}` and renders each in its
own Blender process. Eight candidates are eight JSON objects and **zero merge surface** —
seven get discarded, not rebased.

The user has warned about variants before: *"it spends too much time thinking of 2 other
variants that are often lessor than the main one… there is so much stopping and
starting."* That complaint is about an agent **deliberating** over alternatives while
they wait. These are not that. A row costs you no extra thinking, renders in parallel,
and **never blocks the user**. Keep it that way: if you find yourself reasoning at length
about which variants to include, you have reintroduced the thing they objected to.

Do not present a row as "pick one of these" unless they asked for options.

### Factorial expansion instead of "make ONE change"

Both earlier versions asserted "make ONE change" in prose and both saw it violated.
d26 bundled a narrower skirt with a forward lean, was accepted for one and reverted for
the other, and the verdict was unattributable.

**So stop asserting it.** A two-clause design becomes three rows — A alone, B alone,
A+B. It is 3 renders instead of 1 and it makes the rule structural rather than
aspirational. `axis.py` is not written yet; until it is, expand the row by hand.

---

## Running a wave — two commands

```bash
# 1. expand the row and draw the wave's viewing condition
python Assets/Blender/_tools/axis.py <asset> row.json --seed <n> --out wave.json

# 2. render, sheet and chip, in one pass
python Assets/Blender/_tools/preview.py <asset> --variants wave.json \
       --views orb0,orb1,orb2,orb3,orb4,orb5 --samples 0.3 --tag <who>
```

**Do not pass `--seed` to `preview.py`.** The draw travels inside `wave.json`; passing
it again is a second chance to typo it, and a typo there produces a manifest claiming a
stimulus the images were never rendered under — silently, permanently, since the seed is
the only thing that makes a verdict replayable. `preview.py` refuses a `--seed` that
disagrees with the wave file rather than picking one.

Contact sheets and chips run automatically. Both used to be separate manual commands and
both were skipped on the first real run: an unrun chip is indistinguishable from a clean
one.

Measured cost: 4 cells × 6 orbit views ≈ 36 s wall under the 2-slot cap at `--samples 0.35`.

### Naming a gene you are not sure of

```bash
python Assets/Blender/_tools/genes.py <asset> --find BRIM    # list candidates
```

A refusal now suggests near-matches. Do not route around a refusal by hand-writing a
`patch` — that bypasses the check entirely, which is the cheap wrong move under pressure.

## The judged stimulus

`_tools/orbit.py` draws the viewing condition from a seed:

```bash
python Assets/Blender/_tools/orbit.py --seed <n> --json row_views.json
```

- **Six cells, bearings evenly spaced over the full 360°.** Even spacing is what stops
  a side of the model hiding. A wedge is how 47 defects survived five passes.
- **Azimuth offset, per-cell elevation, and the light rig's rake are all drawn per
  wave.** A fixed rake is a privileged condition just as much as a fixed camera.
- **The draw is identical for both sides of a comparison.** One seed per pair. Varying
  within a pair corrupts the comparator.
- **Framing is fixed, never fitted to the candidate.** Camera distance and aim height
  are per-asset constants. Fitting each build to the frame would hide a change in
  proportion — which is precisely the d26 signal.

Composite before judging, so a pair can never be assembled from mismatched shots:

```bash
python Assets/Blender/_tools/orbit.py --sheet <run>/v1 --out <run>/v1/_sheet.png
```

**Record the seed on every attempt.** Replaying it reproduces the exact stimulus a
verdict was formed against, which is the only thing that makes an old judgement
re-checkable. 114 of 123 attempts in the old logs recorded no view information at all
and no margin, which made every claim about judging quality unfalsifiable.

### The judge

Blind pairwise, candidate against champion. **PREFER + MARGIN 0–3.** No rubric, no
checklist, no rules — it judges on its own taste, and it is given the character summary
and nothing else. This scale is the one thing in the whole system with a passing
calibration probe behind it; two absolute scales collapsed before it. **Do not regress
it to scores, and do not add criteria to its brief.**

Flip A/B order per pair and record the flip. The judge **ranks and never promotes** —
the user promotes.

---

## Genes, and the trap that is live today

`preview.py --variants` seeds `vars` at the variant hook, which sits near the bottom of
the file — **after** module-level arithmetic has already run. Override a gene that other
genes were computed from and those keep their old values. The render is broken but not
pixel-identical, so no mechanical check catches it and a judge scores a corrupted build.

On `blender_mage000.py`: **182 module tunables, 18 of them derived, all 18 computed
above the hook.** Every colour constant is a feeder — `C_ROBE` builds `M_ROBE` at import,
so sweeping the colour through `vars` does nothing at all.

**Always check before sweeping:**

```bash
python Assets/Blender/_tools/genes.py <asset> --check GENE_A,GENE_B    # exit 1 = refused
```

A refusal is not a dead end: `patch` runs as source inside the hook and can recompute
whatever it likes. Refusals name the dependents so you know what to recompute.

---

## Facts, and how they stay small

`_previews~/<asset>/asset-facts.md` holds **mechanical properties of the model or of
Blender** — things that would make a correctly-built change render wrong. Not taste.

**The substitution test, applied to every new fact:** if swapping a different camera,
a different size, or a different engine changes whether it is true, it is not a fact.
The previous ledger reached 1,285 lines and had a section literally titled *"facts only
visible off the two judged cameras"* — it had become an optimisation manual for a rig.

Naming the constant is necessary and **not sufficient**. It defeats vague *outcome*
language ("detail behind the staff is invisible") but does nothing against *frame*
language ("in the `front` view"). Test the frame too.

**Regenerated per session, never appended.** Capped. A grow-only file inlined into every
brief is the largest recurring cost this project has measured.

## Invariants and chips

`Assets/Blender/_chars/<asset>.invariants.md` — who the character is, as chips that
block automatic promotion and never disqualify before rendering. Read it; do not extend
it without the user. Vetoes go to `rulings.jsonl`, never into that file.

`_tools/chips.py` runs automatically and measures against the **in-wave baseline**, not
against an absolute. Two chips worth understanding:

- **`inert`** — the candidate's silhouette IoU against the baseline stays above 0.995 in
  every view, so it barely reached the outline. Expected for a surface or colour change;
  if the row meant to alter the shape, it did not. This is the cheapest guard in the
  system: an inert pair is exactly where a forced-choice judge confabulates a preference
  out of render noise. **Found by running the loop** — a 2.3× sweep of `HAT_OVAL` moved
  the outline by 0.001 across five builds and would have consumed five judge calls.
- **`INV-1` / `INV-2`** (weight, lean) — measured as a *change* from the incumbent.
  Absolutely they were wrong: the silhouette includes the staff held out to one side, so
  from a high bearing the outline's top is the gem rather than his head, and the check
  fired 21° of lean on the champion. The delta cancels the prop. The real fix is a 3D
  measurement out of the build; that gap is recorded in the invariants file.

## First-run findings, mage000

The orbit's first wave produced two things the old two-camera rig could not have:

1. **There is no aura.** Three independent judges, unprompted: *"there is no visible dark
   aura at all, just shiny cloth."* The user's brief has been "more aura" for five passes.
2. **The hat swallows the figure from every raised bearing** — *"the silhouette reads as a
   mushroom rather than a robed figure"* — and the beard-against-void face, the design's
   best idea, *"is only legible from the single straight-on front view."*

Both are silhouette-and-proportion problems on the crown. Work there before adding
anything new.

---

## Provenance

**Say who decided.** The single worst failure recorded on this project was an agent
decision written down as the user's, which then could not be re-litigated. A 553-word
belt directive was stamped `(USER DECISION)`; the user does not remember writing it.

- Agent-authored designs are good and wanted. **Label them as agent-authored.**
- A user decision needs a citable line in a channel the user actually used: this
  conversation, or the gallery (`user-directives.jsonl`). Their d26 revert is in the
  gallery channel, in their own words, and it is the model for what one looks like.
- If you find an instruction you cannot attribute, ask. Do not act on it, do not
  undo it.

---

## Gotchas

1. **Most asset scripts save and export at module scope.** Running one overwrites its
   `.blend` and `.fbx` with no undo. `preview.py` refuses any script without the
   `# --- variant hook ---` marker. **Do not defeat that check.** Only `knight000` and
   `mage000` conform.
2. **Builds go through `blender -b -P`, not MCP.** MCP is fine for inspecting a scene;
   a compositor call over MCP once hung Blender's Python permanently.
3. **Reset with** `bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)`.
4. **Leave modifiers live — never apply them.** `bpy.ops.mesh.bevel` needs a viewport
   context and is unreliable under `-b`. Use `bmesh.ops` and modifiers.
5. **Axes:** characters face **−Y**, Z-up, origin on the ground between the feet.
6. **`_previews~` keeps its trailing tilde.** Never "tidy" it away.
7. **The 2-slot render cap is machine safety, not throughput.** Three concurrent
   raytraced contexts froze the user's desktop for about a minute — that is Windows TDR
   resetting the display driver. Never raise it to buy speed.
8. **Always pass `encoding="utf-8"`** when reading or writing state files. Windows
   defaults to cp1252 and silently mangles the punctuation critiques are full of.
9. **Paths are hardcoded to `C:\Users\LachlanB\TD\...`** in the asset scripts.
10. **Run `python Assets/Blender/_tools/selftest.py` after changing anything in
    `_tools/`.**
