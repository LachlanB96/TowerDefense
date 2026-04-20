using UnityEngine;
using UnityEngine.UI;

public static class UIBuilder
{
    private static readonly Vector2 DesignResolution = new Vector2(1920, 1080);
    private static Font _font;

    private static Font DefaultFont
    {
        get
        {
            if (_font == null) _font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            return _font;
        }
    }

    public static GameObject Canvas(string name, int sortingOrder)
    {
        var go = new GameObject(name);
        var canvas = go.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = sortingOrder;
        var scaler = go.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = DesignResolution;
        go.AddComponent<GraphicRaycaster>();
        return go;
    }

    public static Text Text(string name, Transform parent, string content, int fontSize, Color color, bool bold = false)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var t = go.AddComponent<Text>();
        t.text = content;
        t.font = DefaultFont;
        t.alignment = TextAnchor.MiddleCenter;
        t.color = color;
        t.fontSize = fontSize;
        if (bold) t.fontStyle = FontStyle.Bold;
        return t;
    }

    public static RectTransform Stretch(GameObject go)
    {
        var rt = go.GetComponent<RectTransform>() ?? go.AddComponent<RectTransform>();
        rt.anchorMin = Vector2.zero;
        rt.anchorMax = Vector2.one;
        rt.offsetMin = Vector2.zero;
        rt.offsetMax = Vector2.zero;
        return rt;
    }

    public static void ApplyStandardColors(Button btn)
    {
        ColorBlock cb = btn.colors;
        cb.normalColor = Color.white;
        cb.highlightedColor = new Color(1.2f, 1.2f, 1.2f, 1f);
        cb.pressedColor = new Color(0.8f, 0.8f, 0.8f, 1f);
        cb.disabledColor = new Color(0.5f, 0.5f, 0.5f, 0.5f);
        btn.colors = cb;
    }

    public static Outline AddOutline(GameObject go, float distance = 1f)
    {
        var outline = go.AddComponent<Outline>();
        outline.effectColor = Color.black;
        outline.effectDistance = new Vector2(distance, -distance);
        return outline;
    }

    public static Image RadialCooldown(string name, Transform parent, Color tint)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var img = go.AddComponent<Image>();
        img.color = tint;
        img.type = Image.Type.Filled;
        img.fillMethod = Image.FillMethod.Radial360;
        img.fillOrigin = (int)Image.Origin360.Top;
        img.fillAmount = 0f;
        img.raycastTarget = false;
        Stretch(go);
        return img;
    }
}
