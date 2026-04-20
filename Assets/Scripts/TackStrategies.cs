using System.Collections;
using UnityEngine;

public abstract class ProjectileBurstStrategy : ITackFireStrategy
{
    protected Material _projectileMaterial;

    protected abstract int Count { get; }
    protected abstract float StartAngle { get; }
    protected abstract bool ProjectileApplyBurn { get; }
    protected abstract GameObject CreateProjectile();

    public virtual void OnStart(TackAttack tack)
    {
        Renderer r = tack.GetComponentInChildren<Renderer>();
        _projectileMaterial = r != null && r.sharedMaterial != null
            ? new Material(r.sharedMaterial)
            : new Material(Shader.Find("Universal Render Pipeline/Lit"));

        _projectileMaterial.SetColor("_BaseColor", tack.diskColor);
        _projectileMaterial.SetFloat("_Metallic", tack.diskMetallic);
        _projectileMaterial.SetFloat("_Smoothness", tack.diskSmoothness);
    }

    public bool TryFire(TackAttack tack)
    {
        Transform target = UnitScanner.ClosestInRange(tack.transform.position, tack.range);
        if (target == null) return false;

        tack.PlaySquash();

        for (int i = 0; i < Count; i++)
        {
            float angle = StartAngle + i * (360f / Count);
            Vector3 dir = Quaternion.Euler(0, angle, 0) * Vector3.forward;

            GameObject proj = CreateProjectile();
            proj.transform.SetParent(SceneContainers.Projectiles, false);
            proj.transform.position = tack.transform.position;
            proj.transform.rotation = Quaternion.LookRotation(dir);
            TowerUtils.SetProjectileLayer(proj);

            var vel = proj.AddComponent<Velocity>();
            vel.direction = dir;
            vel.speed = tack.diskFlySpeed;
            vel.damage = tack.damage;
            vel.pierce = tack.pierce;
            vel.maxRange = tack.range + 1f;
            vel.applyBurn = ProjectileApplyBurn;
            vel.source = tack.GetComponent<TowerData>();
        }
        return true;
    }
}

public class DiskBurstStrategy : ProjectileBurstStrategy
{
    protected override int Count => 8;
    protected override float StartAngle => 0f;
    protected override bool ProjectileApplyBurn => false;

    protected override GameObject CreateProjectile()
    {
        GameObject disk = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        disk.name = "TackDisk";
        disk.transform.localScale = new Vector3(0.3f, 0.05f, 0.3f);
        disk.GetComponent<Renderer>().sharedMaterial = _projectileMaterial;
        Object.Destroy(disk.GetComponent<Collider>());
        return disk;
    }
}

public class FireballBurstStrategy : ProjectileBurstStrategy
{
    protected override int Count => 4;
    protected override float StartAngle => 45f;
    protected override bool ProjectileApplyBurn => true;

    protected override GameObject CreateProjectile()
    {
        var fireball = new GameObject("Fireball");

        var core = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        core.name = "_core";
        Object.Destroy(core.GetComponent<Collider>());
        core.transform.SetParent(fireball.transform, false);
        core.transform.localScale = Vector3.one * 0.25f;

        var coreMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        coreMat.SetColor("_BaseColor", new Color(1f, 0.85f, 0.2f));
        core.GetComponent<Renderer>().material = coreMat;

        var glow = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        glow.name = "_glow";
        Object.Destroy(glow.GetComponent<Collider>());
        glow.transform.SetParent(fireball.transform, false);
        glow.transform.localScale = Vector3.one * 0.4f;

        var glowMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        glowMat.SetColor("_BaseColor", new Color(1f, 0.35f, 0.0f, 0.5f));
        MaterialUtils.MakeTransparent(glowMat);
        glow.GetComponent<Renderer>().material = glowMat;

        return fireball;
    }
}

public class AirPuffBurstStrategy : ProjectileBurstStrategy
{
    protected override int Count => 8;
    protected override float StartAngle => 0f;
    protected override bool ProjectileApplyBurn => false;

    public override void OnStart(TackAttack tack)
    {
        _projectileMaterial = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        _projectileMaterial.SetColor("_BaseColor", tack.diskColor);
        MaterialUtils.MakeTransparent(_projectileMaterial);
    }

    protected override GameObject CreateProjectile()
    {
        GameObject puff = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        puff.name = "TackPuff";
        puff.transform.localScale = new Vector3(0.35f, 0.25f, 0.35f);
        puff.GetComponent<Renderer>().sharedMaterial = _projectileMaterial;
        Object.Destroy(puff.GetComponent<Collider>());
        return puff;
    }
}

public class AreaPulseStrategy : ITackFireStrategy
{
    public bool applyBurn = false;

    public void OnStart(TackAttack tack) { }

    public bool TryFire(TackAttack tack)
    {
        int hitCount = 0;
        bool anyHit = false;
        var data = tack.GetComponent<TowerData>();

        UnitScanner.ForEachInRange(tack.transform.position, tack.range, (unit, movement) =>
        {
            if (hitCount >= tack.pierce) return;

            if (!anyHit)
            {
                tack.PlaySquash();
                SpawnGroundPulse(tack);
                anyHit = true;
            }

            var report = movement.Hit(tack.damage);
            if (data != null)
                data.Credit(report.damageDealt, report.killed);
            if (applyBurn && unit.GetComponent<BurnEffect>() == null)
            {
                var burn = unit.gameObject.AddComponent<BurnEffect>();
                burn.source = data;
            }

            hitCount++;
        });
        return anyHit;
    }

    static void SpawnGroundPulse(TackAttack tack)
    {
        var pulse = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        pulse.name = "_AreaPulse";
        Object.Destroy(pulse.GetComponent<Collider>());
        pulse.transform.SetParent(SceneContainers.Effects, false);
        pulse.transform.position = tack.transform.position + Vector3.up * 0.02f;
        pulse.transform.localScale = new Vector3(0.1f, 0.02f, 0.1f);

        var mat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        mat.SetColor("_BaseColor", new Color(1f, 0.45f, 0.1f, 0.7f));
        MaterialUtils.MakeTransparent(mat);
        pulse.GetComponent<Renderer>().material = mat;

        tack.StartCoroutine(AnimatePulse(pulse, mat, tack.range * 2f, 0.25f));
    }

    static IEnumerator AnimatePulse(GameObject pulse, Material mat, float targetDiameter, float duration)
    {
        float t = 0f;
        while (pulse != null && t < duration)
        {
            float k = t / duration;
            float d = Mathf.Lerp(0.1f, targetDiameter, k);
            pulse.transform.localScale = new Vector3(d, 0.02f, d);
            Color c = mat.GetColor("_BaseColor");
            c.a = Mathf.Lerp(0.7f, 0f, k);
            mat.SetColor("_BaseColor", c);
            t += Time.deltaTime;
            yield return null;
        }
        if (pulse != null) Object.Destroy(pulse);
    }
}
