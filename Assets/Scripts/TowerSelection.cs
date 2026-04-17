using System.Collections.Generic;
using UnityEngine;
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

    private Dictionary<string, GameObject> _upgradePrefabs;
    private Dictionary<string, System.Action<GameObject>> _upgradeSetup;

    void Start()
    {
        _outlineMaterial = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        _outlineMaterial.SetColor("_BaseColor", Color.white);
        _outlineMaterial.SetFloat("_Cull", 1f);

        _upgradePrefabs = new Dictionary<string, GameObject>
        {
            { "tack100", tack100Prefab },
            { "tack010", tack010Prefab },
            { "tack001", tack001Prefab },
        };

        _upgradeSetup = new Dictionary<string, System.Action<GameObject>>
        {
            { "tack100", tower =>
                {
                    var attack = tower.AddComponent<TackAttack>();
                    attack.damage = 0;
                    attack.useFireball = true;
                }
            },
            { "tack010", tower =>
                {
                    var attack = tower.AddComponent<TackAttack>();
                    attack.damage = 1;
                    attack.diskColor = new Color(0.7f, 0.88f, 1.0f, 0.6f);
                    attack.diskMetallic = 0f;
                    attack.diskSmoothness = 0.1f;
                    attack.projectileSpeed = 0.12f;
                    attack.useAirPuff = true;
                    attack.pierce = 2;
                }
            },
            { "tack001", tower =>
                {
                    var attack = tower.AddComponent<NatureAttack>();
                    attack.range = 3f;
                    attack.cooldown = 1f;
                    attack.damage = 1;
                    attack.treeLifetime = 10f;
                }
            },
        };

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
            float closestScreenDist = 50f;
            foreach (var td in FindObjectsByType<TowerData>(FindObjectsSortMode.None))
            {
                Vector3 screenPt = cam.WorldToScreenPoint(td.transform.position);
                if (screenPt.z < 0) continue;
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
        var attack = _selectedTower.GetComponent<ITowerAttack>();
        if (attack == null) return;
        float range = attack.Range;
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
            bool hasPrefab = available && _upgradePrefabs.TryGetValue(info.resultType, out var prefab) && prefab != null;
            buttons[i].interactable = available && canAfford && hasPrefab;

            var txt = buttons[i].GetComponentInChildren<Text>();
            if (available)
                txt.text = $"Path {i + 1} (${info.cost})";
            else
                txt.text = $"Path {i + 1}";
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
            FloatingText.Spawn(worldPos, $"+${refund}", new Color(1f, 0.85f, 0.1f), 1.2f, 28, true, 80f);
        }

        Destroy(tower);
    }

    void OnUpgrade(int path)
    {
        if (_selectedTower == null) return;
        var data = _selectedTower.GetComponent<TowerData>();
        if (data == null) return;

        int pathIndex = path - 1;
        int currentLevel = pathIndex == 0 ? data.upgradePath1Level
                         : pathIndex == 1 ? data.upgradePath2Level
                         : data.upgradePath3Level;

        if (!TowerCosts.TryGetUpgrade(data.towerType, pathIndex, currentLevel, out var upgradeInfo)) return;
        if (!_upgradePrefabs.TryGetValue(upgradeInfo.resultType, out var prefab) || prefab == null) return;
        if (EconomyManager.Instance == null || !EconomyManager.Instance.TrySpend(upgradeInfo.cost)) return;

        int previousInvestment = data.totalInvested;
        Vector3 pos = _selectedTower.transform.position;
        Quaternion rot = _selectedTower.transform.rotation;

        Deselect();
        Destroy(data.gameObject);

        GameObject newTower = Instantiate(prefab, pos, rot);
        newTower.name = upgradeInfo.resultType;

        TowerUtils.EnsureCollider(newTower);

        var nd = newTower.AddComponent<TowerData>();
        nd.towerType = upgradeInfo.resultType;
        if (pathIndex == 0) nd.upgradePath1Level = currentLevel + 1;
        else if (pathIndex == 1) nd.upgradePath2Level = currentLevel + 1;
        else nd.upgradePath3Level = currentLevel + 1;
        nd.totalInvested = previousInvestment + upgradeInfo.cost;

        if (_upgradeSetup.TryGetValue(upgradeInfo.resultType, out var setup))
            setup(newTower);

        Select(newTower);
    }
}
