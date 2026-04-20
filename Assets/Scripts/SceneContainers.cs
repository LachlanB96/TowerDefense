using UnityEngine;

public static class SceneContainers
{
    private static Transform _units;
    private static Transform _projectiles;
    private static Transform _effects;

    public static Transform Units => _units != null ? _units : (_units = GetOrCreate("_Units"));
    public static Transform Projectiles => _projectiles != null ? _projectiles : (_projectiles = GetOrCreate("_Projectiles"));
    public static Transform Effects => _effects != null ? _effects : (_effects = GetOrCreate("_Effects"));

    static Transform GetOrCreate(string name)
    {
        var existing = GameObject.Find(name);
        if (existing != null) return existing.transform;
        return new GameObject(name).transform;
    }
}
