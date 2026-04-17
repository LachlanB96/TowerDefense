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

- **Cost:** *Not yet implemented (cost 0 in `TowerCosts`).*
- **Changes:** TBD.
- **Visual:** TBD.
- **Description:** TBD.

## Tier 3 — Tack300

- **Cost:** *Not yet implemented (cost 0 in `TowerCosts`).*
- **Changes:** TBD.
- **Visual:** TBD.
- **Description:** TBD.

---

See [[Base]] · [[Crosspaths]]
