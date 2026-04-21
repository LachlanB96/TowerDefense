# Boat — Base

## Concept
*One-line role:* Water-only all-rounder; a low gothic galleon that broadsides the closest enemy with twin cannons.

The Boat is the entry-level water tower — placeable only on lake/water surfaces, where land towers can't reach. The base hull provides none of artillery / support / income on its own; those roles are unlocked by the three upgrade paths (100 / 010 / 001). On its own it is a steady mid-cost damage dealer that slowly auto-rotates so its port broadside faces the closest enemy, then fires both port and starboard cannons in unison.

## Aesthetics

### Tower Model
- Silhouette: Low pirate galleon, ~2.2 long × 0.9 wide × 1.4 tall above the waterline. Two masts, two cannon ports amidships, small flag on the main mast.
- Form / pose: Carved-wood hull with bevels + subsurf so it reads as rounded wood, never a box. Slight upward sheer at bow and stern.
- Hierarchy (under root `Boat`):
  - `Hull` — clinker-style planked body
  - `DeckRail` — short bevelled railing
  - `MastFore`, `MastMain` — two masts
  - `SailFore`, `SailMain` — billowed quad-mesh sails (subdivided so they can ripple)
  - `Flag` — small subdivided plane on top of `MastMain`
  - `Turret` (empty) → `CannonPort_L`, `CannonPort_R` — barrels at port + starboard amidships, parented under the `Turret` empty so the whole boat can yaw to aim
- Palette (gothic galleon):
  - Hull / rails / masts: near-black stained wood `(0.10, 0.07, 0.06)`
  - Sails / flag: deep crimson `(0.42, 0.06, 0.08)`
  - Cannons + iron fittings: tarnished iron `(0.18, 0.18, 0.20)`, low metallic
  - Subtle baked highlight rim along plank edges (vertex paint) so silhouette reads against the dark blue lake.
- Materials: URP/Lit. Hull and sails near-matte (smoothness ~0.2), iron slightly higher metallic (~0.3).
- Animation feel: Hybrid — sail ripple and flag wave are baked **shape keys** in Blender (Wave modifier → single `Ripple` key); everything else is C# (`BoatAnimator.cs`). Idle is continuous (hull bob + rock, independent mast sway, sails+flag blendshape cycle). Placement is a one-shot drop+splash on Start. Shoot is a one-shot recoil + smoke + `SquashStretch` pulse on every fire.
- Idle / fire tells: Constant gentle hull bob and sail/flag motion = idle; visible recoil + muzzle smoke + hull squash pop + small deck splash ripple = a volley just fired.
- **Cannon mounting:** Both cannons are **rigidly fixed** to the hull at fixed angles (port faces `-Turret.right`, starboard faces `+Turret.right`). They do **not** rotate independently. To aim, the whole `Turret` (containing hull, masts, both cannons) yaws as one piece so port lines up with the target; both cannons then fire simultaneously along their fixed barrel axes. The starboard shot goes the opposite direction regardless of what's there. The "recoil" animation is a small translation along the barrel axis, not a rotation.

### Audio
- Placement cue: `Assets/Resources/SFX/boat_place.mp3` — wooden hull splashing into calm water, single thump, ~0.6s. Generated via ElevenLabs `text_to_sound_effects`. Played by `SfxPlayer` from `BoatAnimator` at the impact frame of the placement drop. Volume 0.7.
- Fire cue: `Assets/Resources/SFX/boat_fire.mp3` — twin cannon broadside in unison, deep boom + short smoke-hiss tail, ~0.5s, no echo. Generated via ElevenLabs `text_to_sound_effects`. Played by `SfxPlayer` from `BoatAttack.Fire()` at the moment of fire. Volume 0.85, with ±5% pitch randomization on each play to avoid monotony.
- Impact cue: None (matches Tack — keeps the mix uncluttered).
- Ambient / idle: None.

## Attacks

### Attack 1 — *Twin Broadside*

#### Stats

| Stat             | Value |
|------------------|-------|
| Damage           | 2     |
| Pierce           | 1     |
| Range            | 5.5   |
| Attack Rate      | ~0.77/s (1.3s cooldown) |
| Projectile Speed | 18    |
| Targeting        | Closest unit in range (auto) |

#### Behavior
Every fixed update the boat picks the closest enemy in `Spawn.UnitsParent` within 5.5 units. The cannons are **fixed to the hull** — they do not aim independently. Instead, the whole `Turret` (containing hull, masts, both cannons) slowly auto-rotates at **90°/s** so the **port broadside** (`-Turret.right`) faces the target. When `Vector3.Angle(-Turret.right, toTarget) < 15°` and the cooldown is ready, both cannons fire **simultaneously**: one ball from `CannonPort_L` along `-Turret.right` (toward the target), one from `CannonPort_R` along `+Turret.right` (away — wherever the opposite side happens to be pointing). The starboard shot is a free side-effect of the broadside, not separately aimed. Cooldown resets to 1.3s; `SquashStretch` pulse fires.

#### Projectile
- Description: Small dark iron cannonball — fast straight shot with a short white tracer so it's legible at high speed.
- Material / shader: URP/Lit, `_BaseColor (0.18, 0.18, 0.20)`, `_Metallic 0.3`, `_Smoothness 0.4`. Tarnished iron.
- Geometry: Unity Sphere primitive, local scale `(0.18, 0.18, 0.18)`.
- Trail / VFX: `TrailRenderer`, `time = 0.08s`, width 0.08 → 0, white → transparent.
- Impact VFX: None (damage applied silently via `Velocity.HitTarget`).
- Projectile driver: `Velocity.cs` directional mode (no new component).
- Sound — fire: *TBD — see Section 4.*
- Sound — impact: *TBD.*

## Base Stats

| Stat       | Value |
|------------|-------|
| Cost       | $450  |
| Footprint  | ~1.4 unit placement radius (`TowerPlacer._overlapRadius`) |
| Placement  | On water surface (lake) only; not overlapping other towers or the enemy path. Surface gating in `TowerPlacer` reads `TowerCosts.GetSurface("boat000") == SurfaceType.Water`. |

## Upgrade Rules
- Paths available: 3
- Max simultaneous upgraded paths: *TBD — not yet enforced in `TowerCosts`.*
- Max tier per path: 3
- Crosspath restrictions: *TBD.*

## Upgrade Paths
- [[Path1]] — *Theme: artillery (heavier cannons, AOE shells; details TBD in future sub-project).*
- [[Path2]] — *Theme: support (details TBD in future sub-project).*
- [[Path3]] — *Theme: income (details TBD in future sub-project).*

## Crosspath Synergies
See [[Crosspaths]].
