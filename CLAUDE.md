# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Gloomfell** — a Bloons-style tower defense game built in Unity 6 (Editor version `6000.4.3f1`, URP). Tone is an intentional grim/silly clash: gothic Templar heroes alongside whimsical wooden tack launchers.

## Working with Unity

This repo has **no command-line build/test workflow**. All iteration happens inside the Unity Editor via the **UnityMCP** package (`com.coplaydev.unity-mcp`, listed in `Packages/manifest.json`), which is how Claude Code drives the editor.

Use the `mcp__UnityMCP__*` tools for:
- `refresh_unity` / `read_console` — after any `.cs` edit, trigger a recompile and check for errors/warnings before continuing. Pre-existing warnings in `FloatingText.cs`, `TowerSelection.cs`, `Movement.cs`, `GroundGenerator.cs` are noise — filter them out when scanning for new breakage.
- `manage_editor play/stop` — smoke-test in play mode.
- `manage_gameobject` / `find_gameobjects` — edit scenes without opening the YAML.
- `execute_menu_item` — for builds, trigger Unity's own build menu.

There is **no NUnit or PlayMode test suite** in the project (despite `com.unity.test-framework` being installed).

## Scenes

- `Assets/menu.unity` — main menu.
- `Assets/game.unity` — the actual gameplay scene. All the systems below live here as scene objects.
- `Assets/_Recovery/` — Unity auto-recovery dumps; safe to ignore unless investigating a crash.

## Architecture

The game is built from a small number of MonoBehaviours wired up in `game.unity`. Most runtime state lives on singleton-ish scene objects; prefabs are only used for towers and enemies.

### Bootstrapping pattern: UI is built in code, not in the scene

`Spawn.cs`, `EconomyManager.cs`, `TowerPlacer.cs`, and `TowerSelection.cs` each construct their own `Canvas` + panels + buttons at runtime in `Start()` / `BuildUI()`. **Do not expect to find these UI elements in the scene hierarchy at edit time.** If you need to change a button's position, color, or label, edit the `Build*Panel` method in the relevant script, not the scene.

A legacy stub canvas was removed (2026-04-20); if you see references to `PlacementCanvas`, `PlaceTowerButton`, `SpawnBigUnitButton`, or `SpawnUnitButton`, those are gone.

### Core systems

- **`EconomyManager`** (singleton via `Instance`): money, income tick, lives. Every system that spends/earns goes through `TrySpend` / `AddEconomy`.
- **`RoundManager`**: fixed-interval wave timer (`roundInterval` seconds) → hard-coded wave table for rounds 1–3, formula for round 4+. Calls `Spawn.SpawnBigUnit()` / `SpawnUnit()`.
- **`Spawn`**: exposes `public static Transform UnitsParent` — **the canonical list of live enemies**. Every targeting/hit-detection loop iterates `Spawn.UnitsParent`'s children. Don't search for enemies any other way.
- **`Movement`**: enemy waypoint-follower with HP and health bar. `Hit(damage)` is the only legitimate way to damage an enemy.

### Towers

Tower identity is a **3-digit string code** (e.g. `tack000`, `tack100`, `tack210`) — each digit is the tier in Paths 1/2/3. This convention is mirrored in the Obsidian design docs. See `Towers/<Name>/` for specs.

The upgrade machinery lives in three files that must be edited together:

1. **`TowerCosts.cs`** — declarative source of truth. `_towerInfo` lists placeable base towers (cost/icon/range). `_upgrades` is keyed by current tower code; the value is an `UpgradeInfo[path, level]` table giving `(cost, resultTowerCode)`. A missing/zero-cost entry means "not upgradeable here."
2. **`TowerPlacer.cs`** — for *initial placement*: `_prefabs` maps base codes → prefabs, `_placementSetup` maps base codes → an `Action<GameObject>` that attaches the right attack component(s) with tuned fields.
3. **`TowerSelection.cs`** — for *upgrades*: `_upgradePrefabs` + `_upgradeSetup` mirror the above, keyed by the upgraded code. When an upgrade fires, the old prefab is replaced and the setup action rewires components.

Adding a new tower/upgrade therefore means: add the code to `TowerCosts`, add a prefab field + setup action in whichever of `TowerPlacer` / `TowerSelection` owns that step, and (if it's a new behaviour) add a Blender asset + a new attack component.

### Attack components

Implement `ITowerAttack` (`Range` property). Concrete attacks: `TackAttack`, `SniperAttack`, `NatureAttack`. Most variants are **flag-toggled on `TackAttack`** rather than subclassed — see `useFireball`, `useAreaPulse`, `useAirPuff`, `applyBurn`. A fresh path/upgrade usually sets flags + tuning on an existing `TackAttack` via the setup action; reach for a new component only when the targeting or fire loop fundamentally differs (e.g. sniper, nature).

### Projectiles

`Velocity.cs` is the generic projectile driver (direction, speed, pierce, optional burn-on-hit, homing mode). Hit detection is a manual XZ distance loop over `Spawn.UnitsParent` inside `UpdateDirectional()`. Damage is applied via `Movement.Hit(damage)`; status effects via `GetComponent<BurnEffect>() == null` + `AddComponent<BurnEffect>()` to prevent duplicates.

### Visual/game feel conventions

- `SquashStretch` is added to every tower at runtime (`TackAttack.Start()`) and pulsed on fire. Specific child transforms (`TackHead`, `TackShaft`, `TackTip`, `_TackRing*`, `_Range*`, `_outline*`, `_Sniper*`) are excluded by name.
- Character models should read as rounded armour — never visible cubes. Use bevels / subsurf / shade smooth in Blender.

## Asset pipeline

Tower/unit meshes are authored in Blender via scripts in `Assets/Blender/blender_*.py`. Each script opens a base `.blend`, mutates it, and exports an `.fbx` into `Assets/Models/` (path is hardcoded to `C:\Users\LachlanB\TD\...`, which matters if the repo ever moves). This is how visual variants of tower upgrades are produced (e.g. `tack100.blend` = red-metal fire variant of `tack000`).

## Design documentation

Design specs live in an Obsidian vault at `Obsidian/TD/` (the vault itself is untracked, the content is). Layout:

- `Towers/<Name>/Base.md`, `Path1.md`, `Path2.md`, `Path3.md`, `Crosspaths.md`
- `Heroes/<Name>.md`

When the user asks about tower behaviour, **read the Obsidian doc before the code** — the doc is the intent; the code may lag behind (entries marked TBD are common).

## Interaction conventions

- When presenting multiple options to the user (candidate names, approaches, designs, anything choose-one), **always number them**. The user picks by number, so unnumbered lists force a re-ask.

## Git conventions

- Commit messages are short and lowercase (e.g. `"added models for 5 heroes. introduced obsidian as LM"`, `"updated graphics"`).
- `main` is the trunk; work is committed directly. No PR workflow in use.
