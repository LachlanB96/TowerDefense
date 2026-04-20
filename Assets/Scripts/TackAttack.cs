using UnityEngine;

public class TackAttack : MonoBehaviour, ITowerAttack
{
    public float range = 3f;
    public float cooldown = 0.5f;
    public int damage = 1;
    public float projectileSpeed = 0.15f;
    public float diskFlySpeed = 15f;
    public Color diskColor = new Color(0.76f, 0.6f, 0.42f);
    public float diskMetallic = 0f;
    public float diskSmoothness = 0.2f;
    public int pierce = 1;
    public float attackSpeedMultiplier = 1f;

    public ITackFireStrategy strategy;

    public float Range => range;

    private float _lastAttackTime = -999f;
    private SquashStretch _squash;

    void Start()
    {
        _squash = GetComponent<SquashStretch>();
        if (_squash == null) _squash = gameObject.AddComponent<SquashStretch>();

        foreach (Transform child in transform)
        {
            string n = child.name;
            if (n.StartsWith("TackHead") || n.StartsWith("TackShaft") || n.StartsWith("TackTip")
                || n.StartsWith("_TackRing") || n.StartsWith("_Range")
                || n.StartsWith("_outline") || n.StartsWith("_Sniper")) continue;
            _squash.AddPart(child);
        }

        if (strategy == null) strategy = new DiskBurstStrategy();
        strategy.OnStart(this);
    }

    void Update()
    {
        if (Time.time - _lastAttackTime < cooldown / Mathf.Max(0.01f, attackSpeedMultiplier)) return;
        if (strategy.TryFire(this))
            _lastAttackTime = Time.time;
    }

    public void PlaySquash() => _squash?.Play();
}
