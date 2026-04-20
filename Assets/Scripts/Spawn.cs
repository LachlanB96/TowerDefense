using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class Spawn : MonoBehaviour
{
    public static Transform UnitsParent => SceneContainers.Units;

    public GameObject unit;
    private List<GameObject> spawnedUnits = new List<GameObject>();
    public GameObject Waypoints;

    void Start()
    {
        BuildSpawnPanel();
    }

    void BuildSpawnPanel()
    {
        var canvasObj = new GameObject("SpawnUI");
        var canvas = canvasObj.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 10;

        var scaler = canvasObj.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920, 1080);
        canvasObj.AddComponent<GraphicRaycaster>();

        // Panel anchored to bottom center
        var panel = new GameObject("SpawnPanel");
        panel.transform.SetParent(canvasObj.transform, false);

        var prt = panel.AddComponent<RectTransform>();
        prt.anchorMin = new Vector2(0.5f, 0f);
        prt.anchorMax = new Vector2(0.5f, 0f);
        prt.pivot = new Vector2(0.5f, 0f);
        prt.anchoredPosition = new Vector2(0f, 10f);
        prt.sizeDelta = new Vector2(340, 140);

        panel.AddComponent<Image>().color = new Color(0.627f, 0.322f, 0.176f, 0.95f);

        var layout = panel.AddComponent<HorizontalLayoutGroup>();
        layout.padding = new RectOffset(10, 10, 10, 10);
        layout.spacing = 10;
        layout.childForceExpandWidth = false;
        layout.childForceExpandHeight = true;
        layout.childAlignment = TextAnchor.MiddleCenter;

        // Normal unit button (green tint)
        MakeSpawnButton(panel.transform, "UI/unit_icon", "Unit", new Color(0.2f, 0.5f, 0.3f), SpawnUnit);

        // Big unit button (red tint)
        MakeSpawnButton(panel.transform, "UI/bigunit_icon", "Big Unit", new Color(0.6f, 0.15f, 0.12f), SpawnBigUnit);
    }

    void MakeSpawnButton(Transform parent, string spritePath, string label, Color bgColor, UnityEngine.Events.UnityAction action)
    {
        var btnObj = new GameObject(label);
        btnObj.transform.SetParent(parent, false);

        btnObj.AddComponent<Image>().color = bgColor;

        var btn = btnObj.AddComponent<Button>();
        btn.onClick.AddListener(action);
        ColorBlock cb = btn.colors;
        cb.normalColor = Color.white;
        cb.highlightedColor = new Color(1.2f, 1.2f, 1.2f, 1f);
        cb.pressedColor = new Color(0.8f, 0.8f, 0.8f, 1f);
        btn.colors = cb;

        btnObj.AddComponent<LayoutElement>().preferredWidth = 150;

        // Icon
        var iconObj = new GameObject("Icon");
        iconObj.transform.SetParent(btnObj.transform, false);
        var iconImg = iconObj.AddComponent<Image>();
        iconImg.raycastTarget = false;

        var sprite = Resources.Load<Sprite>(spritePath);
        if (sprite != null)
        {
            iconImg.sprite = sprite;
            iconImg.preserveAspect = true;
        }

        var irt = iconObj.GetComponent<RectTransform>();
        irt.anchorMin = new Vector2(0.05f, 0.2f);
        irt.anchorMax = new Vector2(0.95f, 0.95f);
        irt.offsetMin = Vector2.zero;
        irt.offsetMax = Vector2.zero;

        // Label at bottom
        var txtObj = new GameObject("Text");
        txtObj.transform.SetParent(btnObj.transform, false);
        var txt = txtObj.AddComponent<Text>();
        txt.text = label;
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.alignment = TextAnchor.MiddleCenter;
        txt.color = Color.white;
        txt.fontSize = 16;
        txt.fontStyle = FontStyle.Bold;
        txt.raycastTarget = false;

        var outline = txtObj.AddComponent<Outline>();
        outline.effectColor = Color.black;
        outline.effectDistance = new Vector2(1, -1);

        var trt = txtObj.GetComponent<RectTransform>();
        trt.anchorMin = new Vector2(0f, 0f);
        trt.anchorMax = new Vector2(1f, 0.22f);
        trt.offsetMin = Vector2.zero;
        trt.offsetMax = Vector2.zero;
    }

    public void SpawnUnit()
    {
        GameObject newUnit = Instantiate(unit, transform.position, Quaternion.identity);
        newUnit.GetComponent<Movement>().Waypoints = Waypoints;
        newUnit.transform.parent = SceneContainers.Units;
        newUnit.transform.localScale = Vector3.one;
        spawnedUnits.Add(newUnit);

        if (EconomyManager.Instance != null)
            EconomyManager.Instance.AddEconomy(1);
    }

    public void SpawnBigUnit()
    {
        GameObject newUnit = Instantiate(unit, transform.position, Quaternion.identity);
        newUnit.GetComponent<Movement>().Waypoints = Waypoints;
        newUnit.transform.parent = SceneContainers.Units;
        newUnit.transform.localScale = Vector3.one * 2f;
        Movement m = newUnit.GetComponent<Movement>();
        m.health = 5;
        m.insides = 2;
        spawnedUnits.Add(newUnit);

        if (EconomyManager.Instance != null)
            EconomyManager.Instance.AddEconomy(2);
    }

    public void SpawnYellowUnit()
    {
        GameObject newUnit = Instantiate(unit, transform.position, Quaternion.identity);
        newUnit.GetComponent<Movement>().Waypoints = Waypoints;
        newUnit.transform.parent = SceneContainers.Units;
        newUnit.transform.localScale = Vector3.one;
        newUnit.GetComponent<Movement>().insides = 5;
        spawnedUnits.Add(newUnit);
    }

    public List<GameObject> GetSpawnedUnits()
    {
        return spawnedUnits;
    }
}
