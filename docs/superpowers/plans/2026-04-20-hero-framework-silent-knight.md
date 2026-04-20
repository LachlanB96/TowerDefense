# Hero Framework + Silent Knight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the hero framework and ship the Silent Knight as the first hero, matching `Obsidian/TD/Heroes/Framework.md` and `Obsidian/TD/Heroes/Silent Knight.md`.

**Architecture:** Six new scripts (`Hero`, `HeroAbility`, `HeroData`, `HeroManager`, `JudgedEffect`, `SilentKnightSetup`) plus targeted edits to `RoundManager` (round-complete event), the three tower attack scripts (attack-speed aura hook), `Movement` (damage-multiplier hook), `TowerPlacer` (shop hero entry + dev-place), and `TowerSelection` (hero selection layout). `Hero` implements `ITowerAttack` to reuse the existing range indicator. A knight placeholder prefab is built from primitives; the FBX swap is a follow-up.

**Tech Stack:** Unity 6 (6000.4.3f1), URP, C#, UnityMCP for editor control. No test framework — validation is compile-error-free console + play-mode smoke tests.

---

## File structure

**New files:**
- `Assets/Scripts/Hero.cs` — MonoBehaviour. Auto-attack driver. Owns level/xp, passive slot, two active ability slots. Implements `ITowerAttack`.
- `Assets/Scripts/HeroAbility.cs` — Plain C# data class. Fields: `name`, `iconPath`, `description`, `unlockLevel`, `cooldown`, `lastCastTime`, `isPassive`, `callback`.
- `Assets/Scripts/HeroData.cs` — Static lookup, mirrors `TowerCosts.cs`. Maps hero type code → `HeroInfo { cost, iconPath, range, xpToReachLevel[10], sellValue }`.
- `Assets/Scripts/HeroManager.cs` — Scene singleton. Owns permanent top ability bar UI, subscribes to `RoundManager.OnRoundComplete`, enforces one-hero-per-match, routes ability casts.
- `Assets/Scripts/JudgedEffect.cs` — Status-effect component on enemies. Multiplies incoming damage by 1.25× for 10 seconds. Refreshes on reapplication.
- `Assets/Scripts/SilentKnightSetup.cs` — Static class. Wires a freshly instantiated knight GameObject: adds `Hero`, configures its three `HeroAbility` instances with Silent Knight callbacks.

**Edits:**
- `Assets/Scripts/RoundManager.cs` — Add `public event Action<int> OnRoundComplete` and fire at end of `SpawnWave`.
- `Assets/Scripts/Movement.cs` — `Hit(int)` scales incoming damage by `JudgedEffect.damageMultiplier` when present.
- `Assets/Scripts/TackAttack.cs`, `Assets/Scripts/SniperAttack.cs`, `Assets/Scripts/NatureAttack.cs` — Add `public float attackSpeedMultiplier = 1f` and divide `cooldown` by it in the `Update` gate.
- `Assets/Scripts/TowerPlacer.cs` — `_prefabs` and `_placementSetup` gain a `knight000` entry; shop panel gains a "Heroes" section; dev auto-place gains a knight.
- `Assets/Scripts/TowerSelection.cs` — When the selected object has a `Hero` component, render the hero layout instead of the tower upgrade buttons.

---

## Task 1: RoundManager — OnRoundComplete event

**Files:**
- Modify: `Assets/Scripts/RoundManager.cs`

- [ ] **Step 1: Add the event field**

Open `Assets/Scripts/RoundManager.cs`. Directly below the class declaration (line 5) add:

```csharp
    public event System.Action<int> OnRoundComplete;
```

- [ ] **Step 2: Fire the event at the end of SpawnWave**

At the end of the `SpawnWave` coroutine (after the small-unit spawn loop finishes, around line 63), add:

```csharp
        OnRoundComplete?.Invoke(round);
```

- [ ] **Step 3: Compile check**

Call `mcp__UnityMCP__refresh_unity`, then `mcp__UnityMCP__read_console` with `{ "action": "get", "types": ["error"], "count": 20, "format": "detailed" }`.

Expected: no new compile errors referencing `RoundManager.cs`.

- [ ] **Step 4: Commit**

```bash
git add Assets/Scripts/RoundManager.cs
git commit -m "feat(rounds): add OnRoundComplete event fired after wave spawn"
```

---

## Task 2: Tower attack-speed multiplier foundation

**Files:**
- Modify: `Assets/Scripts/TackAttack.cs`
- Modify: `Assets/Scripts/SniperAttack.cs`
- Modify: `Assets/Scripts/NatureAttack.cs`

Adds a per-tower `attackSpeedMultiplier` field that external systems (the Silent Knight's Templar's Zeal passive) can raise to speed up nearby towers. Default 1f is a no-op — existing behaviour unchanged.

- [ ] **Step 1: TackAttack — add field**

In `Assets/Scripts/TackAttack.cs`, add alongside the other public fields (after the `public int pierce = 1;` line, before `public float Range => range;`):

```csharp
    public float attackSpeedMultiplier = 1f;
```

- [ ] **Step 2: TackAttack — use it in the cooldown gate**

Change the first line of `Update` from:

```csharp
        if (Time.time - lastAttackTime < cooldown) return;
```

to:

```csharp
        if (Time.time - lastAttackTime < cooldown / Mathf.Max(0.01f, attackSpeedMultiplier)) return;
```

- [ ] **Step 3: SniperAttack — add field and use it**

In `Assets/Scripts/SniperAttack.cs`, add after `public Color bulletColor = ...;`:

```csharp
    public float attackSpeedMultiplier = 1f;
```

Change the first line of `Update` from:

```csharp
        if (Time.time - lastAttackTime < cooldown) return;
```

to:

```csharp
        if (Time.time - lastAttackTime < cooldown / Mathf.Max(0.01f, attackSpeedMultiplier)) return;
```

- [ ] **Step 4: NatureAttack — add field and use it**

In `Assets/Scripts/NatureAttack.cs`, add after `public float launchSpeed = 8f;`:

```csharp
    public float attackSpeedMultiplier = 1f;
```

Change the cooldown gate line in `Update` from:

```csharp
        if (Time.time - _lastAttackTime < cooldown) return;
```

to:

```csharp
        if (Time.time - _lastAttackTime < cooldown / Mathf.Max(0.01f, attackSpeedMultiplier)) return;
```

- [ ] **Step 5: Compile check + play-mode smoke test**

Call `mcp__UnityMCP__refresh_unity`, then `mcp__UnityMCP__read_console` filtered to errors. Expected: no new compile errors.

Enter play mode (`mcp__UnityMCP__manage_editor` with `action="play"`). Verify that towers still fire at the same rate as before the change (multiplier stays at 1f when nothing touches it). Exit play mode.

- [ ] **Step 6: Commit**

```bash
git add Assets/Scripts/TackAttack.cs Assets/Scripts/SniperAttack.cs Assets/Scripts/NatureAttack.cs
git commit -m "feat(towers): add attackSpeedMultiplier hook for hero auras"
```

---

## Task 3: JudgedEffect + Movement damage-multiplier hook

**Files:**
- Create: `Assets/Scripts/JudgedEffect.cs`
- Modify: `Assets/Scripts/Movement.cs`

- [ ] **Step 1: Create JudgedEffect.cs**

Write `Assets/Scripts/JudgedEffect.cs`:

```csharp
using UnityEngine;

public class JudgedEffect : MonoBehaviour
{
    public float duration = 10f;
    public float damageMultiplier = 1.25f;

    private float _endTime;
    private GameObject _visual;

    void Start()
    {
        _endTime = Time.time + duration;
        CreateVisual();
    }

    public void Refresh()
    {
        _endTime = Time.time + duration;
    }

    void Update()
    {
        if (Time.time >= _endTime)
        {
            if (_visual != null) Destroy(_visual);
            Destroy(this);
        }
    }

    void CreateVisual()
    {
        _visual = new GameObject("_JudgedFX");
        _visual.transform.SetParent(transform, false);
        _visual.transform.localPosition = Vector3.up * 2.2f;

        // Floating red cross glyph: two thin cylinders
        var mat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        mat.SetColor("_BaseColor", new Color(0.9f, 0.05f, 0.15f));

        var vert = GameObject.CreatePrimitive(PrimitiveType.Cube);
        vert.name = "_cross_v";
        Destroy(vert.GetComponent<Collider>());
        vert.transform.SetParent(_visual.transform, false);
        vert.transform.localScale = new Vector3(0.12f, 0.55f, 0.12f);
        vert.GetComponent<Renderer>().sharedMaterial = mat;

        var horiz = GameObject.CreatePrimitive(PrimitiveType.Cube);
        horiz.name = "_cross_h";
        Destroy(horiz.GetComponent<Collider>());
        horiz.transform.SetParent(_visual.transform, false);
        horiz.transform.localPosition = Vector3.up * 0.08f;
        horiz.transform.localScale = new Vector3(0.36f, 0.12f, 0.12f);
        horiz.GetComponent<Renderer>().sharedMaterial = mat;
    }

    void LateUpdate()
    {
        if (_visual == null || Camera.main == null) return;
        // Face camera (billboard)
        _visual.transform.rotation = Quaternion.LookRotation(
            _visual.transform.position - Camera.main.transform.position);
    }
}
```

- [ ] **Step 2: Movement — scale damage by JudgedEffect**

In `Assets/Scripts/Movement.cs`, replace the `Hit` method (currently lines 209-218) with:

```csharp
    internal void Hit(int v)
    {
        var judged = GetComponent<JudgedEffect>();
        if (judged != null)
            v = Mathf.Max(1, Mathf.RoundToInt(v * judged.damageMultiplier));

        FloatingText.Spawn(transform.position + _healthBarWorldOffset, v.ToString(), Color.red, 0.9f, 24, true, 60f);
        health -= v;
        UpdateHealthBar();
        if (health <= 0)
        {
            Death();
        }
    }
```

- [ ] **Step 3: Compile check**

`mcp__UnityMCP__refresh_unity` then `mcp__UnityMCP__read_console` filtered to errors. Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add Assets/Scripts/JudgedEffect.cs Assets/Scripts/Movement.cs
git commit -m "feat(enemies): add JudgedEffect status + Movement damage-multiplier hook"
```

---

## Task 4: HeroAbility data class

**Files:**
- Create: `Assets/Scripts/HeroAbility.cs`

- [ ] **Step 1: Create HeroAbility.cs**

Write `Assets/Scripts/HeroAbility.cs`:

```csharp
using System;

// Plain C# data class (no MonoBehaviour). One instance per ability slot on a Hero.
// Passives: isPassive=true, callback runs every frame in Hero.Update when unlocked.
// Actives:  isPassive=false, callback runs on HeroManager.CastAbility() off cooldown when unlocked.
public class HeroAbility
{
    public string name;
    public string iconPath;
    public string description;
    public int unlockLevel;
    public float cooldown;
    public float lastCastTime = -999f;
    public bool isPassive;
    public Action<Hero> callback;

    public bool IsUnlocked(int heroLevel) => heroLevel >= unlockLevel;

    public bool IsReady(int heroLevel)
    {
        if (!IsUnlocked(heroLevel)) return false;
        if (isPassive) return true;
        return UnityEngine.Time.time - lastCastTime >= cooldown;
    }

    public float CooldownRemaining()
    {
        if (isPassive) return 0f;
        return UnityEngine.Mathf.Max(0f, cooldown - (UnityEngine.Time.time - lastCastTime));
    }
}
```

- [ ] **Step 2: Compile check**

`mcp__UnityMCP__refresh_unity` then `read_console` filtered to errors. Note: a reference to `Hero` (the MonoBehaviour defined in Task 6) will not resolve yet. This is expected and will clear once Task 6 lands. If that is the only error, proceed. Otherwise, fix and re-check.

Workaround if the console blocks subsequent work: create an empty `Assets/Scripts/Hero.cs` stub containing only `public class Hero : UnityEngine.MonoBehaviour { }` and delete it once Task 6 begins. Prefer to push through since Task 6 is the next one.

- [ ] **Step 3: Commit**

```bash
git add Assets/Scripts/HeroAbility.cs
git commit -m "feat(heroes): add HeroAbility data class (passive/active slots)"
```

---

## Task 5: HeroData static lookup

**Files:**
- Create: `Assets/Scripts/HeroData.cs`

- [ ] **Step 1: Create HeroData.cs**

Write `Assets/Scripts/HeroData.cs`:

```csharp
using System.Collections.Generic;

// Static tuning data for every hero. Mirrors TowerCosts.cs.
// Keyed by hero type code (e.g. "knight000" = knight, path0, tier0 — tier-per-path convention).
public static class HeroData
{
    public struct HeroInfo
    {
        public int cost;
        public string iconPath;
        public float range;
        public int[] xpToReachLevel; // length 10, index 0..9 -> XP needed to be at level 1..10
        public int sellValue;

        public HeroInfo(int cost, string iconPath, float range, int[] xpToReachLevel, int sellValue)
        {
            this.cost = cost;
            this.iconPath = iconPath;
            this.range = range;
            this.xpToReachLevel = xpToReachLevel;
            this.sellValue = sellValue;
        }
    }

    // PLACEHOLDER XP curve per hero — tune via playtesting.
    // Design target: Active 1 (L5) reachable in ~20-round match, Active 2 (L10) in ~30-round match.
    private static readonly Dictionary<string, HeroInfo> _heroInfo = new()
    {
        { "knight000", new HeroInfo(
            cost: 1500,
            iconPath: "UI/knight_icon",
            range: 3.5f,
            xpToReachLevel: new int[] { 0, 150, 400, 750, 1200, 1800, 2500, 3300, 4200, 5200 },
            sellValue: 750
        ) },
    };

    public static bool Exists(string heroType) => _heroInfo.ContainsKey(heroType);

    public static int GetCost(string heroType) =>
        _heroInfo.TryGetValue(heroType, out var i) ? i.cost : 0;

    public static string GetIconPath(string heroType) =>
        _heroInfo.TryGetValue(heroType, out var i) ? i.iconPath : null;

    public static float GetRange(string heroType) =>
        _heroInfo.TryGetValue(heroType, out var i) ? i.range : 0f;

    public static int GetSellValue(string heroType) =>
        _heroInfo.TryGetValue(heroType, out var i) ? i.sellValue : 0;

    // Total XP required to reach the given level (1..10). Level 1 costs 0.
    public static int GetXpToReachLevel(string heroType, int level)
    {
        if (!_heroInfo.TryGetValue(heroType, out var info)) return int.MaxValue;
        int idx = level - 1;
        if (idx < 0 || idx >= info.xpToReachLevel.Length) return int.MaxValue;
        return info.xpToReachLevel[idx];
    }

    // XP awarded for completing round N. Same curve for all heroes for now.
    public static int GetXpForRound(int round) => round * 15;
}
```

- [ ] **Step 2: Compile check**

`mcp__UnityMCP__refresh_unity` then `read_console` filtered to errors. Expected: clean (HeroData has no cross-file dependencies).

- [ ] **Step 3: Commit**

```bash
git add Assets/Scripts/HeroData.cs
git commit -m "feat(heroes): add HeroData static lookup with knight000 placeholder tuning"
```

---

## Task 6: Hero component — auto-attack + level-up plumbing

**Files:**
- Create: `Assets/Scripts/Hero.cs`

This task lands the MonoBehaviour with auto-attack, level/xp storage, and ability slots. Abilities are *declared* here but their callbacks are populated per-hero by `SilentKnightSetup` in Task 8. The auto-attack and `CastAbility` logic is framework-generic.

- [ ] **Step 1: Create Hero.cs**

Write `Assets/Scripts/Hero.cs`:

```csharp
using System;
using UnityEngine;

// Framework MonoBehaviour attached to every hero prefab.
// Implements ITowerAttack so the existing RangeIndicator and selection outline work unchanged.
public class Hero : MonoBehaviour, ITowerAttack
{
    [Header("Identity")]
    public string heroType = "knight000";

    [Header("Auto-attack")]
    public float range = 3.5f;
    public int attackDamage = 5;
    public float attackCooldown = 0.8f;
    public float projectileSpeed = 0.25f;
    public Color projectileColor = new Color(1f, 0.85f, 0.15f);

    [Header("Progression")]
    public int level = 1;
    public int xp = 0;

    [Header("Ability slots")]
    public HeroAbility passive;   // unlocked at L1
    public HeroAbility active1;   // unlocked at L5
    public HeroAbility active2;   // unlocked at L10

    public event Action<int> OnLevelUp;
    public event Action OnXpChanged;

    public float Range => range;

    public bool IsChanneling { get; private set; }

    private float _lastAttackTime = -999f;
    private Material _swordMaterial;

    void Start()
    {
        _swordMaterial = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        _swordMaterial.SetColor("_BaseColor", projectileColor);
        _swordMaterial.SetFloat("_Metallic", 0.9f);
        _swordMaterial.SetFloat("_Smoothness", 0.7f);
    }

    void Update()
    {
        // Run passive callback every frame while unlocked.
        if (passive != null && passive.isPassive && passive.IsUnlocked(level))
            passive.callback?.Invoke(this);

        if (IsChanneling) return;
        if (Time.time - _lastAttackTime < attackCooldown) return;

        Transform target = FindStrongestInRange();
        if (target != null)
            ShootSword(target);
    }

    Transform FindStrongestInRange()
    {
        Transform units = Spawn.UnitsParent;
        if (units == null) return null;

        Transform best = null;
        int bestHealth = -1;
        foreach (Transform unit in units)
        {
            var m = unit.GetComponent<Movement>();
            if (m == null || !m.enabled) continue;
            if (Vector3.Distance(transform.position, unit.position) > range) continue;
            if (m.health > bestHealth)
            {
                bestHealth = m.health;
                best = unit;
            }
        }
        return best;
    }

    void ShootSword(Transform target)
    {
        _lastAttackTime = Time.time;

        GameObject sword = new GameObject("HeroSword");
        var blade = GameObject.CreatePrimitive(PrimitiveType.Cube);
        blade.name = "_blade";
        Destroy(blade.GetComponent<Collider>());
        blade.transform.SetParent(sword.transform, false);
        blade.transform.localScale = new Vector3(0.08f, 0.08f, 0.55f);
        blade.GetComponent<Renderer>().sharedMaterial = _swordMaterial;

        sword.transform.position = transform.position + Vector3.up * 1.2f;
        TowerUtils.SetProjectileLayer(sword);

        Velocity vel = sword.AddComponent<Velocity>();
        vel.homing = true;
        vel.target = target.gameObject;
        vel.speed = projectileSpeed;
        vel.damage = attackDamage;
        vel.pierce = 1;
    }

    public void SetChanneling(bool value) => IsChanneling = value;

    public void AddXp(int amount)
    {
        if (amount <= 0) return;
        xp += amount;
        OnXpChanged?.Invoke();
        while (level < 10 && xp >= HeroData.GetXpToReachLevel(heroType, level + 1))
        {
            level++;
            OnLevelUp?.Invoke(level);
        }
    }

    // Called by HeroManager on ability-button click. Index 0 = active1, 1 = active2.
    public bool CastAbility(int index)
    {
        HeroAbility ability = index == 0 ? active1 : index == 1 ? active2 : null;
        if (ability == null || ability.isPassive) return false;
        if (!ability.IsReady(level)) return false;
        ability.lastCastTime = Time.time;
        ability.callback?.Invoke(this);
        return true;
    }

    public int XpTowardNextLevel()
    {
        if (level >= 10) return 0;
        int prev = HeroData.GetXpToReachLevel(heroType, level);
        return xp - prev;
    }

    public int XpRequiredForNextLevel()
    {
        if (level >= 10) return 0;
        int prev = HeroData.GetXpToReachLevel(heroType, level);
        int next = HeroData.GetXpToReachLevel(heroType, level + 1);
        return next - prev;
    }
}
```

- [ ] **Step 2: Compile check**

`mcp__UnityMCP__refresh_unity` then `read_console` filtered to errors. Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add Assets/Scripts/Hero.cs
git commit -m "feat(heroes): add Hero MonoBehaviour with auto-attack and level-up plumbing"
```

---

## Task 7: HeroManager singleton — lifecycle + XP award (no UI yet)

**Files:**
- Create: `Assets/Scripts/HeroManager.cs`

This task lands the singleton that holds the registered hero, awards XP on `OnRoundComplete`, and exposes `RegisterHero` / `UnregisterHero` / `CastAbility` / `IsHeroOwned`. UI is added in Task 12.

- [ ] **Step 1: Create HeroManager.cs**

Write `Assets/Scripts/HeroManager.cs`:

```csharp
using UnityEngine;

public class HeroManager : MonoBehaviour
{
    public static HeroManager Instance { get; private set; }

    public Hero ActiveHero { get; private set; }
    public bool IsHeroOwned => ActiveHero != null;

    private RoundManager _rounds;

    void Awake()
    {
        Instance = this;
    }

    void Start()
    {
        _rounds = FindAnyObjectByType<RoundManager>();
        if (_rounds != null)
            _rounds.OnRoundComplete += HandleRoundComplete;
    }

    void OnDestroy()
    {
        if (_rounds != null)
            _rounds.OnRoundComplete -= HandleRoundComplete;
        if (Instance == this) Instance = null;
    }

    public void RegisterHero(Hero hero)
    {
        if (ActiveHero != null && ActiveHero != hero)
        {
            Debug.LogWarning("[HeroManager] A hero is already registered; ignoring duplicate register.");
            return;
        }
        ActiveHero = hero;
    }

    public void UnregisterHero(Hero hero)
    {
        if (ActiveHero == hero)
            ActiveHero = null;
    }

    void HandleRoundComplete(int round)
    {
        if (ActiveHero == null) return;
        int xp = HeroData.GetXpForRound(round);
        ActiveHero.AddXp(xp);
    }

    // Forwarded by the top ability bar buttons and by TowerSelection's hero layout.
    public bool CastAbility(int index)
    {
        if (ActiveHero == null) return false;
        return ActiveHero.CastAbility(index);
    }
}
```

- [ ] **Step 2: Compile check**

`mcp__UnityMCP__refresh_unity` then `read_console` filtered to errors. Expected: clean.

- [ ] **Step 3: Wire HeroManager into the scene**

Use `mcp__UnityMCP__manage_gameobject` with `action="create"` to add a new GameObject named `HeroManager` at the scene root, then `action="add_component"` to attach the `HeroManager` component. Save the scene (`mcp__UnityMCP__manage_scene` with `action="save"`).

- [ ] **Step 4: Commit**

```bash
git add Assets/Scripts/HeroManager.cs Assets/game.unity
git commit -m "feat(heroes): add HeroManager singleton with round-complete XP award"
```

---

## Task 8: SilentKnightSetup — Zeal passive + ability stubs

**Files:**
- Create: `Assets/Scripts/SilentKnightSetup.cs`

This task lands the Silent Knight-specific configuration class. Passive is fully implemented. Active 1 and Active 2 callbacks land as empty stubs and are implemented in Tasks 10 and 11.

- [ ] **Step 1: Create SilentKnightSetup.cs**

Write `Assets/Scripts/SilentKnightSetup.cs`:

```csharp
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

// Silent Knight (knight000) per-hero configuration.
// Called by TowerPlacer._placementSetup["knight000"] immediately after the knight prefab is instantiated.
public static class SilentKnightSetup
{
    const float ZealAuraRadius = 4f;
    const float BookRange = 8f;
    const float BookChannelDuration = 3f;
    const int BookTickDamage = 5; // 5 dmg/sec = one tick per second
    const float JudgedDuration = 10f;

    // Per-frame cache on each hero: which towers we currently buff.
    // Keyed by Hero instance via a static dictionary so the passive callback is allocation-free at steady state.
    private static readonly Dictionary<Hero, HashSet<MonoBehaviour>> _affected = new();

    public static void Configure(GameObject heroObj)
    {
        Hero hero = heroObj.GetComponent<Hero>() ?? heroObj.AddComponent<Hero>();
        hero.heroType = "knight000";
        hero.range = HeroData.GetRange("knight000");
        hero.attackDamage = 5;
        hero.attackCooldown = 0.8f;
        hero.projectileColor = new Color(1f, 0.85f, 0.15f);

        hero.passive = new HeroAbility
        {
            name = "Templar's Zeal",
            iconPath = "UI/knight_zeal_icon",
            description = "Nearby towers gain bonus attack rate.",
            unlockLevel = 1,
            isPassive = true,
            cooldown = 0f,
            callback = ApplyZeal,
        };

        hero.active1 = new HeroAbility
        {
            name = "Crimson Arc",
            iconPath = "UI/knight_arc_icon",
            description = "360° sword sweep: 25 damage to every enemy in range.",
            unlockLevel = 5,
            cooldown = 12f,
            isPassive = false,
            callback = CrimsonArc,
        };

        hero.active2 = new HeroAbility
        {
            name = "The Templar's Book",
            iconPath = "UI/knight_book_icon",
            description = "Channel 3s: 5 dps to enemies in 8-unit range + Judged debuff (+25% dmg taken, 10s).",
            unlockLevel = 10,
            cooldown = 60f,
            isPassive = false,
            callback = TemplarsBook,
        };

        if (HeroManager.Instance != null)
            HeroManager.Instance.RegisterHero(hero);
    }

    // ─── Passive: Templar's Zeal ──────────────────────────────────────────────

    public static float GetZealBonus(int level)
    {
        // +10% at L1 stepping to +28% at L10 (2% per level).
        return 0.10f + (level - 1) * 0.02f;
    }

    static void ApplyZeal(Hero hero)
    {
        if (!_affected.TryGetValue(hero, out var previouslyAffected))
        {
            previouslyAffected = new HashSet<MonoBehaviour>();
            _affected[hero] = previouslyAffected;
        }

        float bonus = GetZealBonus(hero.level);
        float multiplier = 1f + bonus;

        var currentAffected = new HashSet<MonoBehaviour>();
        Vector3 heroPos = hero.transform.position;

        foreach (var tack in Object.FindObjectsByType<TackAttack>(FindObjectsSortMode.None))
        {
            if (Vector3.Distance(heroPos, tack.transform.position) > ZealAuraRadius) continue;
            tack.attackSpeedMultiplier = multiplier;
            currentAffected.Add(tack);
        }
        foreach (var sniper in Object.FindObjectsByType<SniperAttack>(FindObjectsSortMode.None))
        {
            if (Vector3.Distance(heroPos, sniper.transform.position) > ZealAuraRadius) continue;
            sniper.attackSpeedMultiplier = multiplier;
            currentAffected.Add(sniper);
        }
        foreach (var nature in Object.FindObjectsByType<NatureAttack>(FindObjectsSortMode.None))
        {
            if (Vector3.Distance(heroPos, nature.transform.position) > ZealAuraRadius) continue;
            nature.attackSpeedMultiplier = multiplier;
            currentAffected.Add(nature);
        }

        // Reset any tower that was buffed last frame but isn't in range now.
        foreach (var prev in previouslyAffected)
        {
            if (prev == null) continue;
            if (currentAffected.Contains(prev)) continue;
            switch (prev)
            {
                case TackAttack t: t.attackSpeedMultiplier = 1f; break;
                case SniperAttack s: s.attackSpeedMultiplier = 1f; break;
                case NatureAttack n: n.attackSpeedMultiplier = 1f; break;
            }
        }

        _affected[hero] = currentAffected;
    }

    // ─── Active 1: Crimson Arc (stub — implemented in Task 10) ───────────────

    static void CrimsonArc(Hero hero)
    {
        // Implemented in Task 10.
    }

    // ─── Active 2: Templar's Book (stub — implemented in Task 11) ────────────

    static void TemplarsBook(Hero hero)
    {
        // Implemented in Task 11.
    }
}
```

- [ ] **Step 2: Compile check**

`mcp__UnityMCP__refresh_unity` then `read_console` filtered to errors. Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add Assets/Scripts/SilentKnightSetup.cs
git commit -m "feat(knight): add SilentKnightSetup with Zeal passive, active ability stubs"
```

---

## Task 9: Knight placeholder prefab + TowerPlacer shop integration

**Files:**
- Create: `Assets/Prefabs/knight000.prefab` (via UnityMCP — see Step 1)
- Modify: `Assets/Scripts/TowerPlacer.cs`

Build a primitive-based stand-in so the hero is placeable and visible. The FBX swap is a follow-up.

- [ ] **Step 1: Create the placeholder prefab via UnityMCP**

Use `mcp__UnityMCP__execute_code` to run the following C# in the editor. This builds a knight GameObject from primitives (capsule body + helmet sphere + sword cube) and saves it as a prefab at `Assets/Prefabs/knight000.prefab`.

```csharp
using UnityEngine;
using UnityEditor;
using System.IO;

var root = new GameObject("knight000");

var body = GameObject.CreatePrimitive(PrimitiveType.Capsule);
body.name = "Body";
body.transform.SetParent(root.transform, false);
body.transform.localPosition = new Vector3(0, 0.8f, 0);
body.transform.localScale = new Vector3(0.6f, 0.8f, 0.6f);
{
    var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
    mat.SetColor("_BaseColor", new Color(0.75f, 0.75f, 0.82f));
    mat.SetFloat("_Metallic", 0.9f);
    mat.SetFloat("_Smoothness", 0.6f);
    body.GetComponent<Renderer>().sharedMaterial = mat;
}

var helm = GameObject.CreatePrimitive(PrimitiveType.Sphere);
helm.name = "Helmet";
helm.transform.SetParent(root.transform, false);
helm.transform.localPosition = new Vector3(0, 1.9f, 0);
helm.transform.localScale = Vector3.one * 0.55f;
{
    var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
    mat.SetColor("_BaseColor", new Color(0.9f, 0.85f, 0.5f));
    mat.SetFloat("_Metallic", 1f);
    mat.SetFloat("_Smoothness", 0.8f);
    helm.GetComponent<Renderer>().sharedMaterial = mat;
}

var sword = GameObject.CreatePrimitive(PrimitiveType.Cube);
sword.name = "Sword";
sword.transform.SetParent(root.transform, false);
sword.transform.localPosition = new Vector3(0.5f, 1.0f, 0.1f);
sword.transform.localScale = new Vector3(0.08f, 0.8f, 0.08f);
{
    var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
    mat.SetColor("_BaseColor", new Color(1f, 0.85f, 0.15f));
    mat.SetFloat("_Metallic", 1f);
    mat.SetFloat("_Smoothness", 0.9f);
    sword.GetComponent<Renderer>().sharedMaterial = mat;
}

if (!Directory.Exists("Assets/Prefabs")) Directory.CreateDirectory("Assets/Prefabs");
string path = "Assets/Prefabs/knight000.prefab";
PrefabUtility.SaveAsPrefabAsset(root, path);
Object.DestroyImmediate(root);
AssetDatabase.Refresh();
Debug.Log($"Created prefab at {path}");
```

Verify via `mcp__UnityMCP__read_console` that the "Created prefab at …" log appeared and no errors surfaced. Verify the file exists: `ls Assets/Prefabs/knight000.prefab`.

- [ ] **Step 2: Add knight000 to TowerPlacer**

In `Assets/Scripts/TowerPlacer.cs`:

(a) Add a new serialized prefab field next to `_sniperPrefab` (line 9). Replace:

```csharp
    [SerializeField] private GameObject _sniperPrefab;
```

with:

```csharp
    [SerializeField] private GameObject _sniperPrefab;
    [SerializeField] private GameObject _knightPrefab;
```

(b) Extend the `_prefabs` dictionary initialization (around line 43) from:

```csharp
        _prefabs = new Dictionary<string, GameObject>
        {
            { "tack000", _towerPrefab },
            { "sniper000", _sniperPrefab },
        };
```

to:

```csharp
        _prefabs = new Dictionary<string, GameObject>
        {
            { "tack000", _towerPrefab },
            { "sniper000", _sniperPrefab },
            { "knight000", _knightPrefab },
        };
```

(c) Extend `_placementSetup` (around line 49) by adding a knight entry after the sniper entry:

```csharp
            { "knight000", hero =>
                {
                    SilentKnightSetup.Configure(hero);
                }
            },
```

(d) In `BuildShopPanel` (around line 134, after the "-- Towers --" section), add a Heroes section. Replace the block:

```csharp
        // Header
        MakeLabel("-- Towers --", panel.transform);

        // Tower buttons
        MakeTowerButton("tack000", panel.transform);
        MakeTowerButton("sniper000", panel.transform);
```

with:

```csharp
        // Header
        MakeLabel("-- Towers --", panel.transform);

        // Tower buttons
        MakeTowerButton("tack000", panel.transform);
        MakeTowerButton("sniper000", panel.transform);

        // Heroes
        MakeLabel("-- Heroes --", panel.transform);
        MakeHeroButton("knight000", panel.transform);
```

(e) Add `MakeHeroButton` alongside `MakeTowerButton` (insert before the `MakeLabel` method around line 208):

```csharp
    void MakeHeroButton(string heroType, Transform parent)
    {
        int cost = HeroData.GetCost(heroType);
        string iconPath = HeroData.GetIconPath(heroType);
        Sprite iconSprite = iconPath != null ? Resources.Load<Sprite>(iconPath) : null;

        var go = new GameObject("HeroBtn_" + heroType);
        go.transform.SetParent(parent, false);
        go.AddComponent<LayoutElement>().preferredHeight = 150;

        var btn = go.AddComponent<Button>();
        string capturedType = heroType;
        btn.onClick.AddListener(() =>
        {
            if (HeroManager.Instance != null && HeroManager.Instance.IsHeroOwned) return;
            BeginPlacement(capturedType);
        });

        ColorBlock cb = btn.colors;
        cb.normalColor = Color.white;
        cb.highlightedColor = new Color(1.2f, 1.2f, 1.2f, 1f);
        cb.pressedColor = new Color(0.8f, 0.8f, 0.8f, 1f);
        cb.disabledColor = new Color(0.5f, 0.5f, 0.5f, 0.5f);
        btn.colors = cb;

        var bg = go.AddComponent<Image>();
        bg.color = new Color(0.45f, 0.25f, 0.45f); // purple tint to distinguish from towers

        var iconGO = new GameObject("Icon");
        iconGO.transform.SetParent(go.transform, false);
        var iconImg = iconGO.AddComponent<Image>();
        if (iconSprite != null) { iconImg.sprite = iconSprite; iconImg.preserveAspect = true; }
        iconImg.color = Color.white;
        var iconRT = iconGO.GetComponent<RectTransform>();
        iconRT.anchorMin = new Vector2(0.05f, 0.2f);
        iconRT.anchorMax = new Vector2(0.95f, 0.95f);
        iconRT.offsetMin = Vector2.zero;
        iconRT.offsetMax = Vector2.zero;

        var priceGO = new GameObject("PriceLabel");
        priceGO.transform.SetParent(go.transform, false);
        var priceTxt = priceGO.AddComponent<Text>();
        priceTxt.text = $"${cost}";
        priceTxt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        priceTxt.fontSize = 20;
        priceTxt.color = Color.white;
        priceTxt.alignment = TextAnchor.MiddleCenter;
        priceTxt.fontStyle = FontStyle.Bold;

        var outline = priceGO.AddComponent<Outline>();
        outline.effectColor = Color.black;
        outline.effectDistance = new Vector2(1, -1);

        var priceRT = priceGO.GetComponent<RectTransform>();
        priceRT.anchorMin = new Vector2(0, 0);
        priceRT.anchorMax = new Vector2(1, 0.22f);
        priceRT.offsetMin = Vector2.zero;
        priceRT.offsetMax = Vector2.zero;
    }
```

(f) In `PlaceTower` (around line 335-344), hero placement uses the placement-setup but should skip `TowerData`. Update the method to only add `TowerData` when the placing type is in `TowerCosts` (i.e. a tower, not a hero). Find the block:

```csharp
        TowerData data = _preview.GetComponent<TowerData>() ?? _preview.AddComponent<TowerData>();
        data.towerType = _placingType;
        int cost = TowerCosts.GetPlacementCost(_placingType);
        data.totalInvested = cost;

        FloatingText.Spawn(_preview.transform.position, $"-${cost}", new Color(0.9f, 0.15f, 0.1f), 1.2f, 28, false, 80f);

        if (_placementSetup.TryGetValue(_placingType, out var setup))
            setup(_preview);
```

Replace with:

```csharp
        bool isHero = HeroData.Exists(_placingType);
        int cost = isHero ? HeroData.GetCost(_placingType) : TowerCosts.GetPlacementCost(_placingType);

        if (!isHero)
        {
            TowerData data = _preview.GetComponent<TowerData>() ?? _preview.AddComponent<TowerData>();
            data.towerType = _placingType;
            data.totalInvested = cost;
        }

        FloatingText.Spawn(_preview.transform.position, $"-${cost}", new Color(0.9f, 0.15f, 0.1f), 1.2f, 28, false, 80f);

        if (_placementSetup.TryGetValue(_placingType, out var setup))
            setup(_preview);
```

(g) The placement-cost TrySpend gate in `Update` (around line 283) also assumes `TowerCosts`. Replace:

```csharp
            int cost = TowerCosts.GetPlacementCost(_placingType);
            if (EconomyManager.Instance == null || !EconomyManager.Instance.TrySpend(cost))
                return;
```

with:

```csharp
            int cost = HeroData.Exists(_placingType)
                ? HeroData.GetCost(_placingType)
                : TowerCosts.GetPlacementCost(_placingType);
            if (EconomyManager.Instance == null || !EconomyManager.Instance.TrySpend(cost))
                return;
```

(h) The range indicator during preview (line 253) uses `TowerCosts.GetRange`. Replace:

```csharp
        _rangeIndicator = RangeIndicator.Create(TowerCosts.GetRange(_placingType), _preview.transform);
```

with:

```csharp
        float previewRange = HeroData.Exists(_placingType)
            ? HeroData.GetRange(_placingType)
            : TowerCosts.GetRange(_placingType);
        _rangeIndicator = RangeIndicator.Create(previewRange, _preview.transform);
```

(i) Add a dev auto-place for the knight. Below the two existing `DEV_` position constants (around line 36):

```csharp
    private static readonly Vector3 DEV_KNIGHT_POS = new Vector3(7f, -0.05f, 10f);
```

And in `Start` after the existing two dev placements (line 74):

```csharp
            DevPlaceTower("knight000", DEV_KNIGHT_POS);
```

Also fix `DevPlaceTower` (lines 78-97) to skip `TowerData` for heroes. Replace the method body from:

```csharp
        TowerData data = tower.GetComponent<TowerData>() ?? tower.AddComponent<TowerData>();
        data.towerType = type;
        data.totalInvested = 0;

        if (_placementSetup.TryGetValue(type, out var setup))
            setup(tower);
```

with:

```csharp
        if (!HeroData.Exists(type))
        {
            TowerData data = tower.GetComponent<TowerData>() ?? tower.AddComponent<TowerData>();
            data.towerType = type;
            data.totalInvested = 0;
        }

        if (_placementSetup.TryGetValue(type, out var setup))
            setup(tower);
```

- [ ] **Step 3: Wire the knight prefab reference in the scene**

The `_knightPrefab` serialized field is empty. Use `mcp__UnityMCP__manage_components` or the `find_gameobjects`/`manage_gameobject` pair to locate the TowerPlacer GameObject and set the `_knightPrefab` field to `Assets/Prefabs/knight000.prefab`. Save the scene afterward.

If the tool cannot set a serialized prefab directly, run this editor snippet via `mcp__UnityMCP__execute_code`:

```csharp
using UnityEngine;
using UnityEditor;

var placer = Object.FindAnyObjectByType<TowerPlacer>();
var prefab = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Prefabs/knight000.prefab");
var so = new SerializedObject(placer);
so.FindProperty("_knightPrefab").objectReferenceValue = prefab;
so.ApplyModifiedPropertiesWithoutUndo();
EditorSceneManager.MarkSceneDirty(placer.gameObject.scene);
EditorSceneManager.SaveOpenScenes();
Debug.Log("Knight prefab assigned.");
```

(Namespace `UnityEditor.SceneManagement.EditorSceneManager` — add `using UnityEditor.SceneManagement;` if needed.)

- [ ] **Step 4: Compile check + play-mode smoke test**

`mcp__UnityMCP__refresh_unity` then `read_console` filtered to errors. Expected: clean.

Enter play mode. Expected:
- The left-side shop panel shows a `-- Heroes --` section with a knight button priced at $1500.
- A knight stand-in (capsule + sphere + cube) appears at `(7, -0.05, 10)` via dev auto-place.
- Walking enemies within range 3.5 of the knight get hit by a yellow cube "sword" homing projectile.
- Towers within 4 units of the knight fire noticeably faster (Zeal +10% at L1).

Exit play mode.

- [ ] **Step 5: Commit**

```bash
git add Assets/Prefabs/knight000.prefab Assets/Prefabs/knight000.prefab.meta Assets/Scripts/TowerPlacer.cs Assets/game.unity
git commit -m "feat(knight): placeholder prefab + shop/placement integration"
```

If there is no `Assets/Prefabs/knight000.prefab.meta` yet, omit it and let Unity regenerate it.

---

## Task 10: Crimson Arc — Active 1

**Files:**
- Modify: `Assets/Scripts/SilentKnightSetup.cs`

Implements the instant 360° sword sweep: 25 damage to every enemy within the knight's range.

- [ ] **Step 1: Replace the CrimsonArc stub**

In `Assets/Scripts/SilentKnightSetup.cs`, replace:

```csharp
    static void CrimsonArc(Hero hero)
    {
        // Implemented in Task 10.
    }
```

with:

```csharp
    const int CrimsonArcDamage = 25;

    static void CrimsonArc(Hero hero)
    {
        Transform units = Spawn.UnitsParent;
        if (units != null)
        {
            // Snapshot the iteration target since Hit() may destroy/reparent enemies.
            var targets = new List<Transform>();
            foreach (Transform unit in units) targets.Add(unit);

            foreach (var unit in targets)
            {
                if (unit == null) continue;
                var m = unit.GetComponent<Movement>();
                if (m == null || !m.enabled) continue;
                if (Vector3.Distance(hero.transform.position, unit.position) > hero.range) continue;
                m.Hit(CrimsonArcDamage);
            }
        }

        hero.StartCoroutine(PlayCrimsonArcVisual(hero));
    }

    static IEnumerator PlayCrimsonArcVisual(Hero hero)
    {
        var slash = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        slash.name = "_CrimsonArc";
        Object.Destroy(slash.GetComponent<Collider>());
        slash.transform.position = hero.transform.position + Vector3.up * 0.03f;
        slash.transform.localScale = new Vector3(0.1f, 0.02f, 0.1f);

        var mat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        mat.SetColor("_BaseColor", new Color(0.95f, 0.05f, 0.15f, 0.75f));
        MaterialUtils.MakeTransparent(mat);
        slash.GetComponent<Renderer>().material = mat;

        float duration = 0.3f;
        float targetDiameter = hero.range * 2f;
        float t = 0f;
        while (slash != null && t < duration)
        {
            float k = t / duration;
            float d = Mathf.Lerp(0.1f, targetDiameter, k);
            slash.transform.localScale = new Vector3(d, 0.02f, d);
            Color c = mat.GetColor("_BaseColor");
            c.a = Mathf.Lerp(0.75f, 0f, k);
            mat.SetColor("_BaseColor", c);
            t += Time.deltaTime;
            yield return null;
        }
        if (slash != null) Object.Destroy(slash);
    }
```

- [ ] **Step 2: Compile check**

`mcp__UnityMCP__refresh_unity` then `read_console` filtered to errors. Expected: clean.

- [ ] **Step 3: Play-mode smoke test**

Enter play mode. Temporarily force-level the knight by running in `mcp__UnityMCP__execute_code`:

```csharp
var h = Object.FindAnyObjectByType<Hero>();
if (h != null) { h.AddXp(HeroData.GetXpToReachLevel(h.heroType, 5)); Debug.Log($"Hero level {h.level}"); }
```

Expected log: `Hero level 5`. Spawn enemies via the Unit button. Call:

```csharp
HeroManager.Instance.CastAbility(0);
```

Expected: red expanding disc visual on the ground at the knight's position; every enemy inside the 3.5-unit range takes 25 damage (small units die instantly, big units lose 25 HP). Second immediate call within 12s should fail silently (cooldown gate).

Exit play mode.

- [ ] **Step 4: Commit**

```bash
git add Assets/Scripts/SilentKnightSetup.cs
git commit -m "feat(knight): implement Crimson Arc active (Active 1)"
```

---

## Task 11: Templar's Book — Active 2

**Files:**
- Modify: `Assets/Scripts/SilentKnightSetup.cs`

Implements the 3-second channel: 5 dps to enemies within 8-unit range plus apply/refresh Judged debuff.

- [ ] **Step 1: Replace the TemplarsBook stub**

In `Assets/Scripts/SilentKnightSetup.cs`, replace:

```csharp
    static void TemplarsBook(Hero hero)
    {
        // Implemented in Task 11.
    }
```

with:

```csharp
    static void TemplarsBook(Hero hero)
    {
        hero.StartCoroutine(ChannelTemplarsBook(hero));
    }

    static IEnumerator ChannelTemplarsBook(Hero hero)
    {
        hero.SetChanneling(true);

        // Ground pulse visual — oscillates for the channel's duration.
        var pulse = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        pulse.name = "_BookChannelFX";
        Object.Destroy(pulse.GetComponent<Collider>());
        pulse.transform.SetParent(hero.transform, false);
        pulse.transform.localPosition = Vector3.up * 0.04f;
        float diameter = BookRange * 2f;
        pulse.transform.localScale = new Vector3(diameter, 0.02f, diameter);
        var pulseMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        pulseMat.SetColor("_BaseColor", new Color(0.9f, 0.1f, 0.2f, 0.25f));
        MaterialUtils.MakeTransparent(pulseMat);
        pulse.GetComponent<Renderer>().material = pulseMat;

        float channelStart = Time.time;
        float nextTick = Time.time;

        while (Time.time - channelStart < BookChannelDuration)
        {
            if (Time.time >= nextTick)
            {
                nextTick = Time.time + 1f;
                ApplyBookTick(hero);
            }
            // Breathe the pulse alpha for feedback.
            float osc = 0.2f + Mathf.Sin((Time.time - channelStart) * 8f) * 0.08f;
            Color c = pulseMat.GetColor("_BaseColor");
            c.a = osc;
            pulseMat.SetColor("_BaseColor", c);
            yield return null;
        }

        if (pulse != null) Object.Destroy(pulse);
        hero.SetChanneling(false);
    }

    static void ApplyBookTick(Hero hero)
    {
        Transform units = Spawn.UnitsParent;
        if (units == null) return;

        var targets = new List<Transform>();
        foreach (Transform unit in units) targets.Add(unit);

        foreach (var unit in targets)
        {
            if (unit == null) continue;
            var m = unit.GetComponent<Movement>();
            if (m == null || !m.enabled) continue;
            if (Vector3.Distance(hero.transform.position, unit.position) > BookRange) continue;

            m.Hit(BookTickDamage);
            if (unit == null) continue; // destroyed by Hit
            var judged = unit.GetComponent<JudgedEffect>();
            if (judged == null)
            {
                var j = unit.gameObject.AddComponent<JudgedEffect>();
                j.duration = JudgedDuration;
            }
            else
            {
                judged.Refresh();
            }
        }
    }
```

- [ ] **Step 2: Compile check**

`mcp__UnityMCP__refresh_unity` then `read_console` filtered to errors. Expected: clean.

- [ ] **Step 3: Play-mode smoke test**

Enter play mode. Force-level to 10 via `execute_code`:

```csharp
var h = Object.FindAnyObjectByType<Hero>();
if (h != null) { h.AddXp(HeroData.GetXpToReachLevel(h.heroType, 10)); Debug.Log($"Hero level {h.level}"); }
```

Expected log: `Hero level 10`. Spawn a Big Unit. Cast Active 2:

```csharp
HeroManager.Instance.CastAbility(1);
```

Expected:
- A faint red disc appears around the knight for 3 seconds and breathes.
- The knight's auto-attack pauses during the channel.
- Every second, enemies within 8 units take 5 damage *and* gain a floating red cross glyph above their head.
- After channel ends, the glyph persists for ~10 seconds, then disappears.
- While glyph is up, the next hit from any source deals 25% more damage (verify with floating damage text: e.g. a 5-damage sword hit shows `6` instead of `5`).

Exit play mode.

- [ ] **Step 4: Commit**

```bash
git add Assets/Scripts/SilentKnightSetup.cs
git commit -m "feat(knight): implement Templar's Book channel with Judged debuff (Active 2)"
```

---

## Task 12: HeroManager top ability bar UI

**Files:**
- Modify: `Assets/Scripts/HeroManager.cs`

Adds the permanent top-of-screen ability bar. Hidden until a hero registers; shows hero portrait + level badge + three ability icons with lock overlays and radial cooldown sweep.

- [ ] **Step 1: Replace HeroManager.cs**

Overwrite `Assets/Scripts/HeroManager.cs` with:

```csharp
using UnityEngine;
using UnityEngine.UI;

public class HeroManager : MonoBehaviour
{
    public static HeroManager Instance { get; private set; }

    public Hero ActiveHero { get; private set; }
    public bool IsHeroOwned => ActiveHero != null;

    private RoundManager _rounds;

    // UI
    private GameObject _canvasObj;
    private GameObject _barRoot;
    private Image _portraitImage;
    private Text _levelBadge;
    private AbilityIconWidgets _passive;
    private AbilityIconWidgets _active1;
    private AbilityIconWidgets _active2;

    struct AbilityIconWidgets
    {
        public GameObject root;
        public Image icon;
        public Image cooldownSweep; // filled radial
        public GameObject lockOverlay;
        public Text lockText;
        public Button button;
    }

    void Awake()
    {
        Instance = this;
    }

    void Start()
    {
        _rounds = FindAnyObjectByType<RoundManager>();
        if (_rounds != null)
            _rounds.OnRoundComplete += HandleRoundComplete;

        BuildUI();
        SetBarVisible(false);
    }

    void OnDestroy()
    {
        if (_rounds != null)
            _rounds.OnRoundComplete -= HandleRoundComplete;
        if (Instance == this) Instance = null;
    }

    void Update()
    {
        if (ActiveHero == null) return;
        RefreshAbilityWidgets();
    }

    // ─── Registration ─────────────────────────────────────────────────────────

    public void RegisterHero(Hero hero)
    {
        if (ActiveHero != null && ActiveHero != hero) return;
        ActiveHero = hero;
        SetBarVisible(true);
        PopulatePortrait();
        RefreshAbilityWidgets();
    }

    public void UnregisterHero(Hero hero)
    {
        if (ActiveHero != hero) return;
        ActiveHero = null;
        SetBarVisible(false);
    }

    void HandleRoundComplete(int round)
    {
        if (ActiveHero == null) return;
        ActiveHero.AddXp(HeroData.GetXpForRound(round));
    }

    public bool CastAbility(int index)
    {
        if (ActiveHero == null) return false;
        return ActiveHero.CastAbility(index);
    }

    // ─── UI Build ─────────────────────────────────────────────────────────────

    void BuildUI()
    {
        _canvasObj = new GameObject("HeroBarUI");
        var canvas = _canvasObj.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 25;

        var scaler = _canvasObj.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920, 1080);

        _canvasObj.AddComponent<GraphicRaycaster>();

        _barRoot = new GameObject("HeroBar");
        _barRoot.transform.SetParent(_canvasObj.transform, false);

        var rt = _barRoot.AddComponent<RectTransform>();
        rt.anchorMin = new Vector2(0.72f, 1f);
        rt.anchorMax = new Vector2(0.72f, 1f);
        rt.pivot = new Vector2(0f, 1f);
        rt.anchoredPosition = new Vector2(0f, -6f);
        rt.sizeDelta = new Vector2(260, 50);

        var bg = _barRoot.AddComponent<Image>();
        bg.color = new Color(0.15f, 0.15f, 0.15f, 0.85f);

        var layout = _barRoot.AddComponent<HorizontalLayoutGroup>();
        layout.padding = new RectOffset(6, 6, 5, 5);
        layout.spacing = 6;
        layout.childAlignment = TextAnchor.MiddleLeft;
        layout.childForceExpandWidth = false;
        layout.childForceExpandHeight = false;

        // Portrait + level badge
        var portraitRoot = new GameObject("Portrait");
        portraitRoot.transform.SetParent(_barRoot.transform, false);
        portraitRoot.AddComponent<LayoutElement>().preferredWidth = 44;
        var portraitImg = portraitRoot.AddComponent<Image>();
        portraitImg.color = new Color(0.25f, 0.25f, 0.3f);
        _portraitImage = portraitImg;

        var badgeGO = new GameObject("LevelBadge");
        badgeGO.transform.SetParent(portraitRoot.transform, false);
        var badgeRT = badgeGO.AddComponent<RectTransform>();
        badgeRT.anchorMin = new Vector2(1f, 0f);
        badgeRT.anchorMax = new Vector2(1f, 0f);
        badgeRT.pivot = new Vector2(1f, 0f);
        badgeRT.sizeDelta = new Vector2(20, 18);
        var badgeBG = badgeGO.AddComponent<Image>();
        badgeBG.color = new Color(0f, 0f, 0f, 0.8f);

        _levelBadge = AddTextChild(badgeGO, "1", 12, Color.yellow);

        _passive = MakeAbilityWidget(_barRoot.transform, "Passive", 0, isPassive: true);
        _active1 = MakeAbilityWidget(_barRoot.transform, "Active1", 0, isPassive: false);
        _active2 = MakeAbilityWidget(_barRoot.transform, "Active2", 1, isPassive: false);
    }

    AbilityIconWidgets MakeAbilityWidget(Transform parent, string label, int castIndex, bool isPassive)
    {
        var widgets = new AbilityIconWidgets();

        var root = new GameObject(label);
        root.transform.SetParent(parent, false);
        root.AddComponent<LayoutElement>().preferredWidth = 44;

        var bg = root.AddComponent<Image>();
        bg.color = new Color(0.1f, 0.1f, 0.1f, 0.8f);
        widgets.root = root;

        // Icon
        var iconGO = new GameObject("Icon");
        iconGO.transform.SetParent(root.transform, false);
        var iconImg = iconGO.AddComponent<Image>();
        iconImg.preserveAspect = true;
        iconImg.raycastTarget = false;
        var iconRT = iconGO.GetComponent<RectTransform>();
        iconRT.anchorMin = new Vector2(0.1f, 0.1f);
        iconRT.anchorMax = new Vector2(0.9f, 0.9f);
        iconRT.offsetMin = Vector2.zero;
        iconRT.offsetMax = Vector2.zero;
        widgets.icon = iconImg;

        // Cooldown sweep (radial filled image)
        var sweepGO = new GameObject("CooldownSweep");
        sweepGO.transform.SetParent(root.transform, false);
        var sweepImg = sweepGO.AddComponent<Image>();
        sweepImg.color = new Color(0f, 0f, 0f, 0.55f);
        sweepImg.type = Image.Type.Filled;
        sweepImg.fillMethod = Image.FillMethod.Radial360;
        sweepImg.fillOrigin = (int)Image.Origin360.Top;
        sweepImg.fillAmount = 0f;
        sweepImg.raycastTarget = false;
        var sweepRT = sweepGO.GetComponent<RectTransform>();
        sweepRT.anchorMin = Vector2.zero;
        sweepRT.anchorMax = Vector2.one;
        sweepRT.offsetMin = Vector2.zero;
        sweepRT.offsetMax = Vector2.zero;
        widgets.cooldownSweep = sweepImg;

        // Lock overlay (shown when level < unlockLevel)
        var lockGO = new GameObject("Lock");
        lockGO.transform.SetParent(root.transform, false);
        var lockImg = lockGO.AddComponent<Image>();
        lockImg.color = new Color(0f, 0f, 0f, 0.75f);
        lockImg.raycastTarget = false;
        var lockRT = lockGO.GetComponent<RectTransform>();
        lockRT.anchorMin = Vector2.zero;
        lockRT.anchorMax = Vector2.one;
        lockRT.offsetMin = Vector2.zero;
        lockRT.offsetMax = Vector2.zero;
        widgets.lockOverlay = lockGO;
        widgets.lockText = AddTextChild(lockGO, "L?", 14, Color.white);

        // Clickable button (actives only)
        if (!isPassive)
        {
            var btn = root.AddComponent<Button>();
            int captured = castIndex;
            btn.onClick.AddListener(() => CastAbility(captured));
            widgets.button = btn;
        }

        return widgets;
    }

    static Text AddTextChild(GameObject parent, string txt, int size, Color color)
    {
        var go = new GameObject("Text");
        go.transform.SetParent(parent.transform, false);
        var t = go.AddComponent<Text>();
        t.text = txt;
        t.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        t.alignment = TextAnchor.MiddleCenter;
        t.color = color;
        t.fontSize = size;
        t.fontStyle = FontStyle.Bold;
        t.raycastTarget = false;
        var outline = go.AddComponent<Outline>();
        outline.effectColor = Color.black;
        outline.effectDistance = new Vector2(1, -1);
        var rt = go.GetComponent<RectTransform>();
        rt.anchorMin = Vector2.zero;
        rt.anchorMax = Vector2.one;
        rt.offsetMin = Vector2.zero;
        rt.offsetMax = Vector2.zero;
        return t;
    }

    void SetBarVisible(bool visible)
    {
        if (_barRoot != null) _barRoot.SetActive(visible);
    }

    void PopulatePortrait()
    {
        if (ActiveHero == null) return;
        string iconPath = HeroData.GetIconPath(ActiveHero.heroType);
        var sprite = iconPath != null ? Resources.Load<Sprite>(iconPath) : null;
        if (sprite != null) _portraitImage.sprite = sprite;

        ApplyAbilityIcon(_passive, ActiveHero.passive);
        ApplyAbilityIcon(_active1, ActiveHero.active1);
        ApplyAbilityIcon(_active2, ActiveHero.active2);
    }

    static void ApplyAbilityIcon(AbilityIconWidgets w, HeroAbility a)
    {
        if (a == null) return;
        if (!string.IsNullOrEmpty(a.iconPath))
        {
            var sprite = Resources.Load<Sprite>(a.iconPath);
            if (sprite != null) w.icon.sprite = sprite;
        }
    }

    void RefreshAbilityWidgets()
    {
        if (ActiveHero == null) return;

        _levelBadge.text = ActiveHero.level.ToString();

        RefreshOne(_passive, ActiveHero.passive);
        RefreshOne(_active1, ActiveHero.active1);
        RefreshOne(_active2, ActiveHero.active2);
    }

    void RefreshOne(AbilityIconWidgets w, HeroAbility a)
    {
        if (a == null || ActiveHero == null)
        {
            w.lockOverlay.SetActive(true);
            w.lockText.text = "—";
            w.cooldownSweep.fillAmount = 0f;
            if (w.button != null) w.button.interactable = false;
            return;
        }

        bool unlocked = a.IsUnlocked(ActiveHero.level);
        w.lockOverlay.SetActive(!unlocked);
        w.lockText.text = unlocked ? "" : $"L{a.unlockLevel}";

        if (a.isPassive)
        {
            w.cooldownSweep.fillAmount = 0f;
            return;
        }

        float remaining = a.CooldownRemaining();
        w.cooldownSweep.fillAmount = a.cooldown > 0f ? Mathf.Clamp01(remaining / a.cooldown) : 0f;

        if (w.button != null)
            w.button.interactable = unlocked && remaining <= 0f;
    }
}
```

- [ ] **Step 2: Compile check**

`mcp__UnityMCP__refresh_unity` then `read_console` filtered to errors. Expected: clean.

- [ ] **Step 3: Play-mode smoke test**

Enter play mode. Expected:
- Before a hero is placed (no DEV_AUTO_PLACE of knight? — there is one in Task 9, so a hero is already registered on scene start).
- Actually DEV_AUTO_PLACE places a knight → top bar is visible from scene start: portrait square + level badge "1" + three square icons.
- Passive icon is always lit (no lock overlay).
- Active 1 icon shows a black "L5" lock overlay.
- Active 2 icon shows a black "L10" lock overlay.
- Force-level via `execute_code`: `var h = Object.FindAnyObjectByType<Hero>(); h.AddXp(700); Debug.Log(h.level);` — hero reaches L4. Lock still on A1.
- Add another 500 XP: `h.AddXp(500);` — hero reaches L5. A1 lock clears, button becomes clickable.
- Click A1. Expected: Crimson Arc fires; the A1 icon darkens with a radial sweep counting down from full to empty over 12s.
- Reach L10 via more XP and verify A2 unlock behaves the same way.

Exit play mode.

- [ ] **Step 4: Commit**

```bash
git add Assets/Scripts/HeroManager.cs
git commit -m "feat(heroes): permanent top ability bar UI with lock/cooldown widgets"
```

---

## Task 13: TowerSelection hero panel layout

**Files:**
- Modify: `Assets/Scripts/TowerSelection.cs`

When the selected object has a `Hero` component (instead of `TowerData`), the right-side action panel swaps to a hero layout: portrait, name, level + XP bar, passive text, two ability buttons, sell.

- [ ] **Step 1: Add hero layout fields**

In `Assets/Scripts/TowerSelection.cs`, add new fields below the existing `_upgradeXIcon` fields (after line 28):

```csharp
    // Hero layout fields
    private GameObject _heroLayoutRoot;
    private Text _heroNameText;
    private Text _heroLevelText;
    private Image _heroXpBarFill;
    private Text _heroPassiveText;
    private Button _heroActive1Button;
    private Image _heroActive1Cooldown;
    private GameObject _heroActive1Lock;
    private Text _heroActive1LockText;
    private Button _heroActive2Button;
    private Image _heroActive2Cooldown;
    private GameObject _heroActive2Lock;
    private Text _heroActive2LockText;
    private Button _heroSellButton;
    private GameObject _towerLayoutRoot; // groups existing tower upgrade widgets so we can hide them
```

- [ ] **Step 2: Wrap existing tower buttons in a group container**

In `BuildUI` (currently builds buttons directly onto `_actionPanel`), change it so the tower-specific widgets live inside a container we can toggle. Replace the `BuildUI` method (lines 241-295) with:

```csharp
    void BuildUI()
    {
        // Canvas
        _panelCanvas = new GameObject("SelectionUI");
        var canvas = _panelCanvas.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 10;

        var scaler = _panelCanvas.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920, 1080);

        _panelCanvas.AddComponent<GraphicRaycaster>();

        _actionPanel = new GameObject("ActionPanel");
        _actionPanel.transform.SetParent(_panelCanvas.transform, false);

        var prt = _actionPanel.AddComponent<RectTransform>();
        prt.anchorMin = new Vector2(1, 0.3f);
        prt.anchorMax = new Vector2(1, 0.7f);
        prt.pivot = new Vector2(1, 0.5f);
        prt.anchoredPosition = Vector2.zero;
        prt.sizeDelta = new Vector2(220, 0);

        _actionPanel.AddComponent<Image>().color = new Color(0.627f, 0.322f, 0.176f, 0.95f);

        // Tower layout (upgrade buttons)
        _towerLayoutRoot = BuildTowerLayout(_actionPanel.transform);

        // Hero layout
        _heroLayoutRoot = BuildHeroLayout(_actionPanel.transform);
        _heroLayoutRoot.SetActive(false);

        _actionPanel.SetActive(false);
    }

    GameObject BuildTowerLayout(Transform parent)
    {
        var root = new GameObject("TowerLayout");
        root.transform.SetParent(parent, false);
        var rt = root.AddComponent<RectTransform>();
        rt.anchorMin = Vector2.zero;
        rt.anchorMax = Vector2.one;
        rt.offsetMin = Vector2.zero;
        rt.offsetMax = Vector2.zero;

        var layout = root.AddComponent<VerticalLayoutGroup>();
        layout.padding = new RectOffset(10, 10, 10, 10);
        layout.spacing = 8;
        layout.childForceExpandWidth = true;
        layout.childForceExpandHeight = false;
        layout.childAlignment = TextAnchor.UpperCenter;

        _sellButton = MakeButton("Sell", root.transform, new Color(0.7f, 0.15f, 0.15f));
        _sellButton.onClick.AddListener(OnSell);

        MakeLabel("-- Upgrades --", root.transform);

        Color btnColor = new Color(0.545f, 0.271f, 0.075f);

        _upgrade1Button = MakeUpgradeButton("Path 1", root.transform, btnColor, "UI/tack100_icon", out _upgrade1Icon);
        _upgrade1Button.onClick.AddListener(() => OnUpgrade(1));

        _upgrade2Button = MakeUpgradeButton("Path 2", root.transform, btnColor, "UI/tack010_icon", out _upgrade2Icon);
        _upgrade2Button.onClick.AddListener(() => OnUpgrade(2));

        _upgrade3Button = MakeUpgradeButton("Path 3", root.transform, btnColor, "UI/tack001_icon", out _upgrade3Icon);
        _upgrade3Button.onClick.AddListener(() => OnUpgrade(3));

        return root;
    }

    GameObject BuildHeroLayout(Transform parent)
    {
        var root = new GameObject("HeroLayout");
        root.transform.SetParent(parent, false);
        var rt = root.AddComponent<RectTransform>();
        rt.anchorMin = Vector2.zero;
        rt.anchorMax = Vector2.one;
        rt.offsetMin = Vector2.zero;
        rt.offsetMax = Vector2.zero;

        var layout = root.AddComponent<VerticalLayoutGroup>();
        layout.padding = new RectOffset(10, 10, 10, 10);
        layout.spacing = 6;
        layout.childForceExpandWidth = true;
        layout.childForceExpandHeight = false;
        layout.childAlignment = TextAnchor.UpperCenter;

        _heroNameText = MakeHeroText("NameText", root.transform, 20, Color.white, 30);

        _heroLevelText = MakeHeroText("LevelText", root.transform, 14, new Color(1f, 0.85f, 0.3f), 20);

        // XP bar
        var xpBar = new GameObject("XpBar");
        xpBar.transform.SetParent(root.transform, false);
        xpBar.AddComponent<LayoutElement>().preferredHeight = 10;
        var xpBg = xpBar.AddComponent<Image>();
        xpBg.color = new Color(0.1f, 0.1f, 0.1f, 0.8f);

        var xpFill = new GameObject("Fill");
        xpFill.transform.SetParent(xpBar.transform, false);
        _heroXpBarFill = xpFill.AddComponent<Image>();
        _heroXpBarFill.color = new Color(0.9f, 0.75f, 0.2f);
        var frt = xpFill.GetComponent<RectTransform>();
        frt.anchorMin = Vector2.zero;
        frt.anchorMax = new Vector2(0f, 1f);
        frt.pivot = new Vector2(0f, 0.5f);
        frt.offsetMin = Vector2.zero;
        frt.offsetMax = Vector2.zero;

        MakeLabel("-- Passive --", root.transform);
        _heroPassiveText = MakeHeroText("PassiveText", root.transform, 12, new Color(1f, 1f, 1f, 0.9f), 48);
        _heroPassiveText.alignment = TextAnchor.UpperCenter;

        MakeLabel("-- Abilities --", root.transform);

        (_heroActive1Button, _heroActive1Cooldown, _heroActive1Lock, _heroActive1LockText) =
            MakeHeroAbilityButton("Active 1", root.transform, 0);
        (_heroActive2Button, _heroActive2Cooldown, _heroActive2Lock, _heroActive2LockText) =
            MakeHeroAbilityButton("Active 2", root.transform, 1);

        _heroSellButton = MakeButton("Sell", root.transform, new Color(0.7f, 0.15f, 0.15f));
        _heroSellButton.onClick.AddListener(OnHeroSell);

        return root;
    }

    Text MakeHeroText(string name, Transform parent, int fontSize, Color color, float height)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var t = go.AddComponent<Text>();
        t.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        t.alignment = TextAnchor.MiddleCenter;
        t.color = color;
        t.fontSize = fontSize;
        go.AddComponent<LayoutElement>().preferredHeight = height;
        return t;
    }

    (Button, Image, GameObject, Text) MakeHeroAbilityButton(string label, Transform parent, int index)
    {
        var go = new GameObject(label);
        go.transform.SetParent(parent, false);
        go.AddComponent<LayoutElement>().preferredHeight = 45;

        var bg = go.AddComponent<Image>();
        bg.color = new Color(0.25f, 0.1f, 0.1f);

        var btn = go.AddComponent<Button>();
        int captured = index;
        btn.onClick.AddListener(() => {
            if (HeroManager.Instance != null) HeroManager.Instance.CastAbility(captured);
        });
        ColorBlock cb = btn.colors;
        cb.normalColor = Color.white;
        cb.highlightedColor = new Color(1.2f, 1.2f, 1.2f, 1f);
        cb.pressedColor = new Color(0.8f, 0.8f, 0.8f, 1f);
        cb.disabledColor = new Color(0.5f, 0.5f, 0.5f, 0.5f);
        btn.colors = cb;

        var txt = new GameObject("Text");
        txt.transform.SetParent(go.transform, false);
        var t = txt.AddComponent<Text>();
        t.text = label;
        t.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        t.alignment = TextAnchor.MiddleCenter;
        t.color = Color.white;
        t.fontSize = 15;
        var trt = txt.GetComponent<RectTransform>();
        trt.anchorMin = Vector2.zero;
        trt.anchorMax = Vector2.one;
        trt.offsetMin = Vector2.zero;
        trt.offsetMax = Vector2.zero;

        var cdGO = new GameObject("Cooldown");
        cdGO.transform.SetParent(go.transform, false);
        var cdImg = cdGO.AddComponent<Image>();
        cdImg.color = new Color(0f, 0f, 0f, 0.55f);
        cdImg.type = Image.Type.Filled;
        cdImg.fillMethod = Image.FillMethod.Horizontal;
        cdImg.fillOrigin = (int)Image.OriginHorizontal.Left;
        cdImg.fillAmount = 0f;
        cdImg.raycastTarget = false;
        var cdRT = cdGO.GetComponent<RectTransform>();
        cdRT.anchorMin = Vector2.zero;
        cdRT.anchorMax = Vector2.one;
        cdRT.offsetMin = Vector2.zero;
        cdRT.offsetMax = Vector2.zero;

        var lockGO = new GameObject("Lock");
        lockGO.transform.SetParent(go.transform, false);
        var lockImg = lockGO.AddComponent<Image>();
        lockImg.color = new Color(0f, 0f, 0f, 0.75f);
        lockImg.raycastTarget = false;
        var lockRT = lockGO.GetComponent<RectTransform>();
        lockRT.anchorMin = Vector2.zero;
        lockRT.anchorMax = Vector2.one;
        lockRT.offsetMin = Vector2.zero;
        lockRT.offsetMax = Vector2.zero;

        var lockTxt = new GameObject("LockText");
        lockTxt.transform.SetParent(lockGO.transform, false);
        var lt = lockTxt.AddComponent<Text>();
        lt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        lt.alignment = TextAnchor.MiddleCenter;
        lt.color = Color.white;
        lt.fontSize = 16;
        lt.fontStyle = FontStyle.Bold;
        var ltRT = lockTxt.GetComponent<RectTransform>();
        ltRT.anchorMin = Vector2.zero;
        ltRT.anchorMax = Vector2.one;
        ltRT.offsetMin = Vector2.zero;
        ltRT.offsetMax = Vector2.zero;

        return (btn, cdImg, lockGO, lt);
    }
```

- [ ] **Step 3: Branch Select/Deselect/RefreshButtons on Hero vs TowerData**

Replace the `Select` method (lines 169-178) with:

```csharp
    public void Select(GameObject selected)
    {
        if (_selectedTower == selected) return;
        Deselect();
        _selectedTower = selected;
        AddOutline();
        ShowRangeIndicator();
        _actionPanel.SetActive(true);

        bool isHero = selected.GetComponent<Hero>() != null;
        _towerLayoutRoot.SetActive(!isHero);
        _heroLayoutRoot.SetActive(isHero);

        RefreshButtons();
    }
```

Replace the `RefreshButtons` method (lines 403-428) with:

```csharp
    void RefreshButtons()
    {
        if (_selectedTower == null) return;

        Hero hero = _selectedTower.GetComponent<Hero>();
        if (hero != null)
        {
            RefreshHeroButtons(hero);
            return;
        }

        var data = _selectedTower.GetComponent<TowerData>();
        if (data == null) return;

        var sellTxt = _sellButton.GetComponentInChildren<Text>();
        sellTxt.text = $"Sell (${data.SellValue})";

        int[] levels = { data.upgradePath1Level, data.upgradePath2Level, data.upgradePath3Level };
        Button[] buttons = { _upgrade1Button, _upgrade2Button, _upgrade3Button };

        for (int i = 0; i < 3; i++)
        {
            bool available = TowerCosts.TryGetUpgrade(data.towerType, i, levels[i], out var info);
            bool canAfford = available && EconomyManager.Instance != null && EconomyManager.Instance.CanAfford(info.cost);
            bool hasPrefab = available && _upgradePrefabs.TryGetValue(info.resultType, out var prefab) && prefab != null;
            buttons[i].interactable = available && canAfford && hasPrefab;

            var txt = buttons[i].GetComponentInChildren<Text>();
            if (available)
                txt.text = $"Path {i + 1} (${info.cost})";
            else
                txt.text = $"Path {i + 1}";
        }
    }

    void RefreshHeroButtons(Hero hero)
    {
        _heroNameText.text = hero.heroType == "knight000" ? "Silent Knight" : hero.heroType;
        _heroLevelText.text = hero.level >= 10 ? "Level 10 (MAX)" : $"Level {hero.level}";

        if (hero.level >= 10)
        {
            _heroXpBarFill.rectTransform.anchorMax = new Vector2(1f, 1f);
        }
        else
        {
            int cur = hero.XpTowardNextLevel();
            int req = Mathf.Max(1, hero.XpRequiredForNextLevel());
            float ratio = Mathf.Clamp01(cur / (float)req);
            _heroXpBarFill.rectTransform.anchorMax = new Vector2(ratio, 1f);
        }

        _heroPassiveText.text = hero.passive != null
            ? $"{hero.passive.name}\n{hero.passive.description}"
            : "";

        UpdateHeroAbilityButton(hero, hero.active1, _heroActive1Button, _heroActive1Cooldown, _heroActive1Lock, _heroActive1LockText);
        UpdateHeroAbilityButton(hero, hero.active2, _heroActive2Button, _heroActive2Cooldown, _heroActive2Lock, _heroActive2LockText);

        var sellTxt = _heroSellButton.GetComponentInChildren<Text>();
        int sellValue = HeroData.GetSellValue(hero.heroType);
        sellTxt.text = $"Sell (${sellValue})";
    }

    void UpdateHeroAbilityButton(Hero hero, HeroAbility a, Button btn, Image cooldownFill, GameObject lockGO, Text lockTxt)
    {
        if (a == null)
        {
            btn.interactable = false;
            lockGO.SetActive(true);
            lockTxt.text = "—";
            cooldownFill.fillAmount = 0f;
            return;
        }

        var btnLabel = btn.GetComponentInChildren<Text>();
        btnLabel.text = a.name;

        bool unlocked = a.IsUnlocked(hero.level);
        lockGO.SetActive(!unlocked);
        lockTxt.text = unlocked ? "" : $"L{a.unlockLevel}";

        float remaining = a.CooldownRemaining();
        cooldownFill.fillAmount = a.cooldown > 0f ? Mathf.Clamp01(remaining / a.cooldown) : 0f;

        btn.interactable = unlocked && remaining <= 0f;
    }
```

- [ ] **Step 4: Refresh hero panel every frame while selected**

Add a call to `RefreshButtons` inside `Update` (after `HandleKeyboardShortcuts`) when a hero is selected, so cooldowns and XP update live. Find the existing `Update` method (line 92) and add at the top:

```csharp
        if (_selectedTower != null && _selectedTower.GetComponent<Hero>() != null)
            RefreshButtons();
```

- [ ] **Step 5: Hero-specific sell path**

Add a new `OnHeroSell` method next to `OnSell` (after line 450):

```csharp
    void OnHeroSell()
    {
        if (_selectedTower == null) return;
        Hero hero = _selectedTower.GetComponent<Hero>();
        if (hero == null) return;

        int refund = HeroData.GetSellValue(hero.heroType);
        Vector3 worldPos = hero.transform.position;

        if (HeroManager.Instance != null)
            HeroManager.Instance.UnregisterHero(hero);

        GameObject go = hero.gameObject;
        Deselect();

        if (refund > 0 && EconomyManager.Instance != null)
        {
            EconomyManager.Instance.money += refund;
            FloatingText.Spawn(worldPos, $"+${refund}", new Color(1f, 0.85f, 0.1f), 1.2f, 28, true, 80f);
        }

        Destroy(go);
    }
```

- [ ] **Step 6: Hero pickability — register TowerSelection click handling on heroes**

The existing click raycast in `Update` (lines 110-144) looks for `TowerData`. Add a parallel search for `Hero` so the knight is clickable. Replace the `RaycastAll` and fallback blocks (roughly lines 114-144) with:

```csharp
        TowerData foundTower = null;
        Hero foundHero = null;
        float bestDist = float.MaxValue;

        RaycastHit[] hits = Physics.RaycastAll(ray, 500f);
        foreach (var h in hits)
        {
            var data = h.collider.GetComponentInParent<TowerData>();
            var hero = h.collider.GetComponentInParent<Hero>();
            if (hero != null && h.distance < bestDist)
            {
                bestDist = h.distance;
                foundHero = hero;
                foundTower = null;
            }
            else if (data != null && h.distance < bestDist && foundHero == null)
            {
                bestDist = h.distance;
                foundTower = data;
            }
        }

        if (foundTower == null && foundHero == null)
        {
            Camera cam = Camera.main;
            float closestScreenDist = 50f;
            foreach (var td in FindObjectsByType<TowerData>(FindObjectsSortMode.None))
            {
                Vector3 screenPt = cam.WorldToScreenPoint(td.transform.position);
                if (screenPt.z < 0) continue;
                float dist = Vector2.Distance(mousePos, new Vector2(screenPt.x, screenPt.y));
                if (dist < closestScreenDist)
                {
                    closestScreenDist = dist;
                    foundTower = td;
                }
            }
            foreach (var h in FindObjectsByType<Hero>(FindObjectsSortMode.None))
            {
                Vector3 screenPt = cam.WorldToScreenPoint(h.transform.position);
                if (screenPt.z < 0) continue;
                float dist = Vector2.Distance(mousePos, new Vector2(screenPt.x, screenPt.y));
                if (dist < closestScreenDist)
                {
                    closestScreenDist = dist;
                    foundHero = h;
                    foundTower = null;
                }
            }
        }

        if (foundHero != null)
        {
            Select(foundHero.gameObject);
            return;
        }

        if (foundTower != null)
        {
            Select(foundTower.gameObject);
            return;
        }

        Deselect();
```

- [ ] **Step 7: Compile check + play-mode smoke test**

`mcp__UnityMCP__refresh_unity` then `read_console` filtered to errors. Expected: clean.

Enter play mode. Expected:
- Top ability bar is visible (from Task 12).
- Click the knight placeholder. Right-side panel switches to the hero layout: "Silent Knight" name, "Level 1" label, a thin yellow XP bar (~0% filled), passive text "Templar's Zeal — Nearby towers gain bonus attack rate.", two grey Active buttons with "L5" and "L10" lock overlays, "Sell ($750)" button at the bottom.
- Click a regular tower — panel switches back to upgrade layout. No remnants of the hero layout visible.
- Level up the knight via `execute_code`: `var h = Object.FindAnyObjectByType<Hero>(); h.AddXp(700);` — XP bar fills and "Level N" updates live.
- At L5, A1 unlocks in the panel and becomes clickable. Click it to cast Crimson Arc from the panel button.
- Click "Sell ($750)" — knight disappears, $750 added to money, top ability bar hides, shop knight button becomes clickable again.

Exit play mode.

- [ ] **Step 8: Commit**

```bash
git add Assets/Scripts/TowerSelection.cs
git commit -m "feat(heroes): hero layout in selection panel (portrait, XP, abilities, sell)"
```

---

## Self-review checklist (completed during plan authoring)

- **Spec coverage:** All Framework.md and Silent Knight.md sections map to tasks.
  - Pillars (static/invincible, one-per-match, 10 levels, 4 slots, flat cost, two UI surfaces) → Tasks 6, 7, 12, 13.
  - Code architecture (Hero.cs, HeroAbility.cs, HeroData.cs, HeroManager.cs, JudgedEffect.cs) → Tasks 3, 4, 5, 6, 7, 8, 12.
  - Edits (RoundManager, TowerPlacer, TowerSelection, Movement) → Tasks 1, 3, 9, 13.
  - Silent Knight identity (knight000, $1500, range 3.5, strongest target) → Tasks 5, 6, 9.
  - Auto-attack (homing sword, 5 dmg, 0.8s cd) → Task 6.
  - Passive Templar's Zeal (+10%→+28%, 4-unit radius) → Task 8.
  - Crimson Arc (25 dmg, 360°, 12s cd, L5) → Task 10.
  - Templar's Book (3s channel, 5 dps, range 8, Judged 25% for 10s, 60s cd, L10) → Tasks 3 (Judged), 11 (channel).
- **Placeholder scan:** XP curve and cost are labeled PLACEHOLDER in HeroData with a tuning note. FBX asset swap is a noted follow-up. No "TBD"/"TODO" in code.
- **Type consistency:** `Hero` public surface (`heroType`, `level`, `xp`, `range`, `AddXp`, `CastAbility`, `SetChanneling`, `XpTowardNextLevel`, `XpRequiredForNextLevel`, `ActiveHero` on manager) is stable across tasks 6, 7, 8, 10, 11, 12, 13.
- **Deferred items (intentional):** Hotkeys, hero variants beyond the knight, multiplayer pre-match pick, death/revive, starting level in mid-match placement — all called out in Framework.md "Open items deferred" and not part of this plan.

---

## Follow-ups (out of scope for this plan)

- **FBX model swap.** Replace the primitive knight prefab with the actual knight2 FBX once it is finalized. The hero framework does not care what the prefab looks like.
- **Hero portrait + ability icons.** Drop real sprites into `Assets/Resources/UI/knight_icon.png`, `knight_zeal_icon.png`, `knight_arc_icon.png`, `knight_book_icon.png`. Until then, the UI falls back to solid-colour squares.
- **Hotkey layer.** `TowerSelection.HandleKeyboardShortcuts` already extends cleanly — add an `else if (kb.qKey.wasPressedThisFrame) HeroManager.Instance.CastAbility(0);`-style branch when desired.
- **Second hero.** `HeroData`, `TowerPlacer._prefabs`, `TowerPlacer._placementSetup`, and the shop panel are extensible. Adding a second hero is mostly asset + new `XxxSetup` static class.
