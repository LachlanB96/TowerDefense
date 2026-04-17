using UnityEngine;

public static class TowerUtils
{
    public static void EnsureCollider(GameObject tower)
    {
        if (tower.GetComponentInChildren<Collider>() != null) return;
        Bounds bounds = new Bounds(tower.transform.position, Vector3.zero);
        foreach (var r in tower.GetComponentsInChildren<Renderer>())
            bounds.Encapsulate(r.bounds);
        BoxCollider box = tower.AddComponent<BoxCollider>();
        box.center = tower.transform.InverseTransformPoint(bounds.center);
        box.size = bounds.size;
    }

    public static void SetProjectileLayer(GameObject go)
    {
        int layer = LayerMask.NameToLayer("Projectiles");
        if (layer < 0) return;
        go.layer = layer;
        foreach (Transform child in go.transform)
            child.gameObject.layer = layer;
    }
}
