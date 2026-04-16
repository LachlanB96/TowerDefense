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

    private float lastAttackTime = -999f;
    private Transform unitsParent;
    private Material diskMaterial;

    void Start()
    {
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

        // Visual: 8 projectiles fly outward from inside the tower
        for (int i = 0; i < 8; i++)
        {
            float angle = i * 45f;
            Vector3 dir = Quaternion.Euler(0, angle, 0) * Vector3.forward;
            GameObject visual = useAirPuff ? CreatePuff() : CreateDisk();
            visual.transform.position = transform.position;
            visual.transform.rotation = Quaternion.LookRotation(dir);
            FlyOutward fly = visual.AddComponent<FlyOutward>();
            fly.direction = dir;
            fly.speed = diskFlySpeed;
        }

        // Homing projectile that deals damage
        GameObject proj = useAirPuff ? CreatePuff() : CreateDisk();
        proj.transform.position = transform.position;
        Velocity vel = proj.AddComponent<Velocity>();
        vel.target = target.gameObject;
        vel.speed = projectileSpeed;
        vel.damage = damage;
        vel.homing = true;
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
}
