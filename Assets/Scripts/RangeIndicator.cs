using UnityEngine;

public static class RangeIndicator
{
    public static GameObject Create(float range, Transform parent)
    {
        var indicator = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        indicator.name = "_RangeIndicator";
        Object.Destroy(indicator.GetComponent<Collider>());
        indicator.transform.SetParent(parent, false);
        indicator.transform.localPosition = new Vector3(0f, 0.2f, 0f);
        float diameter = range * 2f;
        indicator.transform.localScale = new Vector3(diameter, 0.01f, diameter);

        var mat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        mat.SetColor("_BaseColor", new Color(0f, 0f, 0f, 0.25f));
        mat.SetFloat("_Surface", 1);
        mat.SetOverrideTag("RenderType", "Transparent");
        mat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
        mat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
        mat.SetInt("_ZWrite", 0);
        mat.renderQueue = 3000;
        mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
        indicator.GetComponent<Renderer>().material = mat;

        // Black border ring using LineRenderer
        var borderObj = new GameObject("_RangeBorder");
        borderObj.transform.SetParent(parent, false);
        borderObj.transform.localPosition = new Vector3(0f, 0.21f, 0f);

        var lr = borderObj.AddComponent<LineRenderer>();
        lr.useWorldSpace = false;
        lr.loop = true;
        lr.widthMultiplier = 0.06f;
        lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        lr.receiveShadows = false;

        var borderMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        borderMat.SetColor("_BaseColor", Color.black);
        lr.material = borderMat;

        int segments = 48;
        lr.positionCount = segments;
        for (int i = 0; i < segments; i++)
        {
            float angle = i * Mathf.PI * 2f / segments;
            lr.SetPosition(i, new Vector3(Mathf.Cos(angle) * range, 0f, Mathf.Sin(angle) * range));
        }

        // Make the border a child of the indicator so it's destroyed together
        borderObj.transform.SetParent(indicator.transform, true);

        return indicator;
    }
}
