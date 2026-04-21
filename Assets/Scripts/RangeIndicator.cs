using UnityEngine;

/// <summary>
/// Creates the flat disc + black border ring that visualises a tower's attack range.
/// </summary>
public static class RangeIndicator
{
    /// <summary>
    /// Builds a range indicator parented under <paramref name="parent"/> (so it moves
    /// and gets destroyed with the tower) but authored in WORLD units regardless of
    /// how the parent prefab is scaled. Without the scale-compensation root, a
    /// tower prefab at 2× scale would draw its range at 2× diameter — see
    /// Boat000.prefab (scale 2) vs Tack/Sniper (scale 1).
    /// </summary>
    public static GameObject Create(float range, Transform parent)
    {
        // Root wrapper whose local scale cancels out the parent's lossy scale.
        // Everything under it lives in world units, so the disc and the border
        // line render at the intended physical size.
        var root = new GameObject("_RangeIndicator");
        root.transform.SetParent(parent, false);
        root.transform.localScale = InverseScale(parent.lossyScale);

        float diameter = range * 2f;

        // Disc (semi-transparent black fill under the tower).
        var disc = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        disc.name = "_RangeDisc";
        Object.Destroy(disc.GetComponent<Collider>());
        disc.transform.SetParent(root.transform, false);
        disc.transform.localPosition = new Vector3(0f, 0.2f, 0f);
        disc.transform.localScale = new Vector3(diameter, 0.01f, diameter);

        var fillMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        fillMat.SetColor("_BaseColor", new Color(0f, 0f, 0f, 0.25f));
        MaterialUtils.MakeTransparent(fillMat);
        disc.GetComponent<Renderer>().material = fillMat;

        // Border ring — a LineRenderer drawing a circle of radius `range`. Sibling
        // of the disc (not a child), so its LineRenderer local-space positions
        // translate directly to world units via the scale-neutral root.
        var border = new GameObject("_RangeBorder");
        border.transform.SetParent(root.transform, false);
        border.transform.localPosition = new Vector3(0f, 0.21f, 0f);

        var lr = border.AddComponent<LineRenderer>();
        lr.useWorldSpace = false;
        lr.loop = true;
        lr.widthMultiplier = 0.06f;
        lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        lr.receiveShadows = false;

        var borderMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        borderMat.SetColor("_BaseColor", Color.black);
        lr.material = borderMat;

        const int segments = 48;
        lr.positionCount = segments;
        for (int i = 0; i < segments; i++)
        {
            float angle = i * Mathf.PI * 2f / segments;
            lr.SetPosition(i, new Vector3(Mathf.Cos(angle) * range, 0f, Mathf.Sin(angle) * range));
        }

        return root;
    }

    /// <summary>
    /// Componentwise 1/s with a guard against divide-by-zero. Used so a scale-compensation
    /// child transform can cancel out its parent's lossy scale exactly.
    /// </summary>
    private static Vector3 InverseScale(Vector3 s)
    {
        return new Vector3(
            Mathf.Approximately(s.x, 0f) ? 1f : 1f / s.x,
            Mathf.Approximately(s.y, 0f) ? 1f : 1f / s.y,
            Mathf.Approximately(s.z, 0f) ? 1f : 1f / s.z);
    }
}
