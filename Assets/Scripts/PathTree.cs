using UnityEngine;

public class PathTree : MonoBehaviour
{
    public int damage = 1;
    public float lifetime = 10f;
    public float hitRadius = 0.4f;
    public System.Action onDestroyed;

    private float _spawnTime;
    private Transform _unitsParent;

    void Start()
    {
        _spawnTime = Time.time;
        Spawn spawner = FindAnyObjectByType<Spawn>();
        if (spawner != null)
            _unitsParent = spawner.transform;
    }

    void Update()
    {
        if (Time.time - _spawnTime >= lifetime)
        {
            ReturnAndDestroy();
            return;
        }

        if (_unitsParent == null)
        {
            Spawn spawner = FindAnyObjectByType<Spawn>();
            if (spawner != null) _unitsParent = spawner.transform;
            if (_unitsParent == null) return;
        }

        foreach (Transform unit in _unitsParent)
        {
            float dx = transform.position.x - unit.position.x;
            float dz = transform.position.z - unit.position.z;
            float dist = Mathf.Sqrt(dx * dx + dz * dz);
            if (dist < hitRadius)
            {
                Movement m = unit.GetComponent<Movement>();
                if (m != null)
                {
                    m.Hit(damage);
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
