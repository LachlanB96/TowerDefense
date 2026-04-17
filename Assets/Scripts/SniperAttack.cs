using System.Collections;
using UnityEngine;

public class SniperAttack : MonoBehaviour, ITowerAttack
{
    public float range = 7f;
    public float cooldown = 2f;
    public int damage = 3;
    public float bulletSpeed = 30f;
    public int pierce = 2;
    public Color bulletColor = new Color(0.18f, 0.18f, 0.22f);

    public float Range => range;

    private float lastAttackTime = -999f;
    private Material bulletMaterial;
    private SquashStretch _squash;
    private SniperIdle _idle;

    void Start()
    {
        _idle = GetComponent<SniperIdle>();

        _squash = GetComponent<SquashStretch>();
        if (_squash == null) _squash = gameObject.AddComponent<SquashStretch>();
        _squash.squashScale = new Vector3(1.12f, 0.85f, 1.12f);
        _squash.squashDuration = 0.06f;
        _squash.stretchScale = new Vector3(0.96f, 1.04f, 0.96f);
        _squash.stretchDuration = 0.12f;
        _squash.settleDuration = 0.10f;

        foreach (Transform child in transform)
        {
            string n = child.name;
            if (n.StartsWith("Sniper") || n.StartsWith("Scope") || n.StartsWith("_"))
                continue;
            _squash.AddPart(child);
        }

        bulletMaterial = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        bulletMaterial.SetColor("_BaseColor", bulletColor);
        bulletMaterial.SetFloat("_Metallic", 0.9f);
        bulletMaterial.SetFloat("_Smoothness", 0.4f);
    }

    void Update()
    {
        if (Time.time - lastAttackTime < cooldown) return;

        Transform units = Spawn.UnitsParent;
        if (units == null) return;

        // Find the first enemy on the path (furthest along) within range
        Transform target = null;
        float bestProgress = -1f;
        foreach (Transform unit in units)
        {
            float dist = Vector3.Distance(transform.position, unit.position);
            if (dist > range) continue;

            var movement = unit.GetComponent<Movement>();
            if (movement == null || !movement.enabled) continue;

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

        if (_idle != null)
            _idle.AimAt(target.position);

        _squash.Play();

        Vector3 dir = (target.position - transform.position).normalized;
        dir.y = 0f;
        dir.Normalize();

        GameObject bullet = CreateBullet();
        bullet.transform.position = transform.position + dir * 0.5f + Vector3.up * 1.05f;
        bullet.transform.rotation = Quaternion.LookRotation(dir);
        TowerUtils.SetProjectileLayer(bullet);

        Velocity vel = bullet.AddComponent<Velocity>();
        vel.direction = dir;
        vel.speed = bulletSpeed;
        vel.damage = damage;
        vel.pierce = pierce;
        vel.maxRange = range + 2f;
        vel.hitRadius = 0.4f;
    }

    GameObject CreateBullet()
    {
        var bullet = new GameObject("SniperBullet");

        var core = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        core.name = "_core";
        Destroy(core.GetComponent<Collider>());
        core.transform.SetParent(bullet.transform, false);
        core.transform.localScale = new Vector3(0.08f, 0.08f, 0.2f);
        core.GetComponent<Renderer>().sharedMaterial = bulletMaterial;

        var flash = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        flash.name = "_flash";
        Destroy(flash.GetComponent<Collider>());
        flash.transform.SetParent(bullet.transform, false);
        flash.transform.localScale = Vector3.one * 0.15f;

        var flashMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        flashMat.SetColor("_BaseColor", new Color(1f, 0.9f, 0.5f));
        flash.GetComponent<Renderer>().material = flashMat;

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
