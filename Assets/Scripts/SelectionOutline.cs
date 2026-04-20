using System.Collections.Generic;
using UnityEngine;

public class SelectionOutline
{
    private readonly List<GameObject> _objects = new List<GameObject>();
    private readonly Material _material;

    public SelectionOutline()
    {
        _material = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        _material.SetColor("_BaseColor", Color.white);
        _material.SetFloat("_Cull", 1f);
    }

    public void Add(GameObject target)
    {
        foreach (var r in target.GetComponentsInChildren<Renderer>())
        {
            string n = r.gameObject.name;
            if (n.StartsWith("TackHead") || n.StartsWith("TackShaft") || n.StartsWith("TackTip")
                || n.StartsWith("_"))
                continue;

            var mf = r.GetComponent<MeshFilter>();
            if (mf == null || mf.sharedMesh == null) continue;

            var go = new GameObject("_outline");
            go.transform.SetParent(r.transform, false);
            go.transform.localScale = Vector3.one * 1.1f;

            go.AddComponent<MeshFilter>().sharedMesh = mf.sharedMesh;
            go.AddComponent<MeshRenderer>().sharedMaterial = _material;

            _objects.Add(go);
        }
    }

    public void Clear()
    {
        foreach (var o in _objects)
            if (o != null) Object.Destroy(o);
        _objects.Clear();
    }
}
