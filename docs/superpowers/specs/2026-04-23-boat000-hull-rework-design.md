# Boat000 — Hull Silhouette Rework

**Status:** Design  
**Date:** 2026-04-23  
**Scope:** `Assets/Blender/blender_boat000.py` (hull section + dependents)

## Problem

The current `boat000` hull reads as a wooden tub, not a galleon. Two views from the current model in Blender confirm:

- **No tumblehome.** The 5-vert rib table (`keel, chine_p, rail_p, rail_s, chine_s`) flares outward from keel to deck. The widest point is the deck edge. Real galleons are widest at or just above the waterline, then curve *inward* above that so the deck is narrower than max beam.
- **4-sided cross-section.** Only two side panels per flank (keel→chine, chine→rail). No room to express a curved topside.
- **Flat stern wall.** The transom is a vertical pentagon running straight from keel to poop. Galleons have a *counter*: the underside sweeps up from the keel toward a high, overhanging transom. The current stern gallery + quarter galleries sit on a flat wall, so they read as taped-on boxes.
- **Vertical bow stem.** The cutwater collapses to a straight vertical line with no forward rake. No integration with the bowsprit.
- **Gentle sheer.** Deck rises from y=0.50 midship to y=0.68 at the ends — a ~36% rise, visually subtle.

## Goal

Rework the hull mesh so the silhouette reads as a galleon from the TD camera distance: visible tumblehome, sweeping stern counter, raked stem, deepened sheer. Keep the overall footprint (max beam ≈ 0.42 half-width, length-axis z ∈ [−1.10, +1.20]) close enough that the `Turret` pivot, gunport z-positions, and cannon placements still fit.

## Non-goals

- **Beakhead / forward spur** under the bowsprit — deferred to a separate "add a detail" sub-project.
- **Plank-level detail** (splitting the hull into individually-thickened strakes) — heavy geometry, marginal gain at the game camera distance.
- **Animation / `BoatAnimator.cs` / attack behaviour** — this is a mesh-only change. Hull pivot and the `Turret` empty don't move.

## Acceptance criteria

1. From a 3/4 bow view in Blender, the deck edge is visibly narrower than the midship waterline (tumblehome readable).
2. From a pure side view, the stern transom's top edge sits aft of where its bottom edge meets the keel curve (counter overhang readable).
3. The bow stem curves forward, not vertical.
4. Strakes, chain trim, gunport frames, damage holes, bell, lantern, figurehead, railings, gallery, quarter galleries, rudder, bowsprit, masts, sails, wheel — all sit in sensible positions on the reshaped hull. No floaters, no deck intersections.
5. FBX re-imports into Unity; `boat000` still places on water and fires; no behavioural change.

## Design

### 1. Rib topology: 5 → 7 verts

Each rib in `_SECTIONS` becomes 7 verts, arranged as a 4-band vertical profile:

```
              rail_p  ──── rail_s          ← deck edge (narrower: tumblehome)
             /                   \
         beam_p                  beam_s    ← max beam (just above waterline)
            |                     |
         bilge_p                bilge_s    ← lower-hull chine
             \                   /
              keel (x = 0)                  ← keel centerline
```

**Per rib-pair faces** (up from 5 to 7 quads + 1 deck):
- `keel → bilge_p` (bottom port)
- `bilge_p → beam_p` (lower topside port)
- `beam_p → rail_p` (upper topside port — this is where tumblehome lives)
- `rail_p → rail_s` (deck top, unchanged)
- `beam_s → rail_s` (upper topside starboard)
- `bilge_s → beam_s` (lower topside starboard)
- `keel → bilge_s` (bottom starboard)

**Stern transom cap** changes from pentagon to heptagon: `keel, bilge_p, beam_p, rail_p, rail_s, beam_s, bilge_s`. Still coplanar (flat transom).

**Bow cap** stays implicit: the bow rib is degenerate (all widths = 0) and bridging collapses naturally, as in the current code.

### 2. `_SECTIONS` row format

Grows from 5 columns to 8:

```
(z, keel_y, bilge_y, beam_y, deck_y, bilge_w, beam_w, deck_w)
```

- `z` — fore/aft rib position (Unity convention: +Z = bow).
- `keel_y` — bottom-centerline height.
- `bilge_y, bilge_w` — lower chine point (low and out from keel).
- `beam_y, beam_w` — max-beam point (widest, just above waterline).
- `deck_y, deck_w` — deck edge (height gives sheer; half-width gives tumblehome).

**Tumblehome invariant:** `deck_w < beam_w` for all midship ribs. Collapsed ribs (bow point) may set all widths to 0.

### 3. Target `_SECTIONS` values

```
# z,     keel_y, bilge_y, beam_y, deck_y,  bilge_w, beam_w, deck_w
(-1.10,   0.40,   0.55,   0.75,   0.95,    0.08,   0.18,   0.14)   # transom apex (aft + high)
(-0.90,   0.15,   0.30,   0.55,   0.85,    0.22,   0.38,   0.30)   # counter shoulder
(-0.60,  -0.05,   0.08,   0.35,   0.72,    0.30,   0.42,   0.34)   # aft quarter
(-0.20,  -0.12,   0.05,   0.28,   0.66,    0.32,   0.42,   0.34)   # mid-aft
( 0.00,  -0.12,   0.05,   0.26,   0.64,    0.32,   0.42,   0.34)   # midship (widest)
( 0.20,  -0.12,   0.05,   0.28,   0.66,    0.32,   0.42,   0.34)   # mid-fore
( 0.60,  -0.08,   0.10,   0.38,   0.74,    0.28,   0.40,   0.32)   # fore quarter
( 0.95,  -0.02,   0.25,   0.58,   0.86,    0.14,   0.22,   0.18)   # fore shoulder
( 1.20,   0.18,   0.40,   0.72,   0.94,    0.00,   0.00,   0.00)   # stem point (raked forward)
```

Encoding summary:
- **Midship tumblehome:** beam_w 0.42 vs deck_w 0.34 (~19% narrower at deck).
- **Max-beam line:** y ≈ 0.26–0.28 midship — just above waterline (y=0).
- **Sheer:** deck_y sweeps 0.64 (midship) → 0.95 (transom) / 0.94 (stem). Much more exaggerated than the current 0.50 → 0.68.
- **Stern counter:** aft of z=−0.20, keel_y rises (−0.12 → +0.40 at transom) while beam_w shrinks (0.42 → 0.18). The transom ends up narrow, high, and pushed aft — a visible overhang on the underside.
- **Stem rake:** bow point moves z=+1.10 → z=+1.20, and keel_y at the point rises to +0.18; combined with the z=+0.95 shoulder rib, the leading edge reads as a forward-raked curve.

These are starting-point numbers. Expect 2–3 values to get nudged after visual feedback in Blender. Acceptance is visual (see criteria §Acceptance), not numeric.

### 4. `hull_half_width_at(y, z)` rewrite

Still the single API used by all hull-surface-hugging features. New body:

1. Find the z-bracket in `_SECTIONS` and compute `t`.
2. Lerp all four band heights (`keel_y, bilge_y, beam_y, deck_y`) and all three band widths (`bilge_w, beam_w, deck_w`) by `t`.
3. Band-dispatch on `y`:
   - `y < keel_y` → return 0.
   - `keel_y ≤ y < bilge_y` → lerp 0 → `bilge_w`.
   - `bilge_y ≤ y < beam_y` → lerp `bilge_w` → `beam_w`.
   - `beam_y ≤ y ≤ deck_y` → lerp `beam_w` → `deck_w` (this is the tumblehome band).
   - `y > deck_y` → return 0.

### 5. Dependent adjustments

#### Bucket A — follows automatically (sampler-driven)

If the sampler is correct, these refit without explicit constants:
- Waterline strakes (port/stbd).
- MainWale strakes (port/stbd).
- Chain trim.
- Damage-hole backing planes.

#### Bucket B — constants re-tuned

- **Gunport frames + gunport holes.** Raise y center from ~0.30 to ~0.42 so they sit below the new midship deck (0.64) and above the new MainWale (~0.48). Z positions unchanged.
- **MainWale strake y.** 0.45 → 0.48.
- **Waterline strake y.** Stays at ~0.08.
- **Raised decks.**
  - Poop `y_top`: 0.80 → ~1.00 (above new transom apex 0.95).
  - Forecastle `y_top`: 0.80 → ~0.98.
- **Cabin bulkhead walls** (fore side of poop, aft of forecastle): `y_bottom` 0.50 → ~0.66, `y_top` 0.76 → ~0.98.
- **Stern gallery.** Base y raised to ~0.75 (was anchored to old transom). Total gallery height reduced to fit between 0.75 and ~1.00. Projecting bay still aft; overhang now sits *on* the new counter (correct galleon relationship).
- **Quarter galleries.** Base y raised to ~0.70; hang off the new counter shoulder rather than the flat stern.
- **Bowsprit.** Anchor moves from current bow to (0, ~0.88, +1.15) so it launches from the top of the new raked stem. Angle unchanged.
- **Figurehead skull.** Follows bowsprit anchor.
- **Rudder.** Anchor at (0, 0.35, −1.10), was near y=0.10; hangs off the new sternpost line.
- **Stern lantern.** Rides up with the raised poop deck.
- **Bell.** Rides up with the poop deck.
- **Railings.** `y_top` tracks `deck_y(z) + offset` — code currently takes samples, tuning constants just shift.
- **Stairs (main deck → raised decks).** Rise grew from 0.30 (0.50 → 0.80) to 0.36 (0.64 → 1.00). Add 1 step or increase step height.
- **Main deck (implicit at deck_y).** Automatically follows the new sheer curve via the rail verts.

#### Bucket C — unchanged

- Masts (z positions, mast heights). Base y may need a +0.02 nudge to sit flush on the new deck.
- Sails, flag, yardarms (parented to masts).
- Crow's nest, wheel, roundhouse, doors, bulkhead windows, cabin trim (parented to masts / raised decks — ride up automatically, or follow their parent's y delta).
- Cannons (parented to `Turret` empty at midship).
- `Turret` empty itself (hull pivot unchanged).

### 6. Verification workflow

1. Rewrite `_SECTIONS` + `build_hull` + `hull_half_width_at` + stern cap.
2. Run Blender script, check viewport for: tumblehome visible, stern counter visible, stem raked, no geometry blowups.
3. Walk Bucket-B list, fix each dependent one at a time, re-running the script and screenshotting port-side + 3/4-bow after each.
4. Export FBX. Open `game.unity`. Confirm `boat000` places on water, fires, and reads correctly at game-camera distance.
5. Commit when acceptance criteria 1–5 are all met.

## Risks & fallbacks

- **Strake seams visible where hull bends sharply.** The bevel+subsurf pass should smooth them, but if strakes (as thin tapered boxes) poke through the new curvature, increase `offset` in `make_contour_strake` or resample at finer z-steps.
- **Stern gallery won't fit the new transom shape.** The transom is narrower (0.18 half-width vs current wider flat). If the gallery bay outgrows the transom, either narrow the gallery bay to match or widen the transom beam_w/deck_w slightly (back off the counter narrowing). Prefer widening the transom marginally over reshaping the gallery.
- **Tumblehome looks too subtle from in-game camera distance.** If 19% narrowing doesn't read, bump beam_w to 0.46 (wider max beam) keeping deck_w at 0.34 — gets to ~26% without narrowing the deck.
- **Turret yaw arc clips into the new bulkheads.** `Turret` empty yaws the whole hull; the bulkheads yaw with it, so this can't actually happen — but call it out to double-check during Unity verification.
