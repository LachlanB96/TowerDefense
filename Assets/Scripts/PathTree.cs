using UnityEngine;

public class PathTree : MonoBehaviour
{
    public int damage = 1;
    public float lifetime = 10f;
    public float hitRadius = 0.4f;
    public TowerData source;
    public System.Action onDestroyed;

    private float _spawnTime;

    void Start()
    {
        _spawnTime = Time.time;
    }

    void Update()
    {
        if (Time.time - _spawnTime >= lifetime)
        {
            ReturnAndDestroy();
            return;
        }

        Transform units = Spawn.UnitsParent;
        if (units == null) return;

        foreach (Transform unit in units)
        {
            float dx = transform.position.x - unit.position.x;
            float dz = transform.position.z - unit.position.z;
            float dist = Mathf.Sqrt(dx * dx + dz * dz);
            if (dist < hitRadius)
            {
                Movement m = unit.GetComponent<Movement>();
                if (m != null)
                {
                    var report = m.Hit(damage);
                    if (source != null)
                        source.Credit(report.damageDealt, report.killed);
                    ReturnAndDestroy();
                    return;
                }
            }
        }
    }

    void ReturnAndDestroy()
    {
        onDestroyed?.Invoke();
        Destroy(gameObject);
    }
}
