using System;
using UnityEngine;

public static class UnitScanner
{
    public static Transform ClosestInRange(Vector3 origin, float range)
    {
        Transform units = Spawn.UnitsParent;
        if (units == null) return null;

        Transform best = null;
        float bestDist = range;
        foreach (Transform unit in units)
        {
            var m = unit.GetComponent<Movement>();
            if (m == null || !m.enabled) continue;
            float dist = Vector3.Distance(origin, unit.position);
            if (dist < bestDist)
            {
                bestDist = dist;
                best = unit;
            }
        }
        return best;
    }

    public static Transform StrongestInRange(Vector3 origin, float range)
    {
        Transform units = Spawn.UnitsParent;
        if (units == null) return null;

        Transform best = null;
        int bestHealth = -1;
        foreach (Transform unit in units)
        {
            var m = unit.GetComponent<Movement>();
            if (m == null || !m.enabled) continue;
            if (Vector3.Distance(origin, unit.position) > range) continue;
            if (m.health > bestHealth)
            {
                bestHealth = m.health;
                best = unit;
            }
        }
        return best;
    }

    public static Transform FurthestOnPathInRange(Vector3 origin, float range)
    {
        Transform units = Spawn.UnitsParent;
        if (units == null) return null;

        Transform best = null;
        int bestIndex = int.MaxValue;
        foreach (Transform unit in units)
        {
            var m = unit.GetComponent<Movement>();
            if (m == null || !m.enabled) continue;
            if (Vector3.Distance(origin, unit.position) > range) continue;
            int idx = unit.GetSiblingIndex();
            if (idx < bestIndex)
            {
                bestIndex = idx;
                best = unit;
            }
        }
        return best;
    }

    // Snapshots the child list before iterating so the callback can safely kill/destroy units.
    public static void ForEachInRange(Vector3 origin, float range, Action<Transform, Movement> callback)
    {
        Transform units = Spawn.UnitsParent;
        if (units == null) return;

        int count = units.childCount;
        var snapshot = new Transform[count];
        for (int i = 0; i < count; i++) snapshot[i] = units.GetChild(i);

        for (int i = 0; i < count; i++)
        {
            Transform unit = snapshot[i];
            if (unit == null) continue;
            var m = unit.GetComponent<Movement>();
            if (m == null || !m.enabled) continue;
            if (Vector3.Distance(origin, unit.position) > range) continue;
            callback(unit, m);
        }
    }
}
