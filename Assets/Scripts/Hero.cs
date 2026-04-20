using System;
using UnityEngine;

public class Hero : MonoBehaviour, ITowerAttack, IDamageCredit
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

    [Header("Stats")]
    public int killCount = 0;
    public int totalDamage = 0;

    [Header("Ability slots")]
    public HeroAbility passive;
    public HeroAbility active1;
    public HeroAbility active2;

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
        if (passive != null && passive.isPassive && passive.IsUnlocked(level))
            passive.callback?.Invoke(this);

        if (IsChanneling) return;
        if (Time.time - _lastAttackTime < attackCooldown) return;

        Transform target = UnitScanner.StrongestInRange(transform.position, range);
        if (target != null)
            ShootSword(target);
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
        vel.source = this;
    }

    public void SetChanneling(bool value) => IsChanneling = value;

    public void Credit(int damageDealt, bool killed)
    {
        totalDamage += damageDealt;
        if (killed) killCount++;
    }

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
