using UnityEngine;

/// <summary>
/// Combat behaviour for Boat 000. Implements <see cref="ITowerAttack"/> so the tower
/// picker / upgrade system can query <see cref="Range"/>.
///
/// <para>Aiming model: the two cannons are rigidly fixed to the hull. To target an
/// enemy, the whole <c>Turret</c> child (which carries hull + masts + both cannons)
/// yaws around world-up until the <b>port</b> broadside (–right axis) lines up with
/// the target. When the angle is within <see cref="aimTolerance"/>, both cannons
/// fire simultaneously — port's ball goes at the enemy, starboard's ball goes the
/// opposite direction (a free side-effect of the broadside, never separately aimed).</para>
///
/// <para>Responsibilities: target selection, yaw, cooldown, spawning projectiles, and
/// kicking off animation/sfx. The actual visual reaction (recoil, smoke, mast impulse)
/// lives in <see cref="BoatAnimator.PlayShoot"/>.</para>
/// </summary>
public class BoatAttack : MonoBehaviour, ITowerAttack
{
    /// <summary>Targeting radius in world units (XZ). Enemies beyond this are ignored.</summary>
    public float range = 5.5f;

    /// <summary>Damage per cannonball (single shot). Per volley the boat fires two balls; only the port one typically hits.</summary>
    public int damage = 2;

    /// <summary>Pierce per cannonball — number of enemies a single ball can damage before despawning.</summary>
    public int pierce = 1;

    /// <summary>Seconds between volleys. Fires when the cooldown is ready AND the turret is within aimTolerance of the target.</summary>
    public float cooldown = 1.3f;

    /// <summary>World units per second the cannonball travels.</summary>
    public float projectileSpeed = 18f;

    /// <summary>Max turret yaw rate in degrees per second. Deliberately slow so the boat feels like a ship, not a laser turret.</summary>
    public float aimSpeed = 90f;

    /// <summary>Angular tolerance (degrees) between port broadside and target. Fire permitted only once the turret is inside this cone.</summary>
    public float aimTolerance = 15f;

    /// <summary>Cannonball prefab wired in <see cref="TowerPlacer"/>. Must have a <see cref="Velocity"/> component.</summary>
    public GameObject projectilePrefab;

    public float Range => range;

    // Cached hierarchy refs: all combat-relevant parts live under Turret so the
    // entire rigid top of the boat yaws as one piece. If the prefab loses its
    // Turret wrapper we fall back to transform so the component still functions.
    private Transform _turret, _cannonL, _cannonR;

    // Real-time countdown — decremented every Update, fire permitted at or below 0.
    private float _cdTimer;

    private SquashStretch _squash;
    private BoatAnimator _animator;
    // TowerData carries the kill / damage tallies. Every projectile this tower spawns
    // is credited back here via IDamageCredit so the game UI and sell-value math stay correct.
    private TowerData _towerData;

    void Start()
    {
        _turret  = transform.Find("Turret");
        if (_turret == null) _turret = transform;
        _cannonL = _turret.Find("CannonPort_L");
        _cannonR = _turret.Find("CannonPort_R");
        _animator = GetComponent<BoatAnimator>();
        _towerData = GetComponent<TowerData>();

        // Per-tower SquashStretch registration pattern (mirrors TackAttack.Start):
        // we add the component if missing, then enumerate direct children of the turret
        // and exclude things that shouldn't pump with the hull. Cannons stay rigid so
        // their recoil animation isn't stomped; sails and flag move via blendshapes so
        // scale-pulsing them would fight the cloth animation.
        _squash = GetComponent<SquashStretch>();
        if (_squash == null) _squash = gameObject.AddComponent<SquashStretch>();
        foreach (Transform child in _turret)
        {
            string n = child.name;
            if (n.StartsWith("CannonPort_L") || n.StartsWith("CannonPort_R")
                || n.StartsWith("SailFore") || n.StartsWith("SailMain") || n.StartsWith("Flag"))
                continue;
            _squash.AddPart(child);
        }

        _cdTimer = 0f;
    }

    void Update()
    {
        _cdTimer -= Time.deltaTime;

        Transform target = FindClosestEnemy();
        if (target == null) return;

        // Flatten to XZ before computing the aim vector — we only yaw around world-up,
        // so vertical differences from the enemy's head height etc. would just jitter the rotation.
        Vector3 d = target.position - _turret.position;
        d.y = 0f;
        if (d.sqrMagnitude < 0.0001f) return;
        Vector3 toTarget = d.normalized;

        // We want `-_turret.right` (port broadside) aligned with `toTarget`.
        // Equivalently, `_turret.forward` must point along `Cross(up, toTarget)` so that
        // the turret's local -X axis comes out at the target. LookRotation builds the
        // rotation whose forward matches that vector and whose up stays world-up.
        Vector3 desiredForward = Vector3.Cross(Vector3.up, toTarget);
        if (desiredForward.sqrMagnitude < 0.0001f) return;
        Quaternion targetRot = Quaternion.LookRotation(desiredForward, Vector3.up);

        // RotateTowards caps the step by aimSpeed*dt — produces a smooth slow yaw
        // regardless of how far the target jumped since last frame.
        _turret.rotation = Quaternion.RotateTowards(_turret.rotation, targetRot, aimSpeed * Time.deltaTime);

        // Only fire when cooldown is ready AND port is roughly on target. This
        // prevents wild shots mid-yaw and sells the "lining up the broadside" feel.
        if (_cdTimer <= 0f && Vector3.Angle(-_turret.right, toTarget) < aimTolerance)
            Fire();
    }

    private void Fire()
    {
        // Port shot goes at the target; starboard shot goes the opposite direction,
        // intentionally unaimed — it's the natural side-effect of a broadside volley.
        SpawnBall(_cannonL.position, -_turret.right);
        SpawnBall(_cannonR.position,  _turret.right);

        _squash.Play();
        if (_animator != null) _animator.PlayShoot();

        // ±5% pitch jitter on the fire SFX avoids audible repetition across consecutive volleys.
        SfxPlayer.PlayOneShot("SFX/boat_fire", transform.position, 0.85f, 0.05f);

        _cdTimer = cooldown;
    }

    private void SpawnBall(Vector3 pos, Vector3 dir)
    {
        if (projectilePrefab == null) return;

        // LookRotation on the spawned ball makes the TrailRenderer orient along the flight
        // path so the tracer visually trails behind the ball correctly.
        var ball = Instantiate(projectilePrefab, pos, Quaternion.LookRotation(dir));

        var v = ball.GetComponent<Velocity>();
        if (v == null) v = ball.AddComponent<Velocity>();
        v.direction = dir;
        v.speed = projectileSpeed;
        v.damage = damage;
        v.pierce = pierce;
        // `maxRange` on Velocity.cs is the projectile's travel limit before auto-destroy.
        // +1f beyond tower range gives a small grace margin so balls flying near the edge
        // don't despawn mid-flight before reaching an enemy at the boundary.
        v.maxRange = range + 1f;
        // Credit back to TowerData so kill/damage tallies show up — same pattern as
        // SniperAttack / TackStrategies. Without this, boat stats stay at zero.
        v.source = _towerData;
    }

    /// <summary>
    /// Closest-enemy targeting in XZ, iterating <see cref="Spawn.UnitsParent"/> — the
    /// canonical list of live enemies in this project. Returns null when nothing is in range.
    /// </summary>
    private Transform FindClosestEnemy()
    {
        if (Spawn.UnitsParent == null) return null;
        Transform best = null;
        float bestSq = range * range;
        Vector3 origin = _turret.position;
        foreach (Transform e in Spawn.UnitsParent)
        {
            Vector3 d = e.position - origin;
            d.y = 0f;
            float sq = d.sqrMagnitude;
            if (sq < bestSq) { bestSq = sq; best = e; }
        }
        return best;
    }
}
