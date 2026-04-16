using System.Collections.Generic;

public static class TowerCosts
{
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

    // upgrades[towerType][path (0-2)][level (0-2)]
    private static readonly Dictionary<string, int> _placementCosts = new()
    {
        { "tack000", 300 },
        { "sniper000", 500 },
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
    };

    public static int GetPlacementCost(string towerType)
    {
        return _placementCosts.TryGetValue(towerType, out int cost) ? cost : 0;
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
