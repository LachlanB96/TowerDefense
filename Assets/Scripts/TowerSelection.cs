using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using UnityEngine.UI;

public class TowerSelection : MonoBehaviour
{
    [Header("Upgrade Prefabs")]
    public GameObject tack100Prefab;
    public GameObject tack010Prefab;
    public GameObject tack001Prefab;

    private GameObject _selectedTower;
    private GameObject _rangeIndicator;
    private readonly List<GameObject> _outlineObjects = new List<GameObject>();
    private Material _outlineMaterial;

    // UI
    private GameObject _panelCanvas;
    private GameObject _actionPanel;
    private Button _sellButton;
    private Button _upgrade1Button;
    private Button _upgrade2Button;
    private Button _upgrade3Button;
    private Image _upgrade1Icon;
    private Image _upgrade2Icon;
    private Image _upgrade3Icon;

    void Start()
    {
        _outlineMaterial = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        _outlineMaterial.SetColor("_BaseColor", Color.white);
        _outlineMaterial.SetFloat("_Cull", 1f); // front-face cull for inverted hull outline
        BuildUI();
    }

    void Update()
    {
        HandleKeyboardShortcuts();

        if (Mouse.current == null || !Mouse.current.leftButton.wasPressedThisFrame) return;

        // Don't process during tower placement
        var placer = FindAnyObjectByType<TowerPlacer>();
        if (placer != null && placer.IsPlacing) return;

        // Only block clicks that land on our action panel (not all UI)
        if (_actionPanel != null && _actionPanel.activeSelf)
        {
            RectTransform panelRect = _actionPanel.GetComponent<RectTransform>();
            if (RectTransformUtility.RectangleContainsScreenPoint(panelRect, Mouse.current.position.ReadValue()))
                return;
        }

        Vector2 mousePos = Mouse.current.position.ReadValue();
        Ray ray = Camera.main.ScreenPointToRay(mousePos);

        // Use RaycastAll to find towers even behind other objects
        TowerData foundTower = null;
        float bestDist = float.MaxValue;

        RaycastHit[] hits = Physics.RaycastAll(ray, 500f);
        foreach (var h in hits)
        {
            var data = h.collider.GetComponentInParent<TowerData>();
            if (data != null && h.distance < bestDist)
            {
                bestDist = h.distance;
                foundTower = data;
            }
        }

        // Fallback: screen-space proximity check for all towers
        if (foundTower == null)
        {
            Camera cam = Camera.main;
            float closestScreenDist = 50f; // max pixel distance to count as a click
            foreach (var td in FindObjectsByType<TowerData>(FindObjectsSortMode.None))
            {
                Vector3 screenPt = cam.WorldToScreenPoint(td.transform.position);
                if (screenPt.z < 0) continue; // behind camera
                float dist = Vector2.Distance(mousePos, new Vector2(screenPt.x, screenPt.y));
                if (dist < closestScreenDist)
                {
                    closestScreenDist = dist;
                    foundTower = td;
                }
            }
        }

        if (foundTower != null)
        {
            Select(foundTower.gameObject);
            return;
        }

        Deselect();
    }

    void HandleKeyboardShortcuts()
    {
        if (_selectedTower == null) return;
        var kb = Keyboard.current;
        if (kb == null) return;

        if (kb.digit1Key.wasPressedThisFrame) OnUpgrade(1);
        else if (kb.digit2Key.wasPressedThisFrame) OnUpgrade(2);
        else if (kb.digit3Key.wasPressedThisFrame) OnUpgrade(3);
        else if (kb.qKey.wasPressedThisFrame) OnSell();
    }

    // ── Selection ────────────────────────────────────────────────────────────

    public void Select(GameObject tower)
    {
        if (_selectedTower == tower) return;
        Deselect();
        _selectedTower = tower;
        AddOutline();
        ShowRangeIndicator();
        _actionPanel.SetActive(true);
        RefreshButtons();
    }

    public void Deselect()
    {
        if (_selectedTower == null) return;
        RemoveOutline();
        HideRangeIndicator();
        _actionPanel.SetActive(false);
        _selectedTower = null;
    }

    void ShowRangeIndicator()
    {
        float range = 0f;
        var tackAttack = _selectedTower.GetComponent<TackAttack>();
        var sniperAttack = _selectedTower.GetComponent<SniperAttack>();
        if (tackAttack != null) range = tackAttack.range;
        else if (sniperAttack != null) range = sniperAttack.range;
        if (range <= 0f) return;
        _rangeIndicator = RangeIndicator.Create(range, _selectedTower.transform);
    }

    void HideRangeIndicator()
    {
        if (_rangeIndicator != null)
        {
            Destroy(_rangeIndicator);
            _rangeIndicator = null;
        }
    }

    // ── White Outline (inverted hull) ────────────────────────────────────────

    void AddOutline()
    {
        foreach (var r in _selectedTower.GetComponentsInChildren<Renderer>())
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
            go.AddComponent<MeshRenderer>().sharedMaterial = _outlineMaterial;

            _outlineObjects.Add(go);
        }
    }

    void RemoveOutline()
    {
        foreach (var o in _outlineObjects)
            if (o != null) Destroy(o);
        _outlineObjects.Clear();
    }

    // ── Right-side action panel UI ───────────────────────────────────────────

    void BuildUI()
    {
        // Canvas
        _panelCanvas = new GameObject("SelectionUI");
        var canvas = _panelCanvas.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 10;

        var scaler = _panelCanvas.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920, 1080);

        _panelCanvas.AddComponent<GraphicRaycaster>();

        // Panel anchored to right side
        _actionPanel = new GameObject("ActionPanel");
        _actionPanel.transform.SetParent(_panelCanvas.transform, false);

        var prt = _actionPanel.AddComponent<RectTransform>();
        prt.anchorMin = new Vector2(1, 0.3f);
        prt.anchorMax = new Vector2(1, 0.7f);
        prt.pivot = new Vector2(1, 0.5f);
        prt.anchoredPosition = Vector2.zero;
        prt.sizeDelta = new Vector2(160, 0);

        _actionPanel.AddComponent<Image>().color = new Color(0.627f, 0.322f, 0.176f, 0.95f);

        var layout = _actionPanel.AddComponent<VerticalLayoutGroup>();
        layout.padding = new RectOffset(10, 10, 10, 10);
        layout.spacing = 8;
        layout.childForceExpandWidth = true;
        layout.childForceExpandHeight = false;
        layout.childAlignment = TextAnchor.UpperCenter;

        // Sell button (red)
        _sellButton = MakeButton("Sell", _actionPanel.transform, new Color(0.7f, 0.15f, 0.15f));
        _sellButton.onClick.AddListener(OnSell);

        // Upgrade header
        MakeLabel("-- Upgrades --", _actionPanel.transform);

        // Three upgrade path buttons with icons
        Color btnColor = new Color(0.545f, 0.271f, 0.075f);

        _upgrade1Button = MakeUpgradeButton("Path 1", _actionPanel.transform, btnColor, "UI/tack100_icon", out _upgrade1Icon);
        _upgrade1Button.onClick.AddListener(() => OnUpgrade(1));

        _upgrade2Button = MakeUpgradeButton("Path 2", _actionPanel.transform, btnColor, "UI/tack010_icon", out _upgrade2Icon);
        _upgrade2Button.onClick.AddListener(() => OnUpgrade(2));

        _upgrade3Button = MakeUpgradeButton("Path 3", _actionPanel.transform, btnColor, "UI/tack001_icon", out _upgrade3Icon);
        _upgrade3Button.onClick.AddListener(() => OnUpgrade(3));

        _actionPanel.SetActive(false);
    }

    Button MakeButton(string label, Transform parent, Color bg)
    {
        var go = new GameObject(label);
        go.transform.SetParent(parent, false);

        go.AddComponent<Image>().color = bg;

        var btn = go.AddComponent<Button>();
        ColorBlock cb = btn.colors;
        cb.normalColor = Color.white;
        cb.highlightedColor = new Color(1.2f, 1.2f, 1.2f, 1f);
        cb.pressedColor = new Color(0.8f, 0.8f, 0.8f, 1f);
        cb.disabledColor = new Color(0.5f, 0.5f, 0.5f, 0.5f);
        btn.colors = cb;

        go.AddComponent<LayoutElement>().preferredHeight = 45;

        // Text child
        var tgo = new GameObject("Text");
        tgo.transform.SetParent(go.transform, false);

        var txt = tgo.AddComponent<Text>();
        txt.text = label;
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.alignment = TextAnchor.MiddleCenter;
        txt.color = Color.white;
        txt.fontSize = 18;

        var trt = tgo.GetComponent<RectTransform>();
        trt.anchorMin = Vector2.zero;
        trt.anchorMax = Vector2.one;
        trt.offsetMin = Vector2.zero;
        trt.offsetMax = Vector2.zero;

        return btn;
    }

    Button MakeUpgradeButton(string label, Transform parent, Color bg, string spritePath, out Image iconImage)
    {
        var go = new GameObject(label);
        go.transform.SetParent(parent, false);

        go.AddComponent<Image>().color = bg;

        var btn = go.AddComponent<Button>();
        ColorBlock cb = btn.colors;
        cb.normalColor = Color.white;
        cb.highlightedColor = new Color(1.2f, 1.2f, 1.2f, 1f);
        cb.pressedColor = new Color(0.8f, 0.8f, 0.8f, 1f);
        cb.disabledColor = new Color(0.5f, 0.5f, 0.5f, 0.5f);
        btn.colors = cb;

        go.AddComponent<LayoutElement>().preferredHeight = 55;

        // Icon on the left
        var iconObj = new GameObject("Icon");
        iconObj.transform.SetParent(go.transform, false);
        iconImage = iconObj.AddComponent<Image>();
        iconImage.raycastTarget = false;
        iconImage.preserveAspect = true;

        var sprite = Resources.Load<Sprite>(spritePath);
        if (sprite != null)
            iconImage.sprite = sprite;

        var irt = iconObj.GetComponent<RectTransform>();
        irt.anchorMin = new Vector2(0.02f, 0.05f);
        irt.anchorMax = new Vector2(0.35f, 0.95f);
        irt.offsetMin = Vector2.zero;
        irt.offsetMax = Vector2.zero;

        // Text on the right
        var tgo = new GameObject("Text");
        tgo.transform.SetParent(go.transform, false);

        var txt = tgo.AddComponent<Text>();
        txt.text = label;
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.alignment = TextAnchor.MiddleCenter;
        txt.color = Color.white;
        txt.fontSize = 15;

        var trt = tgo.GetComponent<RectTransform>();
        trt.anchorMin = new Vector2(0.35f, 0f);
        trt.anchorMax = Vector2.one;
        trt.offsetMin = Vector2.zero;
        trt.offsetMax = Vector2.zero;

        return btn;
    }

    void MakeLabel(string text, Transform parent)
    {
        var go = new GameObject("Label");
        go.transform.SetParent(parent, false);

        var txt = go.AddComponent<Text>();
        txt.text = text;
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.alignment = TextAnchor.MiddleCenter;
        txt.color = new Color(1f, 1f, 1f, 0.6f);
        txt.fontSize = 14;

        go.AddComponent<LayoutElement>().preferredHeight = 25;
    }

    void RefreshButtons()
    {
        var data = _selectedTower != null ? _selectedTower.GetComponent<TowerData>() : null;
        if (data == null) return;

        // Sell button shows refund value
        var sellTxt = _sellButton.GetComponentInChildren<Text>();
        sellTxt.text = $"Sell (${data.SellValue})";

        int[] levels = { data.upgradePath1Level, data.upgradePath2Level, data.upgradePath3Level };
        Button[] buttons = { _upgrade1Button, _upgrade2Button, _upgrade3Button };

        for (int i = 0; i < 3; i++)
        {
            bool available = TowerCosts.TryGetUpgrade(data.towerType, i, levels[i], out var info);
            bool canAfford = available && EconomyManager.Instance != null && EconomyManager.Instance.CanAfford(info.cost);
            buttons[i].interactable = available && canAfford && GetUpgradePrefab(info.resultType) != null;

            var txt = buttons[i].GetComponentInChildren<Text>();
            if (available)
                txt.text = $"Path {i + 1} (${info.cost})";
            else
                txt.text = $"Path {i + 1}";
        }
    }

    GameObject GetUpgradePrefab(string resultType)
    {
        switch (resultType)
        {
            case "tack100": return tack100Prefab;
            case "tack010": return tack010Prefab;
            case "tack001": return tack001Prefab;
            default: return null;
        }
    }

    // ── Actions ──────────────────────────────────────────────────────────────

    void OnSell()
    {
        if (_selectedTower == null) return;
        GameObject tower = _selectedTower;
        var data = tower.GetComponent<TowerData>();
        int refund = data != null ? data.SellValue : 0;
        Vector3 worldPos = tower.transform.position;

        Deselect();

        if (refund > 0 && EconomyManager.Instance != null)
        {
            EconomyManager.Instance.money += refund;
            SpawnSellText(worldPos, refund);
        }

        Destroy(tower);
    }

    void SpawnSellText(Vector3 worldPos, int amount)
    {
        Canvas canvas = null;
        foreach (var c in FindObjectsByType<Canvas>(FindObjectsSortMode.None))
        {
            if (c.renderMode == RenderMode.ScreenSpaceOverlay)
            {
                canvas = c;
                break;
            }
        }
        if (canvas == null) return;

        var go = new GameObject("SellText");
        go.transform.SetParent(canvas.transform, false);

        var txt = go.AddComponent<Text>();
        txt.text = $"+${amount}";
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.fontSize = 28;
        txt.color = new Color(1f, 0.85f, 0.1f); // gold
        txt.alignment = TextAnchor.MiddleCenter;
        txt.fontStyle = FontStyle.Bold;
        txt.raycastTarget = false;

        var outline = go.AddComponent<Outline>();
        outline.effectColor = Color.black;
        outline.effectDistance = new Vector2(2, -2);

        var rt = go.GetComponent<RectTransform>();
        rt.sizeDelta = new Vector2(200, 40);

        // Position at tower's screen position
        Vector3 screenPos = Camera.main.WorldToScreenPoint(worldPos);
        rt.position = screenPos;

        StartCoroutine(FloatAndFade(rt, txt, outline));
    }

    IEnumerator FloatAndFade(RectTransform rt, Text txt, Outline outline)
    {
        float duration = 1.2f;
        float elapsed = 0f;
        Vector3 startPos = rt.position;
        Color startColor = txt.color;
        Color startOutline = outline.effectColor;

        while (elapsed < duration)
        {
            elapsed += Time.deltaTime;
            float t = elapsed / duration;

            // Rise up
            rt.position = startPos + Vector3.up * (80f * t);

            // Fade out in second half
            float alpha = t < 0.5f ? 1f : 1f - (t - 0.5f) / 0.5f;
            txt.color = new Color(startColor.r, startColor.g, startColor.b, alpha);
            outline.effectColor = new Color(0, 0, 0, alpha);

            yield return null;
        }

        Destroy(rt.gameObject);
    }

    void OnUpgrade(int path)
    {
        if (_selectedTower == null) return;
        var data = _selectedTower.GetComponent<TowerData>();
        if (data == null) return;

        int previousInvestment = data.totalInvested;

        if (path == 1 && data.towerType == "tack000" && data.upgradePath1Level == 0
            && tack100Prefab != null)
        {
            if (!TowerCosts.TryGetUpgrade(data.towerType, 0, data.upgradePath1Level, out var upgradeInfo)) return;
            if (EconomyManager.Instance == null || !EconomyManager.Instance.TrySpend(upgradeInfo.cost)) return;

            Vector3 pos = _selectedTower.transform.position;
            Quaternion rot = _selectedTower.transform.rotation;

            Deselect();
            Destroy(data.gameObject);

            GameObject newTower = Instantiate(tack100Prefab, pos, rot);
            newTower.name = "tack100";

            // Collider for click detection
            if (newTower.GetComponentInChildren<Collider>() == null)
            {
                var col = newTower.AddComponent<BoxCollider>();
                Bounds bounds = new Bounds(newTower.transform.position, Vector3.zero);
                foreach (var r in newTower.GetComponentsInChildren<Renderer>())
                    bounds.Encapsulate(r.bounds);
                col.center = newTower.transform.InverseTransformPoint(bounds.center);
                col.size = bounds.size;
            }

            // Tower data
            var nd = newTower.AddComponent<TowerData>();
            nd.towerType = "tack100";
            nd.upgradePath1Level = 1;
            nd.totalInvested = previousInvestment + upgradeInfo.cost;

            // Attack with fireballs that apply burn
            var attack = newTower.AddComponent<TackAttack>();
            attack.damage = 0;
            attack.useFireball = true;

            Select(newTower);
        }

        if (path == 2 && data.towerType == "tack000" && data.upgradePath2Level == 0
            && tack010Prefab != null)
        {
            if (!TowerCosts.TryGetUpgrade(data.towerType, 1, data.upgradePath2Level, out var upgradeInfo)) return;
            if (EconomyManager.Instance == null || !EconomyManager.Instance.TrySpend(upgradeInfo.cost)) return;

            Vector3 pos = _selectedTower.transform.position;
            Quaternion rot = _selectedTower.transform.rotation;

            Deselect();
            Destroy(data.gameObject);

            GameObject newTower = Instantiate(tack010Prefab, pos, rot);
            newTower.name = "tack010";

            // Collider for click detection
            if (newTower.GetComponentInChildren<Collider>() == null)
            {
                var col = newTower.AddComponent<BoxCollider>();
                Bounds bounds = new Bounds(newTower.transform.position, Vector3.zero);
                foreach (var r in newTower.GetComponentsInChildren<Renderer>())
                    bounds.Encapsulate(r.bounds);
                col.center = newTower.transform.InverseTransformPoint(bounds.center);
                col.size = bounds.size;
            }

            // Tower data
            var nd = newTower.AddComponent<TowerData>();
            nd.towerType = "tack010";
            nd.upgradePath2Level = 1;
            nd.totalInvested = previousInvestment + upgradeInfo.cost;

            // Attack with air puffs
            var attack = newTower.AddComponent<TackAttack>();
            attack.damage = 1;
            attack.diskColor = new Color(0.7f, 0.88f, 1.0f, 0.6f);
            attack.diskMetallic = 0f;
            attack.diskSmoothness = 0.1f;
            attack.projectileSpeed = 0.12f;
            attack.useAirPuff = true;
            attack.pierce = 2;

            Select(newTower);
        }

        if (path == 3 && data.towerType == "tack000" && data.upgradePath3Level == 0
            && tack001Prefab != null)
        {
            if (!TowerCosts.TryGetUpgrade(data.towerType, 2, data.upgradePath3Level, out var upgradeInfo)) return;
            if (EconomyManager.Instance == null || !EconomyManager.Instance.TrySpend(upgradeInfo.cost)) return;

            Vector3 pos = _selectedTower.transform.position;
            Quaternion rot = _selectedTower.transform.rotation;

            Deselect();
            Destroy(data.gameObject);

            GameObject newTower = Instantiate(tack001Prefab, pos, rot);
            newTower.name = "tack001";

            // Collider for click detection
            if (newTower.GetComponentInChildren<Collider>() == null)
            {
                var col = newTower.AddComponent<BoxCollider>();
                Bounds bounds = new Bounds(newTower.transform.position, Vector3.zero);
                foreach (var r in newTower.GetComponentsInChildren<Renderer>())
                    bounds.Encapsulate(r.bounds);
                col.center = newTower.transform.InverseTransformPoint(bounds.center);
                col.size = bounds.size;
            }

            // Tower data
            var nd = newTower.AddComponent<TowerData>();
            nd.towerType = "tack001";
            nd.upgradePath3Level = 1;
            nd.totalInvested = previousInvestment + upgradeInfo.cost;

            // Nature attack - launches orbit trees onto the path
            var attack = newTower.AddComponent<NatureAttack>();
            attack.range = 3f;
            attack.cooldown = 1f;
            attack.damage = 1;
            attack.treeLifetime = 10f;

            Select(newTower);
        }
    }
}
