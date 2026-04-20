# Hero Framework

*Status: design approved 2026-04-20. Not yet implemented. First hero: [[Silent Knight]].*

## Pillars

- **Static, invincible.** Placed like a tower. No HP, no death, no re-placement. Multiplayer sends cannot directly damage the hero.
- **One hero per match.** Enforced at purchase — shop button disables once a hero exists.
- **10 levels per hero.** XP awarded on **round completion only** (flat or light-ramp table, tuned later).
- **Four slots per hero:** auto-attack + passive (unlocked at L1) + active 1 (unlocked at L5) + active 2 (unlocked at L10).
- **Flat cost.** Silent Knight is $1500. Sellable for 50% refund.
- **Two UI surfaces:**
    - Permanent top-of-screen ability bar (always visible once a hero exists).
    - Hero-specific layout in the existing right-side tower selection panel when the hero is clicked.

## Code architecture

Four new scripts, one new data-only class, and tight edits to three existing files.

### New files

- **`Hero.cs`** — `MonoBehaviour` attached to the hero prefab. Implements `ITowerAttack` so existing range indicators and targeting utilities work unchanged. Holds `int level`, `int xp`, three `HeroAbility` slots, and an auto-attack driver. Fires `OnLevelUp` / `OnXpChanged` events.
- **`HeroAbility.cs`** — plain C# data class (not a component). Fields: `unlockLevel`, `cooldown`, `lastCastTime`, and a `System.Action<Hero>` callback that performs the effect. The framework never branches on hero identity — every behaviour lives in the callback assigned by the per-hero setup action.
- **`HeroData.cs`** — static lookup, mirrors `TowerCosts.cs`. Keyed by hero type code (e.g. `knight000`), maps to `HeroInfo { cost, iconPath, range, xpPerLevel[10], sellRatio }`. Single source of truth for hero tuning.
- **`HeroManager.cs`** — single scene component. Owns the permanent top ability bar UI, subscribes to `RoundManager`'s round-complete event, awards XP, enforces the one-hero-per-match rule, and exposes `RegisterHero` / `UnregisterHero` / `CastAbility(int index)`.
- **`JudgedEffect.cs`** — status effect component added to enemies by the Templar's Book ultimate. Mirrors `BurnEffect.cs` in shape. Multiplies incoming damage by 1.25× for its duration.

### Edits to existing files

- **`RoundManager.cs`** — expose `public event System.Action<int> OnRoundComplete;` and fire it at the end of `SpawnWave`. `HeroManager` subscribes in `Start`.
- **`TowerPlacer.cs`** — the shop panel gains a "Heroes" section. Placement flow reuses the existing preview / placement-setup machinery; the only new thing is the placement-setup action that wires a `Hero` component + its three `HeroAbility` instances onto the prefab.
- **`TowerSelection.cs`** — detect whether the selected object is a `Hero` (vs a `TowerData`); when it is, render the hero layout (portrait, XP bar, passive text, two ability buttons, sell button) instead of the tower upgrade buttons. Both the top-bar buttons and the panel buttons route through `HeroManager.CastAbility(index)` — single cooldown / unlock source of truth.
- **`Movement.cs`** — `Hit(int damage)` gains a damage-multiplier pass that checks for `JudgedEffect` on the enemy. Same pattern as adding any multiplicative status effect.

### Data flow

1. Player clicks a hero's icon in the shop → `TowerPlacer` enters placement mode with the hero's prefab.
2. On confirm click → hero instantiated. Placement-setup action calls `HeroManager.RegisterHero(hero)`. Shop button for that hero disables (and all other heroes, once we have more than one) until sold.
3. Every frame, `Hero` runs its auto-attack: scan `Spawn.UnitsParent`, pick target by the hero's configured priority (strongest / closest / first), fire projectile off cooldown. Reuses `Velocity.cs` (homing mode for the Silent Knight's sword).
4. `RoundManager` finishes a wave → `OnRoundComplete(round)` → `HeroManager` adds `HeroData.GetXpForRound(round)` to the live hero → level-up checks run → passive re-applies at new tier, active abilities un-grey at L5 / L10 → both UI surfaces refresh.
5. Player clicks an ability icon (in the top bar or in the selection panel) → `HeroManager.CastAbility(index)` validates unlock + cooldown → invokes `HeroAbility.callback(hero)` → `lastCastTime` updates → both UIs refresh cooldown sweep.

## UI

### Permanent top ability bar

Screen-space overlay, built in code by `HeroManager` (consistent with the `EconomyCanvas` / `SpawnUI` / shop-panel build-in-code pattern described in `CLAUDE.md`). Anchored top of screen, adjacent to the economy bar.

- **Visibility:** hidden entirely before hero purchase; visible after `RegisterHero`; hidden again on sell / `UnregisterHero`.
- **Contents:**
    - Hero portrait 40×40 + current level badge overlay.
    - Three ability icons, 40×40, left-to-right:
        - Passive: always lit. Tooltip on hover shows current scaled value.
        - Active 1: greyscale + "L5" lock overlay when locked. When unlocked: coloured icon with radial cooldown sweep. Clickable when off cooldown.
        - Active 2: same pattern with "L10" lock.

No XP bar on the top bar — keeps it compact. Full progression detail lives in the selection panel.

### Hero layout in the tower selection panel

When `TowerSelection` detects the selected object is a `Hero`, it swaps its panel contents to the hero layout:

- Larger portrait + name.
- Level number + XP bar showing progress to next level (and "MAX" at L10).
- Passive description + current scaled value.
- Active 1 + Active 2 buttons, same behaviour as the top-bar buttons (same `HeroManager.CastAbility` handler, same cooldown source).
- Sell button (50% refund).

Selection interaction is unchanged from current tower behaviour — click the hero to open, click elsewhere to close.

## Balance and tuning

- **XP curve:** placeholder. Target: Active 1 reachable in a ~20-round match, Active 2 reachable in a ~30-round match. Exact numbers decided by playtesting.
- **Cost:** $1500 for Silent Knight. Placeholder; may change once we see how eco pacing lands in practice.
- **Sell ratio:** 50%, matching towers.
- **Ability cooldowns:** Active 1 = 12s, Active 2 = 60s (Silent Knight specifics). Framework supports arbitrary cooldowns per ability.

## Open items deferred

Noted but do not block implementation:

- **Hotkeys.** The panel supports click only for MVP. Hotkey layer added later (plumbing already exists in `TowerSelection.HandleKeyboardShortcuts`).
- **Hero variants.** Framework supports N heroes; we ship only the Silent Knight. Models for mage / archer / ninja / robot / knight2 are imported but not designed yet.
- **Multiplayer pre-match pick.** The multiplayer design specifies heroes are chosen pre-match in the loadout phase. Single-player MVP keeps the "buy from shop during match" flow. Hookup between the two happens with the multiplayer work, not now.
- **Death / revive.** Not a thing. Hero is invincible per this design.
- **Starting level in mid-match placement.** Hero starts at L1 whenever placed, regardless of current round. If that feels punishing at higher rounds, we revisit.

## Dev checklist

When adding a new hero:

1. Add a row to `HeroData._heroInfo`.
2. Create the prefab from the character FBX in `Assets/Models/`.
3. Add a `HeroData._placementSetup` entry: a `System.Action<GameObject>` that attaches `Hero` + three `HeroAbility` instances with their callbacks.
4. Write any new status effect components (e.g. [[Silent Knight]]'s `JudgedEffect`) following the `BurnEffect` pattern.
5. Drop prefab reference into the scene's `HeroManager` (or wherever the prefab dictionary lives).
6. Add the portrait / ability icons to `Resources/UI/`.
7. Add a design doc under `Heroes/<Name>.md` — lore, mechanics table, ability descriptions.
