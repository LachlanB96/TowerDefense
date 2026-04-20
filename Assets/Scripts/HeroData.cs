using System.Collections.Generic;

public static class HeroData
{
    public struct HeroInfo
    {
        public int cost;
        public string iconPath;
        public float range;
        public int[] xpToReachLevel;
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

    // PLACEHOLDER XP curve — tune via playtesting.
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

    public static int GetXpToReachLevel(string heroType, int level)
    {
        if (!_heroInfo.TryGetValue(heroType, out var info)) return int.MaxValue;
        int idx = level - 1;
        if (idx < 0 || idx >= info.xpToReachLevel.Length) return int.MaxValue;
        return info.xpToReachLevel[idx];
    }

    public static int GetXpForRound(int round) => round * 15;
}
