using System.Collections.Generic;

public static class TowerCosts
{
    public struct TowerInfo
    {
        public int cost;
        public string iconPath;
        public float range;

        public TowerInfo(int cost, string iconPath, float range)
        {
            this.cost = cost;
            this.iconPath = iconPath;
            this.range = range;
        }
    }

    public struct UpgradeInfo
    {
        public int cost;
        public string resultType;

        public UpgradeInfo(int cost, string resultType)
        {
            this.cost = cost;
            this.resultType = resultType;
        }
    }

    // Tower base info: cost, icon, default range
    private static readonly Dictionary<string, TowerInfo> _towerInfo = new()
    {
        { "tack000", new TowerInfo(300, "UI/tack_icon", 3f) },
        { "sniper000", new TowerInfo(500, "UI/sniper_icon", 7f) },
    };

    // [towerType][path index][upgrade level] = UpgradeInfo
    private static readonly Dictionary<string, UpgradeInfo[,]> _upgrades = new()
    {
        {
            "tack000", new UpgradeInfo[,]
            {
                // Path 1: levels 0, 1, 2
                { new(500, "tack100"), new(0, ""), new(0, "") },
                // Path 2
                { new(400, "tack010"), new(0, ""), new(0, "") },
                // Path 3
                { new(350, "tack001"), new(0, ""), new(0, "") },
            }
        },
        {
            "tack100", new UpgradeInfo[,]
            {
                // Path 1: level 1 -> 2 upgrades to tack200
                { new(0, ""), new(900, "tack200"), new(0, "") },
                // Path 2 crosspath: not implemented
                { new(0, ""), new(0, ""), new(0, "") },
                // Path 3 crosspath: not implemented
                { new(0, ""), new(0, ""), new(0, "") },
            }
        },
    };

    public static int GetPlacementCost(string towerType)
    {
        return _towerInfo.TryGetValue(towerType, out var info) ? info.cost : 0;
    }

    public static string GetIconPath(string towerType)
    {
        return _towerInfo.TryGetValue(towerType, out var info) ? info.iconPath : null;
    }

    public static float GetRange(string towerType)
    {
        return _towerInfo.TryGetValue(towerType, out var info) ? info.range : 0f;
    }

    public static bool TryGetUpgrade(string towerType, int path, int currentLevel, out UpgradeInfo info)
    {
        info = default;
        if (!_upgrades.TryGetValue(towerType, out var table)) return false;
        if (path < 0 || path >= table.GetLength(0)) return false;
        if (currentLevel < 0 || currentLevel >= table.GetLength(1)) return false;

        info = table[path, currentLevel];
        return info.cost > 0;
    }

    public static int GetUpgradeCost(string towerType, int path, int currentLevel)
    {
        if (TryGetUpgrade(towerType, path, currentLevel, out var info))
            return info.cost;
        return 0;
    }
}
