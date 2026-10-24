// EditMode tests for the tower tables. A tower code lives in three places that have to be edited
// together (CLAUDE.md, "Towers"): TowerCosts (what's sold and for how much), TowerPlacer (base
// towers: prefab + setup action) and TowerSelection (upgrades: prefab + setup action). These
// tests fail when they drift apart, which in the game shows up only as a greyed-out button.
//
// The game scripts compile into Assembly-CSharp, and an assembly definition can't reference that,
// so everything here reaches the game code through reflection by type and member name. A rename
// in the game code therefore fails a test with "not found" instead of quietly skipping a check.
//
// The prefab fields come from game.unity as the scene file holds them (its YAML), not from opening
// the scene. In batch mode the scene's script references sometimes fail to bind to their classes
// (MonoScript.GetClass() comes back null, every behaviour loads as a missing script; seen on
// 2026-10-24 after the check's shared Library cache moved between worktrees), which would fail
// these tests for a reason that has nothing to do with the game. The file needs no binding.
//
// Run by check.ps1 (Unity batch mode, -runTests -testPlatform EditMode), or from the editor's
// Test Runner window / UnityMCP's run_tests.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.Serialization;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;

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
        var placer = FromScene("TowerPlacer");
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
        var selection = FromScene("TowerSelection");
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

    // ── the scene's behaviours, from game.unity's YAML ──────────

    /// <summary>
    /// The scene's one <paramref name="typeName"/> as a bare instance of its class, with its
    /// GameObject fields set from what game.unity holds. Only managed code runs on it (the
    /// Build*Tables methods fill dictionaries and make lambdas), so it needs no native object.
    /// </summary>
    static object FromScene(string typeName)
    {
        var type = GameType(typeName);
        var fields = SceneBehaviourFields(typeName);
        var obj = FormatterServices.GetUninitializedObject(type);
        foreach (var f in type.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
            if (f.FieldType == typeof(GameObject) && fields.TryGetValue(f.Name, out var value))
                f.SetValue(obj, LoadReference(value));
        return obj;
    }

    /// <summary>
    /// The top-level fields of the one MonoBehaviour in game.unity whose m_Script is the
    /// script for <paramref name="typeName"/>, as raw YAML values ("{fileID: ..., guid: ..., type: 3}").
    /// </summary>
    static Dictionary<string, string> SceneBehaviourFields(string typeName)
    {
        string script = AssetDatabase.FindAssets($"t:MonoScript {typeName}")
            .Select(AssetDatabase.GUIDToAssetPath)
            .FirstOrDefault(p => Path.GetFileNameWithoutExtension(p) == typeName);
        Assert.IsNotNull(script, $"no script asset named {typeName}.cs");
        string guid = AssetDatabase.AssetPathToGUID(script);

        // A scene file is a run of YAML documents, each "--- !u!<classID> &<fileID>"; 114 is a MonoBehaviour.
        string text = File.ReadAllText(GameScene).Replace("\r\n", "\n");
        var matches = text.Split(new[] { "\n--- !u!" }, StringSplitOptions.None)
            .Where(doc => doc.StartsWith("114 ") && doc.Contains($"m_Script: {{fileID: 11500000, guid: {guid},"))
            .ToList();
        Assert.AreEqual(1, matches.Count, $"{GameScene} should hold exactly one {typeName}");

        var fields = new Dictionary<string, string>();
        foreach (Match m in Regex.Matches(matches[0], @"^  ([A-Za-z_]\w*): (.*)$", RegexOptions.Multiline))
            fields[m.Groups[1].Value] = m.Groups[2].Value.Trim();
        return fields;
    }

    /// <summary>The prefab a "{fileID: N, guid: G, type: 3}" reference points at, or null for an empty field.</summary>
    static GameObject LoadReference(string yaml)
    {
        var guid = Regex.Match(yaml, @"guid:\s*([0-9a-f]{32})");
        if (!guid.Success) return null;   // {fileID: 0}: nothing assigned
        return AssetDatabase.LoadAssetAtPath<GameObject>(AssetDatabase.GUIDToAssetPath(guid.Groups[1].Value));
    }
}
