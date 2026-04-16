using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class TackAttack : MonoBehaviour
{
    public float range = 3f;
    public float cooldown = 0.5f;
    public int damage = 1;
    public float projectileSpeed = 0.15f;
    public float diskFlySpeed = 15f;
    public Color diskColor = new Color(0.76f, 0.6f, 0.42f);
    public float diskMetallic = 0f;
    public float diskSmoothness = 0.2f;
    public bool useAirPuff = false;
    public bool useFireball = false;
    public int pierce = 1;

    private float lastAttackTime = -999f;
    private Transform unitsParent;
    private Material diskMaterial;
    private List<Transform> _bodyParts = new List<Transform>();
    private List<Vector3> _bodyOriginalScales = new List<Vector3>();
    private Coroutine _squashRoutine;

    void Start()
    {
        foreach (Transform child in transform)
        {
            string n = child.name;
            if (n.StartsWith("TackHead") || n.StartsWith("TackShaft") || n.StartsWith("TackTip")
                || n.StartsWith("_")) continue;
            _bodyParts.Add(child);
            _bodyOriginalScales.Add(child.localScale);
        }

        Spawn spawner = FindAnyObjectByType<Spawn>();
        if (spawner != null)
            unitsParent = spawner.transform;

        if (useAirPuff)
        {
            diskMaterial = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            diskMaterial.SetColor("_BaseColor", diskColor);
            diskMaterial.SetFloat("_Surface", 1);
            diskMaterial.SetOverrideTag("RenderType", "Transparent");
            diskMaterial.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
            diskMaterial.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            diskMaterial.SetInt("_ZWrite", 0);
            diskMaterial.renderQueue = 3000;
            diskMaterial.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
        }
        else
        {
            Renderer r = GetComponentInChildren<Renderer>();
            if (r != null && r.sharedMaterial != null)
                diskMaterial = new Material(r.sharedMaterial);
            else
                diskMaterial = new Material(Shader.Find("Universal Render Pipeline/Lit"));

            diskMaterial.SetColor("_BaseColor", diskColor);
            diskMaterial.SetFloat("_Metallic", diskMetallic);
            diskMaterial.SetFloat("_Smoothness", diskSmoothness);
        }
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

        Transform closest = null;
        float closestDist = range;
        foreach (Transform unit in unitsParent)
        {
            float dist = Vector3.Distance(transform.position, unit.position);
            if (dist < closestDist)
            {
                closestDist = dist;
                closest = unit;
            }
        }

        if (closest != null)
            Shoot(closest);
    }

    void Shoot(Transform target)
    {
        lastAttackTime = Time.time;

        if (_squashRoutine != null)
            StopCoroutine(_squashRoutine);
        _squashRoutine = StartCoroutine(ShootSquash());

        int count = useFireball ? 4 : 8;
        float startAngle = useFireball ? 45f : 0f;

        // Each directional projectile deals damage with pierce
        for (int i = 0; i < count; i++)
        {
            float angle = startAngle + i * (360f / count);
            Vector3 dir = Quaternion.Euler(0, angle, 0) * Vector3.forward;
            GameObject proj = useFireball ? CreateFireball() : (useAirPuff ? CreatePuff() : CreateDisk());
            proj.transform.position = transform.position;
            proj.transform.rotation = Quaternion.LookRotation(dir);
            SetProjectileLayer(proj);

            Velocity vel = proj.AddComponent<Velocity>();
            vel.direction = dir;
            vel.speed = diskFlySpeed;
            vel.damage = damage;
            vel.pierce = pierce;
            vel.maxRange = range + 1f;
            vel.applyBurn = useFireball;
        }
    }

    static void SetProjectileLayer(GameObject go)
    {
        int layer = LayerMask.NameToLayer("Projectiles");
        if (layer < 0) return;
        go.layer = layer;
        foreach (Transform child in go.transform)
            child.gameObject.layer = layer;
    }

    IEnumerator ShootSquash()
    {
        // Phase 1: Squash (wider + shorter)
        yield return ScaleBodyTo(new Vector3(1.15f, 0.8f, 1.15f), 0.08f);
        // Phase 2: Overshoot stretch (narrower + taller)
        yield return ScaleBodyTo(new Vector3(0.95f, 1.05f, 0.95f), 0.1f);
        // Phase 3: Settle back to normal
        yield return ScaleBodyTo(Vector3.one, 0.08f);
        _squashRoutine = null;
    }

    IEnumerator ScaleBodyTo(Vector3 scaleMultiplier, float duration)
    {
        // Capture each part's current scale
        Vector3[] startScales = new Vector3[_bodyParts.Count];
        for (int i = 0; i < _bodyParts.Count; i++)
            startScales[i] = _bodyParts[i] != null ? _bodyParts[i].localScale : _bodyOriginalScales[i];

        // Target = original scale * multiplier
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

    GameObject CreateDisk()
    {
        GameObject disk = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        disk.transform.localScale = new Vector3(0.3f, 0.05f, 0.3f);
        disk.GetComponent<Renderer>().sharedMaterial = diskMaterial;
        Destroy(disk.GetComponent<Collider>());
        return disk;
    }

    GameObject CreatePuff()
    {
        GameObject puff = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        puff.transform.localScale = new Vector3(0.35f, 0.25f, 0.35f);
        puff.GetComponent<Renderer>().sharedMaterial = diskMaterial;
        Destroy(puff.GetComponent<Collider>());
        return puff;
    }

    GameObject CreateFireball()
    {
        var fireball = new GameObject("Fireball");

        // Core (bright yellow-orange)
        var core = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        core.name = "_core";
        Destroy(core.GetComponent<Collider>());
        core.transform.SetParent(fireball.transform, false);
        core.transform.localScale = Vector3.one * 0.25f;

        var coreMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        coreMat.SetColor("_BaseColor", new Color(1f, 0.85f, 0.2f));
        core.GetComponent<Renderer>().material = coreMat;

        // Outer glow (orange, transparent)
        var glow = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        glow.name = "_glow";
        Destroy(glow.GetComponent<Collider>());
        glow.transform.SetParent(fireball.transform, false);
        glow.transform.localScale = Vector3.one * 0.4f;

        var glowMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        glowMat.SetColor("_BaseColor", new Color(1f, 0.35f, 0.0f, 0.5f));
        glowMat.SetFloat("_Surface", 1);
        glowMat.SetOverrideTag("RenderType", "Transparent");
        glowMat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
        glowMat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
        glowMat.SetInt("_ZWrite", 0);
        glowMat.renderQueue = 3000;
        glowMat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
        glow.GetComponent<Renderer>().material = glowMat;

        return fireball;
    }
}
