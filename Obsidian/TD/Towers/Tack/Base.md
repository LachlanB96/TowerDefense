# Tack — Base

## Concept
*One-line role:* Cheap 360° area denier — shoots a ring of wooden tacks in every direction.

The Tack is the entry-level crowd-control tower. Because it fires a full eight-disk ring on every attack rather than aiming at a single target, it's at its best when enemies pass close to it — hugging corners, choke points, or any spot on the track where it sits near the middle of the path. It's weak against anything that stays at the edge of its range, because the short projectile lifetime (range + 1) means tacks expire before reaching distant targets, and its pierce of 1 per disk means swarms quickly chew through its output.

## Aesthetics

### Tower Model
- Silhouette: Stationary `TackHead` centrepiece flanked by two concentric counter-rotating rings of spikes (`TackShaft` inner ring, `TackTip` outer ring).
- Form / pose: Squat, wheel-like; reads as a mechanical tack launcher rather than a character.
- Palette: Warm wood/tan (`RGB 0.76, 0.60, 0.42`) — same hue as the disks it fires, so the tower and its ammo visually match.
- Materials: URP/Lit, low metallic (`0`), low smoothness (`0.2`) — matte wooden feel.
- Animation feel: Outer ring spins clockwise at 30°/s, middle ring spins counter-clockwise at 30°/s — constant slow churn even while idle. On firing, a `SquashStretch` pulse plays on all parts except the rings and static head.
- Idle / fire tells: Steady counter-rotation = idle; brief squash-stretch pop on the body = a volley just fired.

### Audio
- Placement cue: *TBD — not yet implemented.*
- Fire cue: *TBD — not yet implemented.*
- Ambient / idle: *TBD — not yet implemented.*

## Attacks

### Attack 1 — *Tack Volley*

#### Stats

| Stat             | Value |
|------------------|-------|
| Damage           | 1     |
| Pierce           | 1     |
| Range            | 3     |
| Attack Rate      | 2/s (0.5s cooldown) |
| Projectile Speed | 15    |
| Targeting        | Closest unit in range (auto) |

#### Behavior
Whenever at least one enemy is inside the 3-unit range, fires a full ring of **8 wooden disks** spaced at 45° intervals around the tower. Each disk travels in a straight line outward until it hits its pierce limit (1) or travels past `range + 1` world units, then despawns. The tower fires the full ring as a single volley — the "closest unit" is only used as a trigger condition, not to aim the ring; direction of fire is fixed relative to the tower's forward axis.

#### Projectile
- Description: Thin flat wooden disc — flung like a throwing-star tack. Eight fire at once, one in each compass-and-diagonal direction.
- Material / shader: URP/Lit, `_BaseColor (0.76, 0.60, 0.42)`, `_Metallic 0`, `_Smoothness 0.2`. Blender source is the `WoodDisk` material (roughness 0.8, same base color).
- Geometry: Unity Cylinder primitive, local scale `(0.3, 0.05, 0.3)` — a short flat disc.
- Trail / VFX: None.
- Impact VFX: None (damage is applied silently via `Velocity.HitTarget`).
- Sound — fire: *TBD.*
- Sound — impact: *TBD.*

<!--
### Attack 2 — *Name*
(copy the Attack 1 block above)
-->

## Base Stats

| Stat       | Value |
|------------|-------|
| Cost       | $300  |
| Footprint  | ~1.4 unit placement radius (`TowerPlacer._overlapRadius`) |
| Placement  | On flat ground, not overlapping other towers or the enemy path |

## Upgrade Rules
- Paths available: 3
- Max simultaneous upgraded paths: *TBD — not yet enforced in `TowerCosts`.*
- Max tier per path: 3
- Crosspath restrictions: *TBD.*

## Upgrade Paths
- [[Path1]] — *Theme: TBD* (Tier 1 cost: $500)
- [[Path2]] — *Theme: TBD* (Tier 1 cost: $400)
- [[Path3]] — *Theme: TBD* (Tier 1 cost: $350)

## Crosspath Synergies
See [[Crosspaths]].
