using System.Collections.Generic;
using UnityEngine;

public class Velocity : MonoBehaviour
{
    public GameObject target;
    public Vector3 direction;
    public float speed;
    public int damage = 1;
    public bool applyBurn;
    public int pierce = 1;
    public float maxRange = 5f;
    public float hitRadius = 0.7f;
    internal bool homing;

    private HashSet<GameObject> _hitTargets = new HashSet<GameObject>();
    private Vector3 _origin;
    private Transform _unitsParent;

    void Start()
    {
        _origin = transform.position;
        Spawn spawner = FindAnyObjectByType<Spawn>();
        if (spawner != null)
            _unitsParent = spawner.transform;
    }

    void Update()
    {
        if (homing)
            UpdateHoming();
        else
            UpdateDirectional();
    }

    void UpdateHoming()
    {
        if (target == null)
        {
            Destroy(gameObject);
            return;
        }

        transform.position = Vector3.MoveTowards(transform.position, target.transform.position, speed);

        if (Vector3.Distance(transform.position, target.transform.position) < 0.1f)
            HitTarget(target);
    }

    void UpdateDirectional()
    {
        transform.position += direction * speed * Time.deltaTime;

        // Destroy if past max range
        if (Vector3.Distance(_origin, transform.position) > maxRange)
        {
            Destroy(gameObject);
            return;
        }

        // Check hits against all units
        if (_unitsParent == null)
        {
            Spawn spawner = FindAnyObjectByType<Spawn>();
            if (spawner != null) _unitsParent = spawner.transform;
            if (_unitsParent == null) return;
        }

        foreach (Transform unit in _unitsParent)
        {
            if (_hitTargets.Contains(unit.gameObject)) continue;
            var m = unit.GetComponent<Movement>();
            if (m == null || !m.enabled) continue;

            float dx = transform.position.x - unit.position.x;
            float dz = transform.position.z - unit.position.z;
            if (Mathf.Sqrt(dx * dx + dz * dz) < hitRadius)
            {
                HitTarget(unit.gameObject);
                if (pierce <= 0) return;
            }
        }
    }

    void HitTarget(GameObject hitObj)
    {
        var movement = hitObj.GetComponent<Movement>();
        if (movement != null)
            movement.Hit(damage);

        if (applyBurn && hitObj.GetComponent<BurnEffect>() == null)
            hitObj.AddComponent<BurnEffect>();

        _hitTargets.Add(hitObj);
        pierce--;

        if (pierce <= 0)
        {
            Destroy(gameObject);
            return;
        }

        // For homing mode, find next target
        if (homing)
        {
            GameObject next = FindNextTarget();
            if (next != null)
                target = next;
            else
                Destroy(gameObject);
        }
    }

    GameObject FindNextTarget()
    {
        if (_unitsParent == null)
        {
            Spawn spawner = FindAnyObjectByType<Spawn>();
            if (spawner != null) _unitsParent = spawner.transform;
            if (_unitsParent == null) return null;
        }

        GameObject closest = null;
        float closestDist = float.MaxValue;

        foreach (Transform unit in _unitsParent)
        {
            if (_hitTargets.Contains(unit.gameObject)) continue;
            var m = unit.GetComponent<Movement>();
            if (m == null || !m.enabled) continue;

            float dist = Vector3.Distance(transform.position, unit.position);
            if (dist < closestDist)
            {
                closestDist = dist;
                closest = unit.gameObject;
            }
        }

        return closest;
    }
}
