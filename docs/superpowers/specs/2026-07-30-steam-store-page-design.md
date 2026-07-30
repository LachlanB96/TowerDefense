# Gloomfell — Steam Store Page

**Status:** Design
**Date:** 2026-07-30
**Scope:** `Assets/Blender/blender_keyart.py` (new), `Marketing/` (new tree), Steamworks store page content

## Problem

Gloomfell has ~9 months of committed history, a data-driven tower/upgrade system, a
scripted Blender asset pipeline, and written design specs — and no public presence
whatsoever. Two distinct audiences need to be served:

1. **Players** — a Steam store page with art engaging enough to earn a wishlist.
2. **Recruiters** — evidence of sustained, deliberate engineering work over a year.

These two goals pull in opposite directions. A store page whose "About This Game"
section reads as an engineering writeup will not convert players, and Valve's review
team reads those sections. Conversely a purely promotional page carries no signal
about how the thing was built.

A second problem is honesty. The gap between implemented and designed is large:

| Area | Implemented | Designed only |
|------|-------------|---------------|
| Towers | Tack, Sniper, Nature, Boat | most upgrade path themes (marked TBD) |
| Systems | economy, waves, placement/upgrade, water surfaces | heroes (Silent Knight), competitive multiplayer |

Claiming heroes and multiplayer as features would be an overclaim that a recruiter
is well placed to notice.

## Goal

Ship a complete, upload-ready Steam store page for Gloomfell framed as **Coming Soon,
no date**: all required art at Valve's exact specifications, player-facing copy, and
an honestly-labelled roadmap block. Engineering depth is deliberately *not* on this
page; it lives in a separate devlog site (sub-project B) linked from Steam's website
field.

## Non-goals

- **The devlog site.** Sub-project B. Gets its own spec and reuses this project's
  art library. Deliberately decomposed rather than crammed in here.
- **A trailer.** No `ffmpeg` on this machine and no playable build exists. Steam does
  not require a trailer to publish a Coming Soon page, though its absence is felt.
- **Actually publishing.** Requires a Steamworks partner account, the $100 USD Steam
  Direct fee, and authenticated login — none of which can be done on the user's
  behalf. The upload is a follow-on step once the user is signed in.
- **Illustrated/painted key art.** Not producible here (see Risks).
- **Rebuilding `char_knight`.** Its material work is a real art task, tracked but
  out of scope; this spec routes around it instead of pretending it's fine.

## Acceptance criteria

1. Every required asset in the manifest below exists in `Marketing/steam/` at exactly
   the specified pixel dimensions.
2. `Assets/Blender/blender_keyart.py` reproduces the entire render library headlessly
   from a clean checkout, with no manual steps, on Blender 5.1.
3. The game title is legible at the smallest capsule size (462×174) and inside the
   Library Hero's 860×380 safe area.
4. No asset carries text other than the game title (Valve's guidance).
5. Store copy distinguishes implemented from planned features without a reader having
   to infer it.
6. Screenshots are genuine gameplay captures, not renders — Valve requires this.

## Design

### 1. Asset manifest

Dimensions verified against Steamworks documentation on 2026-07-30, not recalled from
memory. Note that the header capsule is **920×430**; 460×215 is the auto-generated
half-size and is a common stale-spec error.

| Asset | Dimensions | Required | Notes |
|-------|-----------|----------|-------|
| Small capsule | 462×174 | yes | 120×45 and 184×69 auto-generated |
| Header capsule | 920×430 | yes | store page top, Big Picture |
| Main capsule | 1232×706 | yes | store home carousel |
| Vertical capsule | 748×896 | yes | seasonal sales |
| Page background | 1438×810 | optional | auto-derived from last screenshot if omitted |
| Library capsule | 600×900 | yes | PNG; logo must be legible |
| Library header | 920×430 | yes | PNG; falls back to header capsule |
| Library hero | 3840×1240 | yes | **safe area 860×380 centred** |
| Library logo | ≤1280 w and/or ≤720 h | yes | transparent PNG, logotype only |
| Screenshots | ≥1920×1080, 16:9 | yes, ≥5 | must be real gameplay |
| App icon | 184×184 | yes | **JPG**, not PNG — compact layouts, library list view, Deck |
| Shortcut icon | 256×256 or 512×512 | yes | ICO or PNG; alpha is replaced with black when deriving the app icon |

Ten aspect ratios from 462×174 (2.66:1) to 748×896 (0.83:1) cannot be served by one
composition. This is why the pipeline splits into a *render library* and a
*per-slot compositor* rather than producing finished images directly from Blender.

### 2. Art direction

Chosen from three rendered candidates built from the real game assets. The selected
treatment is **cold gothic world, warm key light on the whimsical elements** — the
tonal clash carried by colour temperature rather than by geometry. It was the only
treatment in which both halves of the game's tone survived in one frame:

- Pure gothic dusk flattened the green creeps and wooden towers to muddy olive,
  erasing the comedy.
- Bright storybook high-key washed the near-black galleon to grey and drained the
  crimson sails, erasing the gothic.

Asset roles, based on how legibly each reads at capsule scale:

- **Galleon (`boat000`)** — hero subject. Reads instantly at small size and carries
  the gothic tone unaided. Crimson sails, skull figurehead, warm cabin lanterns.
- **Creeps (`monster`)** — carry the whimsy effortlessly. Big eyes, dumb smile.
- **Tack tower (`tack000`)** — must be shot face-on; the face *is* the joke and is
  invisible from above or behind.
- **`char_knight`** — excluded from hero duty. At capsule scale it reads as a chrome
  blob with a red skirt, not a Templar.

### 3. Pipeline

**Stage 1 — `Assets/Blender/blender_keyart.py`** (follows the existing
`blender_*.py` convention; committed; headless via `blender -b -P`):

- Appends objects from the real source `.blend` files rather than importing FBX, so
  authored materials survive.
- Per-asset uniform scale normalisation against a nominated axis, because the source
  files were authored at inconsistent scales.
- **Applies a +90° X correction to `boat000`**, which is authored **Y-up** (mast along
  +Y, hull fore-aft along Z) in Unity's coordinate frame, unlike every other asset in
  the project, which is standard Blender Z-up. Without this the ship renders capsized.
- Uses the real `lake.blend` mesh for water. A primitive plane reads as an obviously
  floating square and is a giveaway.
- Builds the chosen lighting rig, and resets the AgX `look` to a known baseline before
  each variant. The look/view-transform enums are populated dynamically from OCIO and
  are **not introspectable via `bl_rna` in background mode** (they report a single
  `NONE` item), so membership testing gives false negatives and a failed assignment
  silently inherits the previous variant's grade.
- Renders **tight crops, not wide dioramas**, into `Marketing/renders/`.

**Stage 2 — `Marketing/compose_capsules.py`** (Pillow 12.2.0):

- Composites the title lockup over renders, per-slot crop and safe-area handling,
  writing to `Marketing/steam/`.
- Title face: **CharlemagneStd-Bold** — Romanesque inscriptional capitals, medieval
  and ecclesiastical without tipping into cheesy blackletter. Warm gold against the
  cold environment, reinforcing the temperature clash.
- Emits the transparent-background Library Logo as its own output.

Interactive iteration happens in a live Blender session over MCP for fast visual
feedback; the result is then codified back into the headless script so the pipeline
stays reproducible. The committed script, not the live session, is the deliverable.

### 4. Store copy

- **Short description** (≤300 chars): player-facing hook, leads with the tonal clash.
- **About This Game**: what you do, the towers, the 3-path upgrade system, the water
  layer. Player-facing throughout.
- **In Development block**: explicitly separates working systems from planned ones
  (heroes, competitive 1v1 sends). Honest, and defuses the overclaim risk.
- **Tags/genres**: Tower Defense, Strategy, Indie, Singleplayer.
- Developer/website field links to the sub-project B devlog.

## Risks

- **Diorama renders are not painted key art.** Wide 3D shots of this asset set read
  as competent programmer art on a Steam capsule. Mitigation is tight crops, aggressive
  lighting and heavy typographic treatment — not wider scenes. Genuinely illustrated
  key art would need to be generated or commissioned externally and composited in;
  the Stage 2 compositor is structured so that swapping the background plate for an
  illustration requires no pipeline change.
- **Screenshots are a hard external dependency.** Valve requires real gameplay, so
  they need the Unity Editor open with the MCP bridge running, or PNGs supplied
  directly. Nothing in this spec can route around it.
- **`char_knight` legibility** will resurface the moment heroes are marketed. Tracked,
  not solved here.
