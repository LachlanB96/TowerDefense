using System.Collections.Generic;
using UnityEngine;

public static class OutlineUtils
{
    private static readonly Dictionary<Color, Material> _cache = new Dictionary<Color, Material>();

    public static Material GetMaterial(Color color)
    {
        if (!_cache.TryGetValue(color, out var mat) || mat == null)
        {
            mat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            mat.SetColor("_BaseColor", color);
            mat.SetFloat("_Cull", 1f);
            _cache[color] = mat;
        }
        return mat;
    }

    public static GameObject AddInvertedHull(Transform target, Color color, float scale = 1.15f)
    {
        var mf = target.GetComponent<MeshFilter>();
        if (mf == null || mf.sharedMesh == null) return null;

        var outline = new GameObject("_outline");
        outline.transform.SetParent(target, false);
        outline.transform.localScale = Vector3.one * scale;

        outline.AddComponent<MeshFilter>().sharedMesh = mf.sharedMesh;
        outline.AddComponent<MeshRenderer>().sharedMaterial = GetMaterial(color);

        return outline;
    }
}
