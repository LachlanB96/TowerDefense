// EditMode tests for the tower tables. A tower code lives in three places that have to be edited
// together (CLAUDE.md, "Towers"): TowerCosts (what's sold and for how much), TowerPlacer (base
// towers: prefab + setup action) and TowerSelection (upgrades: prefab + setup action). These
// tests fail when they drift apart, which in the game shows up only as a greyed-out button.
//
// The game scripts compile into Assembly-CSharp, and an assembly definition can't reference that,
// so everything here reaches the game code through reflection by type and member name. A rename
// in the game code therefore fails a test with "not found" instead of quietly skipping a check.
//
// Run by check.ps1 (Unity batch mode, -runTests -testPlatform EditMode), or from the editor's
// Test Runner window / UnityMCP's run_tests.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public class TowerTablesTests
{
    const string GameScene = "Assets/game.unity";
    const BindingFlags Any = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance;

    /// <summary>
    /// Upgrades TowerCosts sells whose prefab doesn't exist yet, each with why. The upgrade test
    /// fails if one of these gets its prefab (take it off the list) or a new gap appears.
    /// </summary>
    static readonly Dictionary<string, string> KnownMissingPrefabs = new()
    {
        { "tack200", "no tack200 model yet: Obsidian/TD/Towers/Tack/Path1.md has blender_tack200.py still to do, so the scene's tack200Prefab is empty and the Path 1 tier 2 button stays disabled" },
    };

    /// <summary>One sellable upgrade: TowerCosts._upgrades[From][Path, Level] with a cost above zero.</summary>
    struct Upgrade
    {
        public string From;
        public int Path;
        public int Level;
        public int Cost;
        public string Result;
        public override string ToString() => $"{From} path {Path + 1} level {Level} -> {Result} (${Cost})";
    }

    // A tower code is a name followed by three digits, one tier per path (CLAUDE.md, "Towers").
    static readonly Regex Code = new(@"^([a-z]+)([0-9])([0-9])([0-9])$");

    Scene _scene;
    bool _openedByTest;

    [OneTimeSetUp]
    public void OpenGameScene()
    {
        // Additive, so running these from an open editor doesn't throw away whatever scene is up.
        _scene = SceneManager.GetSceneByPath(GameScene);
        if (!_scene.isLoaded)
        {
            _scene = EditorSceneManager.OpenScene(GameScene, OpenSceneMode.Additive);
            _openedByTest = true;
        }
        Assert.IsTrue(_scene.isLoaded, $"couldn't open {GameScene}");
    }

    [OneTimeTearDown]
    public void CloseGameScene()
    {
        // Never saved: BuildTables() only fills private dictionaries, but nothing here should
        // ever reach the scene file.
        if (_openedByTest && _scene.isLoaded && SceneManager.sceneCount > 1)
            EditorSceneManager.CloseScene(_scene, true);
    }

    [Test]
    public void BaseTowersAreCostedAndHaveIcons()
    {
        var info = (IDictionary)StaticField(GameType("TowerCosts"), "_towerInfo");
        Assert.IsNotEmpty(info, "TowerCosts._towerInfo is empty");
        foreach (DictionaryEntry e in info)
        {
            string code = (string)e.Key;
            Assert.IsTrue(Code.IsMatch(code) && code.EndsWith("000"), $"{code}: a base tower's code ends in 000");
            Assert.Greater(FieldOf<int>(e.Value, "cost"), 0, $"{code}: cost");
            Assert.Greater(FieldOf<float>(e.Value, "range"), 0f, $"{code}: range");
            string icon = FieldOf<string>(e.Value, "iconPath");
            Assert.IsNotNull(Resources.Load(icon), $"{code}: icon Resources/{icon} doesn't load");
        }
    }

    [Test]
    public void UpgradeCodesFollowTheDigitConvention()
    {
        foreach (var u in Upgrades())
        {
            var from = Code.Match(u.From);
            var to = Code.Match(u.Result);
            Assert.IsTrue(from.Success, $"{u}: '{u.From}' isn't a tower code");
            Assert.IsTrue(to.Success, $"{u}: '{u.Result}' isn't a tower code");
            Assert.AreEqual(from.Groups[1].Value, to.Groups[1].Value, $"{u}: an upgrade stays the same tower");

            int tier = Digit(from, u.Path);
            Assert.AreEqual(tier, u.Level, $"{u}: the level index is the tier the tower is on in that path");
            for (int p = 0; p < 3; p++)
                Assert.AreEqual(p == u.Path ? tier + 1 : Digit(from, p), Digit(to, p),
                    $"{u}: only path {u.Path + 1}'s digit goes up, by one");
        }
    }

    [Test]
    public void EveryUpgradeStartsFromATowerYouCanHave()
    {
        var reachable = new HashSet<string>(BaseTowers());
        foreach (var u in Upgrades()) reachable.Add(u.Result);
        foreach (var u in Upgrades())
            Assert.IsTrue(reachable.Contains(u.From), $"{u}: nothing places or upgrades into {u.From}");
    }

    [Test]
    public void BaseTowersHaveAPrefabAndASetupAction()
    {
        var placer = SceneComponent("TowerPlacer");
        Invoke(placer, "BuildTables");
        var prefabs = (IDictionary)InstanceField(placer, "_prefabs");
        var setup = (IDictionary)InstanceField(placer, "_placementSetup");

        foreach (string code in BaseTowers())
        {
            Assert.IsTrue(prefabs.Contains(code), $"{code}: no entry in TowerPlacer._prefabs");
            Assert.IsTrue(prefabs[code] as GameObject != null, $"{code}: its prefab field is empty in {GameScene}");
            Assert.IsTrue(setup.Contains(code), $"{code}: no entry in TowerPlacer._placementSetup");
        }
    }

    [Test]
    public void UpgradesHaveAPrefabAndASetupAction()
    {
        var selection = SceneComponent("TowerSelection");
        var args = new object[2];   // the two out parameters
        Invoke(selection, "BuildUpgradeTables", args);
        var prefabs = (IDictionary)args[0];
        var setup = (IDictionary)args[1];

        var sold = Upgrades().Select(u => u.Result).Distinct().ToList();
        var missing = new List<string>();
        foreach (string code in sold)
        {
            Assert.IsTrue(setup.Contains(code), $"{code}: no entry in TowerSelection's upgrade setup");
            Assert.IsTrue(prefabs.Contains(code), $"{code}: no entry in TowerSelection's upgrade prefabs");
            if (prefabs[code] as GameObject == null) missing.Add(code);
        }

        foreach (string code in missing)
            Assert.IsTrue(KnownMissingPrefabs.ContainsKey(code),
                $"{code}: TowerCosts sells it but its prefab field is empty in {GameScene}, so the upgrade button never enables");
        foreach (var known in KnownMissingPrefabs)
            Assert.IsTrue(missing.Contains(known.Key),
                $"{known.Key} is listed as missing its prefab ({known.Value}) but has one now, or isn't sold: take it off KnownMissingPrefabs");
    }

    // ── reflection helpers ─────────────────────────────────────

    static Type GameType(string name)
    {
        var t = Type.GetType(name + ", Assembly-CSharp");
        Assert.IsNotNull(t, $"type {name} not found in Assembly-CSharp");
        return t;
    }

    static object StaticField(Type t, string name)
    {
        var f = t.GetField(name, Any);
        Assert.IsNotNull(f, $"{t.Name}.{name} not found");
        return f.GetValue(null);
    }

    static object InstanceField(object o, string name)
    {
        var f = o.GetType().GetField(name, Any);
        Assert.IsNotNull(f, $"{o.GetType().Name}.{name} not found");
        return f.GetValue(o);
    }

    static T FieldOf<T>(object boxed, string name) => (T)InstanceField(boxed, name);

    static void Invoke(object o, string method, object[] args = null)
    {
        var m = o.GetType().GetMethod(method, Any);
        Assert.IsNotNull(m, $"{o.GetType().Name}.{method}() not found");
        m.Invoke(o, args);
    }

    static int Digit(Match code, int path) => code.Groups[2 + path].Value[0] - '0';

    static List<string> BaseTowers() =>
        ((IDictionary)StaticField(GameType("TowerCosts"), "_towerInfo")).Keys.Cast<string>().ToList();

    static List<Upgrade> Upgrades()
    {
        var table = (IDictionary)StaticField(GameType("TowerCosts"), "_upgrades");
        var list = new List<Upgrade>();
        foreach (DictionaryEntry e in table)
        {
            var grid = (Array)e.Value;   // UpgradeInfo[path, level]
            for (int p = 0; p < grid.GetLength(0); p++)
                for (int l = 0; l < grid.GetLength(1); l++)
                {
                    object info = grid.GetValue(p, l);
                    int cost = FieldOf<int>(info, "cost");
                    if (cost > 0)   // zero cost means "not upgradeable here" (TowerCosts.TryGetUpgrade)
                        list.Add(new Upgrade { From = (string)e.Key, Path = p, Level = l, Cost = cost, Result = FieldOf<string>(info, "resultType") });
                }
        }
        Assert.IsNotEmpty(list, "TowerCosts._upgrades sells nothing");
        return list;
    }

    Component SceneComponent(string typeName)
    {
        var type = GameType(typeName);
        var found = _scene.GetRootGameObjects()
            .SelectMany(root => root.GetComponentsInChildren(type, true))
            .ToList();
        Assert.AreEqual(1, found.Count, $"{GameScene} should hold exactly one {typeName}");
        return found[0];
    }
}
