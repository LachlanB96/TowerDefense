using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public static class SilentKnightSetup
{
    const float ZealAuraRadius = 4f;
    const float BookRange = 8f;
    const float BookChannelDuration = 3f;
    const int BookTickDamage = 5;
    const float JudgedDuration = 10f;

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
            description = "360 sword sweep: 25 damage to every enemy in range.",
            unlockLevel = 5,
            cooldown = 12f,
            isPassive = false,
            callback = CrimsonArc,
        };

        hero.active2 = new HeroAbility
        {
            name = "The Templar's Book",
            iconPath = "UI/knight_book_icon",
            description = "Channel 3s: 5 dps in 8-unit range + Judged debuff (+25% dmg taken, 10s).",
            unlockLevel = 10,
            cooldown = 60f,
            isPassive = false,
            callback = TemplarsBook,
        };

        if (HeroManager.Instance != null)
            HeroManager.Instance.RegisterHero(hero);
    }

    public static float GetZealBonus(int level)
    {
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

    const int CrimsonArcDamage = 25;

    static void CrimsonArc(Hero hero)
    {
        UnitScanner.ForEachInRange(hero.transform.position, hero.range, (unit, m) =>
        {
            var report = m.Hit(CrimsonArcDamage);
            hero.Credit(report.damageDealt, report.killed);
        });

        hero.StartCoroutine(PlayCrimsonArcVisual(hero));
    }

    static IEnumerator PlayCrimsonArcVisual(Hero hero)
    {
        var slash = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        slash.name = "_CrimsonArc";
        Object.Destroy(slash.GetComponent<Collider>());
        slash.transform.SetParent(SceneContainers.Effects, false);
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

    static void TemplarsBook(Hero hero)
    {
        hero.StartCoroutine(ChannelTemplarsBook(hero));
    }

    static IEnumerator ChannelTemplarsBook(Hero hero)
    {
        hero.SetChanneling(true);

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
        UnitScanner.ForEachInRange(hero.transform.position, BookRange, (unit, m) =>
        {
            var report = m.Hit(BookTickDamage);
            hero.Credit(report.damageDealt, report.killed);
            if (unit == null) return;
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
        });
    }
}
