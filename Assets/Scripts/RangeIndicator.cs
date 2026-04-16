using UnityEngine;

public static class RangeIndicator
{
    public static GameObject Create(float range, Transform parent)
    {
        var indicator = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        indicator.name = "RangeIndicator";
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

        return indicator;
    }
}
