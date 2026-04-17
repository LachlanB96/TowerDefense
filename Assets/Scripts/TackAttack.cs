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
    public bool useAirPuff = false;
    public bool useFireball = false;
    public int pierce = 1;

    public float Range => range;

    private float lastAttackTime = -999f;
    private Material diskMaterial;
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

        if (useAirPuff)
        {
            diskMaterial = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            diskMaterial.SetColor("_BaseColor", diskColor);
            MaterialUtils.MakeTransparent(diskMaterial);
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

        Transform units = Spawn.UnitsParent;
        if (units == null) return;

        Transform closest = null;
        float closestDist = range;
        foreach (Transform unit in units)
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
        _squash.Play();

        int count = useFireball ? 4 : 8;
        float startAngle = useFireball ? 45f : 0f;

        for (int i = 0; i < count; i++)
        {
            float angle = startAngle + i * (360f / count);
            Vector3 dir = Quaternion.Euler(0, angle, 0) * Vector3.forward;
            GameObject proj = useFireball ? CreateFireball() : (useAirPuff ? CreatePuff() : CreateDisk());
            proj.transform.position = transform.position;
            proj.transform.rotation = Quaternion.LookRotation(dir);
            TowerUtils.SetProjectileLayer(proj);

            Velocity vel = proj.AddComponent<Velocity>();
            vel.direction = dir;
            vel.speed = diskFlySpeed;
            vel.damage = damage;
            vel.pierce = pierce;
            vel.maxRange = range + 1f;
            vel.applyBurn = useFireball;
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
        MaterialUtils.MakeTransparent(glowMat);
        glow.GetComponent<Renderer>().material = glowMat;

        return fireball;
    }
}
