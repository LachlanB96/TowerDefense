The Silent Knight is a feared hero among monsters. A knight in shiny medieval armour, trimmed with the finest gold stolen from the monsters he has slain. The knight bears the emblem of the Templar, a shiny T of pure gold. The Silent Knight has bedazzled his own rubies into the T, signifying the Knight's lust for blood. In his right hand he holds his Golden Sword, a gift from the elves for an old quest. The knight's left hand holds The Templar's Book — a magic book written by Old Knights who seemed to never die. Although none of the knight's body is visible, covered in shiny armour, a red glow emits from within the helmet; one can only guess this power emanates from their eyes.


---

## Mechanics

*Status: design approved 2026-04-20. Not yet implemented. See [[Framework]] for the hero system this hero plugs into.*

### Identity

| Field | Value |
|-------|-------|
| Type code | `knight000` |
| Cost | $1500 |
| Sell value | $750 (50%) |
| Range | 3.5 |
| Footprint | 1.4 unit placement radius (same as towers) |
| Target priority | Strongest enemy in range — fits his lore ("lust for blood") |

### Auto-attack — Golden Sword

- **Type:** homing projectile (reuses `Velocity.cs` in homing mode).
- **Damage:** 5 per hit.
- **Cooldown:** 0.8s.
- **Visual:** thrown sword arcs toward target; on hit, projectile destroyed. Knight always holds a sword in hand between throws (cosmetic — the "return" is not simulated).

### Passive (L1) — Templar's Zeal

Attack-rate aura on every tower within 4 units of the knight.

| Level | Attack-rate bonus |
|-------|-------------------|
| 1 | +10% |
| 2 | +12% |
| 3 | +14% |
| 4 | +16% |
| 5 | +18% |
| 6 | +20% |
| 7 | +22% |
| 8 | +24% |
| 9 | +26% |
| 10 | +28% |

Implementation: each affected tower's cooldown is divided by `(1 + bonus)`. Applied per-frame or on range enter/exit. Visual: subtle red ground-glow ring under affected tower bases.

### Active 1 (L5 unlock) — Crimson Arc

Instant 360° sword sweep centred on the knight.

- **Area:** full circle at range 3.5 (same as his auto-attack range).
- **Damage:** 25 to every enemy in range.
- **Cooldown:** 12s.
- **Cast time:** instant, no channel.
- **Visual:** radial red slash VFX on the ground.

*Design note — why 360° and not a frontal cone:* The knight is a static hero with no facing direction controllable by the player. A frontal cone would require inventing a "face" mechanic for a fringe case; 360° solves it with zero UX wrinkle and still reads as "sword sweep."

### Active 2 (L10 ultimate) — The Templar's Book

Knight opens the book and channels for 3 seconds. During the channel:

- All enemies within range 8 of the knight take **5 damage per second**.
- Every enemy hit gains the **Judged** debuff: **+25% damage taken from all sources**, lasts **10 seconds** after application. Judged survives the channel ending.

- **Cooldown:** 60s (measured from channel start).
- **Interaction with auto-attack:** auto-attacks are paused during the 3s channel.
- **Visual:** red beam from the open book to every enemy in range + a floating cross glyph over each Judged enemy.

*Implementation note:* Judged is the first status effect beyond `BurnEffect`. Add a new `JudgedEffect.cs` component following the `BurnEffect` pattern. `Movement.Hit(damage)` gains a small hook that scales incoming damage by the multiplier of any active status effects on the target — tiny refactor.

### Design notes on lore → mechanics mapping

- **Golden Sword** from the lore → auto-attack.
- **Templar's Book** from the lore → Active 2 ultimate. The book is what the *old knights who never died* wrote; having it project the "Judged" debuff (literally marking enemies for judgement and amplifying their death from any source) cashes in that fantasy better than making the book deal its own damage alone.
- **Red glow from helmet** → shared colour motif across VFX (ground-glow under Zeal towers, Crimson Arc slash, beam from the book). Ties him visually to his own abilities without needing a separate "aura" effect on the knight himself.
- **Templar emblem / rubies / lust for blood** → target priority "strongest in range" instead of "closest" (attacks whatever's most worth killing, not whatever's nearest).
- **"Never die"** → the hero is genuinely invincible in game terms. The lore and the mechanics agree.
