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
    public TowerData source;
    public Hero heroSource;
    internal bool homing;

    private HashSet<GameObject> _hitTargets = new HashSet<GameObject>();
    private Vector3 _origin;

    void Start()
    {
        _origin = transform.position;
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
        Transform units = Spawn.UnitsParent;
        if (units == null) return;

        foreach (Transform unit in units)
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
        {
            var report = movement.Hit(damage);
            if (source != null)
                source.Credit(report.damageDealt, report.killed);
            if (heroSource != null)
                heroSource.Credit(report.damageDealt, report.killed);
        }

        if (applyBurn && hitObj.GetComponent<BurnEffect>() == null)
        {
            var burn = hitObj.AddComponent<BurnEffect>();
            burn.source = source;
        }

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
        Transform units = Spawn.UnitsParent;
        if (units == null) return null;

        GameObject closest = null;
        float closestDist = float.MaxValue;

        foreach (Transform unit in units)
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
