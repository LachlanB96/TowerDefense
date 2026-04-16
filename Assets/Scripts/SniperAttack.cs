using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class SniperAttack : MonoBehaviour
{
    public float range = 7f;
    public float cooldown = 2f;
    public int damage = 3;
    public float bulletSpeed = 30f;
    public int pierce = 2;
    public Color bulletColor = new Color(0.18f, 0.18f, 0.22f);

    private float lastAttackTime = -999f;
    private Transform unitsParent;
    private Material bulletMaterial;
    private List<Transform> _bodyParts = new List<Transform>();
    private List<Vector3> _bodyOriginalScales = new List<Vector3>();
    private Coroutine _recoilRoutine;
    private SniperIdle _idle;

    void Start()
    {
        _idle = GetComponent<SniperIdle>();

        // Collect body parts for squash animation (exclude barrel parts handled by SniperIdle)
        foreach (Transform child in transform)
        {
            string n = child.name;
            if (n.StartsWith("Sniper") || n.StartsWith("Scope") || n.StartsWith("_"))
                continue;
            _bodyParts.Add(child);
            _bodyOriginalScales.Add(child.localScale);
        }

        Spawn spawner = FindAnyObjectByType<Spawn>();
        if (spawner != null)
            unitsParent = spawner.transform;

        // Bullet material - dark metallic
        bulletMaterial = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        bulletMaterial.SetColor("_BaseColor", bulletColor);
        bulletMaterial.SetFloat("_Metallic", 0.9f);
        bulletMaterial.SetFloat("_Smoothness", 0.4f);
    }

    void Update()
    {
        if (Time.time - lastAttackTime < cooldown) return;

        if (unitsParent == null)
        {
            Spawn spawner = FindAnyObjectByType<Spawn>();
            if (spawner != null) unitsParent = spawner.transform;
            if (unitsParent == null) return;
        }

        // Find the first enemy on the path (furthest along) within range
        Transform target = null;
        float bestProgress = -1f;
        foreach (Transform unit in unitsParent)
        {
            float dist = Vector3.Distance(transform.position, unit.position);
            if (dist > range) continue;

            var movement = unit.GetComponent<Movement>();
            if (movement == null || !movement.enabled) continue;

            // Use sibling index as a proxy for path progress (earlier spawned = further along)
            // Units further along the path have lower sibling index
            float progress = unit.GetSiblingIndex();
            if (target == null || progress < bestProgress)
            {
                bestProgress = progress;
                target = unit;
            }
        }

        if (target != null)
            Shoot(target);
    }

    void Shoot(Transform target)
    {
        lastAttackTime = Time.time;

        // Aim turret at target
        if (_idle != null)
            _idle.AimAt(target.position);

        // Recoil + squash animation
        if (_recoilRoutine != null)
            StopCoroutine(_recoilRoutine);
        _recoilRoutine = StartCoroutine(ShootRecoil());

        // Fire a single bullet toward the target
        Vector3 dir = (target.position - transform.position).normalized;
        dir.y = 0f;
        dir.Normalize();

        GameObject bullet = CreateBullet();
        // Spawn bullet slightly in front of the tower
        bullet.transform.position = transform.position + dir * 0.5f + Vector3.up * 1.05f;
        bullet.transform.rotation = Quaternion.LookRotation(dir);
        SetProjectileLayer(bullet);

        Velocity vel = bullet.AddComponent<Velocity>();
        vel.direction = dir;
        vel.speed = bulletSpeed;
        vel.damage = damage;
        vel.pierce = pierce;
        vel.maxRange = range + 2f;
        vel.hitRadius = 0.4f;
    }

    static void SetProjectileLayer(GameObject go)
    {
        int layer = LayerMask.NameToLayer("Projectiles");
        if (layer < 0) return;
        go.layer = layer;
        foreach (Transform child in go.transform)
            child.gameObject.layer = layer;
    }

    IEnumerator ShootRecoil()
    {
        // Phase 1: Squash body (wider + shorter) - the kick
        yield return ScaleBodyTo(new Vector3(1.12f, 0.85f, 1.12f), 0.06f);
        // Phase 2: Overshoot stretch
        yield return ScaleBodyTo(new Vector3(0.96f, 1.04f, 0.96f), 0.12f);
        // Phase 3: Settle
        yield return ScaleBodyTo(Vector3.one, 0.10f);
        _recoilRoutine = null;
    }

    IEnumerator ScaleBodyTo(Vector3 scaleMultiplier, float duration)
    {
        Vector3[] startScales = new Vector3[_bodyParts.Count];
        for (int i = 0; i < _bodyParts.Count; i++)
            startScales[i] = _bodyParts[i] != null ? _bodyParts[i].localScale : _bodyOriginalScales[i];

        Vector3[] targetScales = new Vector3[_bodyParts.Count];
        for (int i = 0; i < _bodyParts.Count; i++)
            targetScales[i] = Vector3.Scale(_bodyOriginalScales[i], scaleMultiplier);

        float elapsed = 0f;
        while (elapsed < duration)
        {
            elapsed += Time.deltaTime;
            float t = Mathf.SmoothStep(0f, 1f, elapsed / duration);
            for (int i = 0; i < _bodyParts.Count; i++)
            {
                if (_bodyParts[i] == null) continue;
                _bodyParts[i].localScale = Vector3.LerpUnclamped(startScales[i], targetScales[i], t);
            }
            yield return null;
        }

        for (int i = 0; i < _bodyParts.Count; i++)
        {
            if (_bodyParts[i] != null)
                _bodyParts[i].localScale = targetScales[i];
        }
    }

    GameObject CreateBullet()
    {
        // Elongated capsule-like bullet
        var bullet = new GameObject("SniperBullet");

        // Core - stretched sphere
        var core = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        core.name = "_core";
        Destroy(core.GetComponent<Collider>());
        core.transform.SetParent(bullet.transform, false);
        core.transform.localScale = new Vector3(0.08f, 0.08f, 0.2f);
        core.GetComponent<Renderer>().sharedMaterial = bulletMaterial;

        // Muzzle flash (brief bright sphere at spawn - fades via Velocity lifetime)
        var flash = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        flash.name = "_flash";
        Destroy(flash.GetComponent<Collider>());
        flash.transform.SetParent(bullet.transform, false);
        flash.transform.localScale = Vector3.one * 0.15f;

        var flashMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        flashMat.SetColor("_BaseColor", new Color(1f, 0.9f, 0.5f));
        flash.GetComponent<Renderer>().material = flashMat;

        // Flash fades quickly
        StartCoroutine(FadeFlash(flash));

        return bullet;
    }

    IEnumerator FadeFlash(GameObject flash)
    {
        float duration = 0.1f;
        float elapsed = 0f;
        while (elapsed < duration && flash != null)
        {
            elapsed += Time.deltaTime;
            float t = elapsed / duration;
            flash.transform.localScale = Vector3.one * 0.15f * (1f - t);
            yield return null;
        }
        if (flash != null)
            Destroy(flash);
    }
}
