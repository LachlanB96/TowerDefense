using System;

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
