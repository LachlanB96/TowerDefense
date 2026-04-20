# Tack — Path 1

*Theme: Fire — trades raw disks for fireballs that set enemies alight. Direct impact stops mattering; the damage is in the burn.*

## Tier 1 — Tack100

- **Cost:** $500
- **Changes:**
    - Projectile swapped: from 8 wooden discs to **4 fireballs** per volley (offset 45°, so they fire into the diagonals rather than the cardinal directions).
    - **Impact damage: 0** — the fireball itself does no damage on contact.
    - On hit, applies **Burn** to the target: 6s duration, 1 damage every 2s → **3 damage per burn cycle**.
    - Range (3), attack rate (2/s), pierce (1), and projectile speed (15) unchanged.
- **Visual:**
    - Tower body recolored: gray metal bands → dark crimson metallic (`RedMetal` mat); silver tack parts → red chrome (`RedTack` mat).
    - Two perpendicular emissive orange **flame symbols** mounted on the tower's top cap — the emblem reads from any camera angle.
    - Counter-rotating rings and squash-stretch fire tell inherited from base.
- **Projectile:** Fireball (runtime-built, not a Blender asset). Bright yellow-orange inner core sphere + transparent orange outer glow; no trail, no impact VFX beyond the enemy's own burn flame kicking in.
- **Description:** The entry fire tier. Damage-per-hit is nothing on its own — the value is in sustained burn pressure on enemies that pass through multiple volleys. Because burns reset their duration when reapplied, the Tack100 is strongest against enemies that linger in range and weakest against fast singletons that leave before the first tick lands.

## Tier 2 — Tack200

- **Cost:** TBD — suggest $900 (roughly 1.8× Tier 1, consistent with typical mid-tier scaling).
- **Changes:**
    - **Attack replaced:** no more projectiles — the tower fires an instantaneous **area attack** each tick, skipping travel time entirely.
    - **Range reduced:** 3 → **2** (shorter reach, but no projectile falloff or miss-past-pierce waste).
    - **Pierce:** 20 (up from 1).
    - **Damage:** 3 per hit (up from 0).
    - On each attack, picks up to **20** enemies inside the 2-unit range and, for each, deals **3 damage + applies Burn** (same 6s / 1-per-2s / 3-total burn as Tier 1).
    - Attack rate unchanged (2/s).
- **Visual:**
    - Tower keeps the crimson / red-chrome palette from Tier 1, with the flame emblems intensified — suggest a second, larger pair of emissive flames or a brightness boost on the existing ones.
    - Firing tell: on each attack, a short-lived expanding orange ring / flame pulse rendered on the ground at the tower's base, capped at the new 2-unit radius. No projectiles to animate.
    - Inherits the counter-rotating rings and squash-stretch body pulse from Base.
- **Projectile:** None — this tier is an AoE pulse. Impact is represented by the existing Burn FX on each hit enemy (orange flame sprite + material tint, per `BurnEffect.CreateFireVisual`).
- **Description:** Shifts the tower from "spray and hope" to "everything inside gets roasted." The short range forces placement on tight corners and choke points, but anything that gets close eats a hard 3-damage hit plus a 3-damage burn — 6 damage per enemy per attack, up to 20 enemies at a time, twice a second. Against a tight pack of 20 that's 240 damage in the first second alone. Strong against crowds; genuinely weak against lone fast movers that can sprint past the 2-unit reach before a second tick lands.
- **Implementation notes:** Not yet coded. Would need:
    - `TowerCosts._upgrades["tack000"][0, 1]` → `(900, "tack200")` (Path 1, level index 1).
    - A `tack200Prefab` reference and `_upgradeSetup["tack200"]` entry in `TowerSelection.cs` that installs a new area-attack component (or reuses `TackAttack` with a `useAreaPulse` flag branch in `Shoot()`).
    - Attack loop: scan `Spawn.UnitsParent`, collect up to 20 units within range, call `Movement.Hit(3)` and add a `BurnEffect` (guarding against duplicates — the current `TackAttack` already checks `GetComponent<BurnEffect>() == null` before adding).
    - New `tack200.blend` / `blender_tack200.py` for the intensified visuals.

## Tier 3 — Tack300

- **Cost:** *Not yet implemented (cost 0 in `TowerCosts`).*
- **Changes:** TBD.
- **Visual:** TBD.
- **Description:** TBD.

---

See [[Base]] · [[Crosspaths]]
