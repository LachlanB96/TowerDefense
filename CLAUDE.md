# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Gloomfell** — a Bloons-style tower defense game built in Unity 6 (Editor version `6000.4.3f1`, URP). Tone is an intentional grim/silly clash: gothic Templar heroes alongside whimsical wooden tack launchers.

## The check

**Check:** `pwsh -File check.ps1` (from the main checkout or a worktree; it checks the folder it's in). Nothing lands on `main` until it passes. Three parts, `-Only ts,harness,unity` for some of them:

- **ts:** TypeScript 7 type-checks the repo's `.ts` and runs its `*.test.ts` (`..\.typescript\check.cts`).
- **harness:** the Blender preview harness's pytest suite, `Assets/Blender/_tools/tests` (moved from `selftest.py` on 2026-10-24; `python Assets/Blender/_tools/selftest.py [name]` is now a shim that runs it).
- **unity:** the EditMode tests in `Assets/Tests/Editor` (the tower tables: everything TowerCosts sells has a prefab and a setup action, and the codes follow the digit convention), in Unity batch mode.

The harness and Unity parts start Blender and Unity, so `check.ps1` queues them with the Process Warden itself (`warden-run`); run `check.ps1` directly, never inside `warden-run`. Two traps:

- Batch mode can't open a project the editor already has open, so with the editor open on this folder the unity part fails and says so. Close the editor, or run the tests from it (Test Runner window, or UnityMCP's `run_tests`). A worktree never has the editor open on it, so a branch's check runs there.
- Batch mode runs on the entitlement license in `%LOCALAPPDATA%\Unity\licenses`, which only Unity Hub renews, signed in, about every 30 days. Once it lapses the unity part fails with "Unity's license has lapsed": open Unity Hub, then run it again.

In a worktree, `Library` becomes a junction to one shared cache, `%LOCALAPPDATA%\GloomFell\check-library` (copied once from the main checkout's), so a branch reimports only what it changed instead of the whole project. Results and logs go to `%LOCALAPPDATA%\GloomFell\check\`.

## The dashboard

**Dashboard:** `gloomfell-dashboard.ts` (styled by `gloomfell-dashboard.css`), on the Dashboards server at http://127.0.0.1:27151/d/gloomfell (`gloomfell` in `Dashboards/dashboards.json`, with a card on the home page). It shows git (branches ahead of and behind main with their worktrees, commits not on GitHub, uncommitted files), the modelling fleet (`Assets/Blender/_previews~/fleet.json` and each `<asset>/pipeline.json`, heartbeat ages, whether serve.py answers on 8777), the Blender scripts (hook marker, FBX in `Assets/Models`), the towers (`TowerCosts.cs`'s `_towerInfo` and `_upgrades`, with the TBDs in `Obsidian/TD/Towers/<Name>/`), Unity (whether the editor holds `Temp/UnityLockfile`) and the last check. Its test is `test/dashboard.test.ts`, against a made-up repo; the check's ts part runs it.

**Actions:** every button is `bun server.ts action gloomfell <action>` from `~\AI\Dashboards`, and `bun server.ts render gloomfell` shows the page. `startSuite` starts `python Assets/Blender/_tools/serve.py` from the repo root with no window, outside any session, through Start-Unfocused (`~\AI\Terminal\code\LBTerm\lbterm\motion\start-unfocused.ps1`, `-NoConsole`), and waits for http://localhost:8777/v4.html to answer; `check` runs `pwsh -NoProfile -NonInteractive -File check.ps1` as a job; `refresh` re-reads git, the fleet and serve.py. Everything else Lachlan does here, Claude does through UnityMCP (the editor), the Blender MCP and headless Blender through `warden-run` (models), and serve.py's endpoints (the suite).

## Working with Unity

All iteration happens inside the Unity Editor via the **UnityMCP** package (`com.coplaydev.unity-mcp`, listed in `Packages/manifest.json`), which is how Claude Code drives the editor. The only command-line runs are the check's.

Use the `mcp__UnityMCP__*` tools for:
- `refresh_unity` / `read_console` — after any `.cs` edit, trigger a recompile and check for errors/warnings before continuing. Pre-existing warnings in `FloatingText.cs`, `TowerSelection.cs`, `Movement.cs`, `GroundGenerator.cs` are noise — filter them out when scanning for new breakage.
- `manage_editor play/stop` — smoke-test in play mode.
- `manage_gameobject` / `find_gameobjects` — edit scenes without opening the YAML.
- `execute_menu_item` — for builds, trigger Unity's own build menu.
- `run_tests` — the EditMode tests, when the editor is open (the check can't run them then).

EditMode tests live in `Assets/Tests/Editor` (assembly `GloomFell.Tests.Editor`). The game scripts compile into Assembly-CSharp, which an assembly definition can't reference, so the tests reach the game code by reflection, by type and member name: renaming a member they name fails them with "not found". There are no PlayMode tests yet.

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
2. **`TowerPlacer.cs`** — for *initial placement*: `BuildTables()` fills `_prefabs` (base codes → prefabs) and `_placementSetup` (base codes → an `Action<GameObject>` that attaches the right attack component(s) with tuned fields).
3. **`TowerSelection.cs`** — for *upgrades*: `BuildUpgradeTables()` gives the upgrade prefabs and setup actions, mirroring the above, keyed by the upgraded code. When an upgrade fires, the old prefab is replaced and the setup action rewires components. An upgrade whose prefab field is empty in `game.unity` shows a button that never enables.

Adding a new tower/upgrade therefore means: add the code to `TowerCosts`, add a prefab field + setup action in whichever of `TowerPlacer` / `TowerSelection` owns that step, assign the prefab in `game.unity`, and (if it's a new behaviour) add a Blender asset + a new attack component. `Assets/Tests/Editor/TowerTablesTests.cs` checks the three agree; an upgrade that's sold before its model exists goes in its `KnownMissingPrefabs` with why (today `tack200`: no model yet).

### Attack components

Implement `ITowerAttack` (`Range` property). Concrete attacks: `TackAttack`, `SniperAttack`, `NatureAttack`. Most variants are **flag-toggled on `TackAttack`** rather than subclassed — see `useFireball`, `useAreaPulse`, `useAirPuff`, `applyBurn`. A fresh path/upgrade usually sets flags + tuning on an existing `TackAttack` via the setup action; reach for a new component only when the targeting or fire loop fundamentally differs (e.g. sniper, nature).

### Projectiles

`Velocity.cs` is the generic projectile driver (direction, speed, pierce, optional burn-on-hit, homing mode). Hit detection is a manual XZ distance loop over `Spawn.UnitsParent` inside `UpdateDirectional()`. Damage is applied via `Movement.Hit(damage)`; status effects via `GetComponent<BurnEffect>() == null` + `AddComponent<BurnEffect>()` to prevent duplicates.

### Visual/game feel conventions

- `SquashStretch` is added to every tower at runtime (`TackAttack.Start()`) and pulsed on fire. Specific child transforms (`TackHead`, `TackShaft`, `TackTip`, `_TackRing*`, `_Range*`, `_outline*`, `_Sniper*`) are excluded by name.
- Character models should read as rounded armour — never visible cubes. Use bevels / subsurf / shade smooth in Blender.

## Asset pipeline

Tower/unit meshes are authored in Blender via scripts in `Assets/Blender/blender_*.py`. Each script opens a base `.blend`, mutates it, and exports an `.fbx` into `Assets/Models/`. Each script works its paths out from its own location (`_REPO` at the top), so they hold wherever the repo lives; a copy run from a worktree under `.claude/worktrees/` still writes into the main checkout's `Assets/`, which the modev4 finish flow relies on. (Until 2026-10-24 they were hardcoded to `~\TD`, the repo's old home.) This is how visual variants of tower upgrades are produced (e.g. `tack100.blend` = red-metal fire variant of `tack000`).

### Preview harness

`Assets/Blender/_tools/` renders variants of an asset in parallel and shows them in
**the Gloomfell suite** — one page for everything: fleet overview → per-asset war room
(tabs Overview · Live · Compare) → design dossier. Start the server once and leave it
running (the dashboard's Start suite does it with no window, outside any session, which
the warden would otherwise clean up when that session ends):

    python Assets/Blender/_tools/serve.py        # suite: http://localhost:8777/v4.html

The suite is `_tools/gallery/v4.html` and its script `_tools/gallery/v4.ts` (TypeScript 7).
`serve.py` copies the page into the previews root and bundles `v4.ts` there as `v4.js`, with
a linked source map `v4.js.map` so devtools show `v4.ts`, using the Bun pinned in
`..\.typescript` (`GLOOMFELL_BUN` overrides it). It does that at startup and again whenever a
request for the page or its script finds `v4.ts`, `v4.html` or Bun changed, so reload after
editing; no restart is needed. `v4.js` and `v4.js.map` are build output: never edit them,
commit them or build them under `_tools/`. A failed build prints `!! PAGE SCRIPT NOT BUILT`
at startup (no bundle is served) or `!! PAGE SCRIPT NOT REBUILT` later (the last good bundle
stays), puts a red banner on the page, and leaves the data files and POST doors working.
`serve.py` redirects the old URLs (`/`, `/index.html`, `/live.html`) into the suite, keeping
their `?asset=` deep links, and deletes the copies of those pages earlier starts left in the
previews root. Page contract: `.claude/skills/blender-model-modev4/references/page.md`.
`GLOOMFELL_PREVIEW_ROOT` points the server at a scratch root for testing (never POST against
the live root). The gallery's tests are `_tools/tests/test_gallery.py` (no Blender; one runs
the page in headless Edge or Chrome, `GLOOMFELL_BROWSER` overrides it, and skips without one),
in the check's harness part.

Then, to compare alternatives (it starts Blender, one per variant, so it's queued with the
Process Warden: `--cpus` one per variant, 2 GB each, never a bare run):

    warden-run --name preview-knight000 --cpus 4 --mem 8 --gpu --max 30m -- python Assets/Blender/_tools/preview.py knight000 --variants helmets.json

`preview.py` starts no more Blenders at once than the CPUs the warden granted (and never more
than 4), and a hook refuses a bare `blender -b`; anything else that runs Blender headless
(`build_one.py`, an asset script with `-- save render export`) goes through `warden-run` the
same way.

In the `preview.py` command above, `helmets.json` is a list of `{"label": ..., "vars": {...}, "patch": "..."}`.
`vars` overrides any module-level global in the asset script; `patch` is Python
source (not a function object — it must bind to the script's own globals) that can
replace a whole builder such as `build_helmet`. Variants are numbered 1..N in the
gallery, which is how they should be referred to when asking the user to choose.

Preview runs are non-destructive: they never write the `.blend` or the FBX. Output
goes to `_previews~/` — the trailing tilde is what stops Unity importing every
scratch render.

A script is "conforming" (drivable by the harness) if its tunables are module-level
globals, it has a single top-level build call with the `# --- variant hook ---`
block immediately above it, its `render_view()` honours `RENDER_ONLY`, and its own
save/export are behind `DO_SAVE` / `DO_EXPORT`. `_tools/_selftest_asset.py` is the
shortest complete example. **Five conform** (knight000, mage000, evilMage000, plague000,
plaguedoc000; the dashboard's Blender scripts tile shows which, live).

The other eight scripts save and/or export unconditionally at module scope, so a
preview would rebuild the asset and overwrite the real `.blend` and `.fbx` with no
undo. Both `preview.py` and `build_one.py` refuse outright to run a script without
the hook marker — this is a safety interlock, not a style check, so do not loosen
it. To opt a script in: copy the hook block from `_tools/_selftest_asset.py` to just
above its top-level build call, and put its `save_as_mainfile` / `export_scene.fbx`
calls behind `DO_SAVE` / `DO_EXPORT` (see `blender_knight000.py`'s `_flag()`).

After changing anything in `_tools/`, run the harness tests: `pwsh -File check.ps1 -Only harness`.

The modelling fleet is `/blender-model-modev4`, typed by Lachlan (never auto-invoked). Since
2026-10-24 it runs **one asset per session**: the session is the shepherd, and its makers,
designer batches and reviewers are its own subagents, at most 8 at once (4 while the warden
halves the cap), each told to start none. A second asset is a second session in its own LBTerm
tab. v1 to v3 of the skill are retired in `docs/shelved/skills/`.

## Design documentation

Design specs live in `Obsidian/TD/`, a folder of Markdown notes that started as an Obsidian vault (its `.obsidian` settings are untracked, the notes are). Obsidian is retired (2026-10-23), so read and edit the files directly. Layout:

- `Towers/<Name>/Base.md`, `Path1.md`, `Path2.md`, `Path3.md`, `Crosspaths.md`
- `Heroes/<Name>.md`

When the user asks about tower behaviour, **read the Obsidian doc before the code** — the doc is the intent; the code may lag behind (entries marked TBD are common).

## Git conventions

- Rule 4 of the global CLAUDE.md, like every project in the megaproject (Lachlan, 2026-10-24): work happens on a branch (`feat/...`, `fix/...`) in a worktree under `.claude/worktrees/`, never in the main checkout, which stays on `main`. Drive a worktree with `git -C` and full paths; never `cd` into it. Commit each working step on the branch, then land it with `land <branch> -m "<what it does>. Check passed"` once `check.ps1` passes there. Never `git merge` into `main` by hand.
- The junctions `.claude/worktrees/.typescript` (to `~\AI\.typescript`) and `.claude/worktrees/Dashboards` (to `~\AI\Dashboards`, for the dashboard's `../Dashboards/contract` import) give worktrees the shared TypeScript; they're gitignored and made once per machine (`~\.claude\reference\typescript.md`). Remove a junction with `rmdir`, never `rm -r`.
- The blender-model-modev4 fleet keeps its own `mage000/dNN` and `model/<asset>` branches and worktrees while a design is in flight; it lands them the same way.
- Commit messages are short and lowercase (e.g. `"added models for 5 heroes. introduced obsidian as LM"`, `"updated graphics"`).
- The repo is public (`LachlanB96/TowerDefense` on GitHub): it's pushed only when Lachlan asks, and nothing private goes in it. `.claude/settings.local.json` is per-machine and git-ignored.

## Outside this repo

What this project needs that git doesn't hold (global CLAUDE.md, rule 7). The encrypted backup covers all of it:

- Claude's memory for this project: `~\.claude\projects\C--Users-LachlanB-AI-GloomFell\memory\`. The repo is public, so its memory never goes in it.
- The UnityMCP server pin, in `~\.claude.json` under this project's path (it has to match the C# package's tag in `Packages/manifest.json`).
- The Blender MCP add-on and its settings: `%APPDATA%\Blender Foundation\Blender\5.1\extensions\lab_blender_org\mcp`, and the client at `~\.local\bin\blender-mcp.exe`.
- The preview suite's runs and fleet state: `Assets/Blender/_previews~/` (git-ignored; renders can be made again, the signals and verdicts in it can't).
- The check's Library cache and logs: `%LOCALAPPDATA%\GloomFell\` (rebuildable).
- Unity's license: `%LOCALAPPDATA%\Unity\licenses` (Unity Hub renews it).
