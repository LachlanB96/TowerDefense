using UnityEngine;
using UnityEngine.UI;

public static class SelectionPanelBuilder
{
    public static Button Button(string label, Transform parent, Color bg)
    {
        var go = new GameObject(label);
        go.transform.SetParent(parent, false);

        go.AddComponent<Image>().color = bg;

        var btn = go.AddComponent<Button>();
        UIBuilder.ApplyStandardColors(btn);

        go.AddComponent<LayoutElement>().preferredHeight = 45;

        var txt = UIBuilder.Text("Text", go.transform, label, 18, Color.white);
        UIBuilder.Stretch(txt.gameObject);

        return btn;
    }

    public static void Label(string text, Transform parent)
    {
        var txt = UIBuilder.Text("Label", parent, text, 14, new Color(1f, 1f, 1f, 0.6f));
        txt.gameObject.AddComponent<LayoutElement>().preferredHeight = 25;
    }

    public static Text StatsBlock(Transform parent)
    {
        var go = new GameObject("Stats");
        go.transform.SetParent(parent, false);

        go.AddComponent<Image>().color = new Color(0f, 0f, 0f, 0.25f);
        go.AddComponent<LayoutElement>().preferredHeight = 52;

        var txt = UIBuilder.Text("Text", go.transform, "Kills: 0\nDamage: 0", 16, Color.white, bold: true);
        txt.raycastTarget = false;
        UIBuilder.AddOutline(txt.gameObject);
        var rt = txt.GetComponent<RectTransform>();
        rt.anchorMin = Vector2.zero;
        rt.anchorMax = Vector2.one;
        rt.offsetMin = new Vector2(4, 2);
        rt.offsetMax = new Vector2(-4, -2);
        return txt;
    }
}
