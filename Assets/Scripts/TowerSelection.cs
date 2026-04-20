using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

public class TowerSelection : MonoBehaviour
{
    [Header("Upgrade Prefabs")]
    public GameObject tack100Prefab;
    public GameObject tack200Prefab;
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
    private Text _statsText;
    private Button _upgrade1Button;
    private Button _upgrade2Button;
    private Button _upgrade3Button;
    private Image _upgrade1Icon;
    private Image _upgrade2Icon;
    private Image _upgrade3Icon;

    // Hero layout fields
    private GameObject _heroLayoutRoot;
    private Text _heroNameText;
    private Text _heroLevelText;
    private Image _heroXpBarFill;
    private Text _heroPassiveText;
    private Button _heroActive1Button;
    private Image _heroActive1Cooldown;
    private GameObject _heroActive1Lock;
    private Text _heroActive1LockText;
    private Button _heroActive2Button;
    private Image _heroActive2Cooldown;
    private GameObject _heroActive2Lock;
    private Text _heroActive2LockText;
    private Button _heroSellButton;
    private Button _heroLevelUpButton;
    private Text _heroStatsText;
    private GameObject _towerLayoutRoot;

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
            { "tack200", tack200Prefab },
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
            { "tack200", tower =>
                {
                    var attack = tower.AddComponent<TackAttack>();
                    attack.range = 2f;
                    attack.damage = 3;
                    attack.pierce = 20;
                    attack.useAreaPulse = true;
                    attack.applyBurn = true;
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

        if (_selectedTower != null)
            RefreshButtons();

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

        TowerData foundTower = null;
        Hero foundHero = null;
        float bestDist = float.MaxValue;

        RaycastHit[] hits = Physics.RaycastAll(ray, 500f);
        foreach (var h in hits)
        {
            var data = h.collider.GetComponentInParent<TowerData>();
            var hero = h.collider.GetComponentInParent<Hero>();
            if (hero != null && h.distance < bestDist)
            {
                bestDist = h.distance;
                foundHero = hero;
                foundTower = null;
            }
            else if (data != null && h.distance < bestDist && foundHero == null)
            {
                bestDist = h.distance;
                foundTower = data;
            }
        }

        if (foundTower == null && foundHero == null)
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
            foreach (var h in FindObjectsByType<Hero>(FindObjectsSortMode.None))
            {
                Vector3 screenPt = cam.WorldToScreenPoint(h.transform.position);
                if (screenPt.z < 0) continue;
                float dist = Vector2.Distance(mousePos, new Vector2(screenPt.x, screenPt.y));
                if (dist < closestScreenDist)
                {
                    closestScreenDist = dist;
                    foundHero = h;
                    foundTower = null;
                }
            }
        }

        if (foundHero != null)
        {
            Select(foundHero.gameObject);
            return;
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

    public void Select(GameObject selected)
    {
        if (_selectedTower == selected) return;
        Deselect();
        _selectedTower = selected;
        AddOutline();
        ShowRangeIndicator();
        _actionPanel.SetActive(true);

        bool isHero = selected.GetComponent<Hero>() != null;
        _towerLayoutRoot.SetActive(!isHero);
        _heroLayoutRoot.SetActive(isHero);

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
        _panelCanvas = new GameObject("SelectionUI");
        var canvas = _panelCanvas.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 10;

        var scaler = _panelCanvas.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920, 1080);

        _panelCanvas.AddComponent<GraphicRaycaster>();

        _actionPanel = new GameObject("ActionPanel");
        _actionPanel.transform.SetParent(_panelCanvas.transform, false);

        var prt = _actionPanel.AddComponent<RectTransform>();
        prt.anchorMin = new Vector2(1, 0.3f);
        prt.anchorMax = new Vector2(1, 0.7f);
        prt.pivot = new Vector2(1, 0.5f);
        prt.anchoredPosition = Vector2.zero;
        prt.sizeDelta = new Vector2(220, 0);

        _actionPanel.AddComponent<Image>().color = new Color(0.627f, 0.322f, 0.176f, 0.95f);

        _towerLayoutRoot = BuildTowerLayout(_actionPanel.transform);
        _heroLayoutRoot = BuildHeroLayout(_actionPanel.transform);
        _heroLayoutRoot.SetActive(false);

        _actionPanel.SetActive(false);
    }

    GameObject BuildTowerLayout(Transform parent)
    {
        var root = new GameObject("TowerLayout");
        root.transform.SetParent(parent, false);
        var rt = root.AddComponent<RectTransform>();
        rt.anchorMin = Vector2.zero;
        rt.anchorMax = Vector2.one;
        rt.offsetMin = Vector2.zero;
        rt.offsetMax = Vector2.zero;

        var layout = root.AddComponent<VerticalLayoutGroup>();
        layout.padding = new RectOffset(10, 10, 10, 10);
        layout.spacing = 8;
        layout.childForceExpandWidth = true;
        layout.childForceExpandHeight = false;
        layout.childAlignment = TextAnchor.UpperCenter;

        _sellButton = MakeButton("Sell", root.transform, new Color(0.7f, 0.15f, 0.15f));
        _sellButton.onClick.AddListener(OnSell);

        _statsText = MakeStatsBlock(root.transform);

        MakeLabel("-- Upgrades --", root.transform);

        Color btnColor = new Color(0.545f, 0.271f, 0.075f);

        _upgrade1Button = MakeUpgradeButton("Path 1", root.transform, btnColor, "UI/tack100_icon", out _upgrade1Icon);
        _upgrade1Button.onClick.AddListener(() => OnUpgrade(1));

        _upgrade2Button = MakeUpgradeButton("Path 2", root.transform, btnColor, "UI/tack010_icon", out _upgrade2Icon);
        _upgrade2Button.onClick.AddListener(() => OnUpgrade(2));

        _upgrade3Button = MakeUpgradeButton("Path 3", root.transform, btnColor, "UI/tack001_icon", out _upgrade3Icon);
        _upgrade3Button.onClick.AddListener(() => OnUpgrade(3));

        return root;
    }

    GameObject BuildHeroLayout(Transform parent)
    {
        var root = new GameObject("HeroLayout");
        root.transform.SetParent(parent, false);
        var rt = root.AddComponent<RectTransform>();
        rt.anchorMin = Vector2.zero;
        rt.anchorMax = Vector2.one;
        rt.offsetMin = Vector2.zero;
        rt.offsetMax = Vector2.zero;

        var layout = root.AddComponent<VerticalLayoutGroup>();
        layout.padding = new RectOffset(10, 10, 10, 10);
        layout.spacing = 6;
        layout.childForceExpandWidth = true;
        layout.childForceExpandHeight = false;
        layout.childAlignment = TextAnchor.UpperCenter;

        _heroNameText = MakeHeroText("NameText", root.transform, 20, Color.white, 30);
        _heroLevelText = MakeHeroText("LevelText", root.transform, 14, new Color(1f, 0.85f, 0.3f), 20);

        var xpBar = new GameObject("XpBar");
        xpBar.transform.SetParent(root.transform, false);
        xpBar.AddComponent<LayoutElement>().preferredHeight = 10;
        var xpBg = xpBar.AddComponent<Image>();
        xpBg.color = new Color(0.1f, 0.1f, 0.1f, 0.8f);

        var xpFill = new GameObject("Fill");
        xpFill.transform.SetParent(xpBar.transform, false);
        _heroXpBarFill = xpFill.AddComponent<Image>();
        _heroXpBarFill.color = new Color(0.9f, 0.75f, 0.2f);
        var frt = xpFill.GetComponent<RectTransform>();
        frt.anchorMin = Vector2.zero;
        frt.anchorMax = new Vector2(0f, 1f);
        frt.pivot = new Vector2(0f, 0.5f);
        frt.offsetMin = Vector2.zero;
        frt.offsetMax = Vector2.zero;

        _heroLevelUpButton = MakeButton("Level Up", root.transform, new Color(0.2f, 0.45f, 0.75f));
        _heroLevelUpButton.onClick.AddListener(OnHeroLevelUp);

        _heroStatsText = MakeStatsBlock(root.transform);

        MakeLabel("-- Passive --", root.transform);
        _heroPassiveText = MakeHeroText("PassiveText", root.transform, 12, new Color(1f, 1f, 1f, 0.9f), 48);
        _heroPassiveText.alignment = TextAnchor.UpperCenter;

        MakeLabel("-- Abilities --", root.transform);

        (_heroActive1Button, _heroActive1Cooldown, _heroActive1Lock, _heroActive1LockText) =
            MakeHeroAbilityButton("Active 1", root.transform, 0);
        (_heroActive2Button, _heroActive2Cooldown, _heroActive2Lock, _heroActive2LockText) =
            MakeHeroAbilityButton("Active 2", root.transform, 1);

        _heroSellButton = MakeButton("Sell", root.transform, new Color(0.7f, 0.15f, 0.15f));
        _heroSellButton.onClick.AddListener(OnHeroSell);

        return root;
    }

    Text MakeHeroText(string name, Transform parent, int fontSize, Color color, float height)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var t = go.AddComponent<Text>();
        t.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        t.alignment = TextAnchor.MiddleCenter;
        t.color = color;
        t.fontSize = fontSize;
        go.AddComponent<LayoutElement>().preferredHeight = height;
        return t;
    }

    (Button, Image, GameObject, Text) MakeHeroAbilityButton(string label, Transform parent, int index)
    {
        var go = new GameObject(label);
        go.transform.SetParent(parent, false);
        go.AddComponent<LayoutElement>().preferredHeight = 45;

        var bg = go.AddComponent<Image>();
        bg.color = new Color(0.25f, 0.1f, 0.1f);

        var btn = go.AddComponent<Button>();
        int captured = index;
        btn.onClick.AddListener(() => {
            if (HeroManager.Instance != null) HeroManager.Instance.CastAbility(captured);
        });
        ColorBlock cb = btn.colors;
        cb.normalColor = Color.white;
        cb.highlightedColor = new Color(1.2f, 1.2f, 1.2f, 1f);
        cb.pressedColor = new Color(0.8f, 0.8f, 0.8f, 1f);
        cb.disabledColor = new Color(0.5f, 0.5f, 0.5f, 0.5f);
        btn.colors = cb;

        var txt = new GameObject("Text");
        txt.transform.SetParent(go.transform, false);
        var t = txt.AddComponent<Text>();
        t.text = label;
        t.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        t.alignment = TextAnchor.MiddleCenter;
        t.color = Color.white;
        t.fontSize = 15;
        var trt = txt.GetComponent<RectTransform>();
        trt.anchorMin = Vector2.zero;
        trt.anchorMax = Vector2.one;
        trt.offsetMin = Vector2.zero;
        trt.offsetMax = Vector2.zero;

        var cdGO = new GameObject("Cooldown");
        cdGO.transform.SetParent(go.transform, false);
        var cdImg = cdGO.AddComponent<Image>();
        cdImg.color = new Color(0f, 0f, 0f, 0.6f);
        cdImg.type = Image.Type.Filled;
        cdImg.fillMethod = Image.FillMethod.Radial360;
        cdImg.fillOrigin = (int)Image.Origin360.Top;
        cdImg.fillClockwise = true;
        cdImg.fillAmount = 0f;
        cdImg.raycastTarget = false;
        var cdRT = cdGO.GetComponent<RectTransform>();
        cdRT.anchorMin = Vector2.zero;
        cdRT.anchorMax = Vector2.one;
        cdRT.offsetMin = Vector2.zero;
        cdRT.offsetMax = Vector2.zero;

        var cdTxtGO = new GameObject("CooldownText");
        cdTxtGO.transform.SetParent(cdGO.transform, false);
        var cdTxt = cdTxtGO.AddComponent<Text>();
        cdTxt.text = "";
        cdTxt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        cdTxt.alignment = TextAnchor.MiddleCenter;
        cdTxt.color = Color.white;
        cdTxt.fontSize = 20;
        cdTxt.fontStyle = FontStyle.Bold;
        cdTxt.raycastTarget = false;
        var cdTxtOutline = cdTxtGO.AddComponent<Outline>();
        cdTxtOutline.effectColor = Color.black;
        cdTxtOutline.effectDistance = new Vector2(1, -1);
        var cdTxtRT = cdTxtGO.GetComponent<RectTransform>();
        cdTxtRT.anchorMin = Vector2.zero;
        cdTxtRT.anchorMax = Vector2.one;
        cdTxtRT.offsetMin = Vector2.zero;
        cdTxtRT.offsetMax = Vector2.zero;

        var lockGO = new GameObject("Lock");
        lockGO.transform.SetParent(go.transform, false);
        var lockImg = lockGO.AddComponent<Image>();
        lockImg.color = new Color(0f, 0f, 0f, 0.75f);
        lockImg.raycastTarget = false;
        var lockRT = lockGO.GetComponent<RectTransform>();
        lockRT.anchorMin = Vector2.zero;
        lockRT.anchorMax = Vector2.one;
        lockRT.offsetMin = Vector2.zero;
        lockRT.offsetMax = Vector2.zero;

        var lockTxt = new GameObject("LockText");
        lockTxt.transform.SetParent(lockGO.transform, false);
        var lt = lockTxt.AddComponent<Text>();
        lt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        lt.alignment = TextAnchor.MiddleCenter;
        lt.color = Color.white;
        lt.fontSize = 16;
        lt.fontStyle = FontStyle.Bold;
        var ltRT = lockTxt.GetComponent<RectTransform>();
        ltRT.anchorMin = Vector2.zero;
        ltRT.anchorMax = Vector2.one;
        ltRT.offsetMin = Vector2.zero;
        ltRT.offsetMax = Vector2.zero;

        return (btn, cdImg, lockGO, lt);
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

    Text MakeStatsBlock(Transform parent)
    {
        var go = new GameObject("Stats");
        go.transform.SetParent(parent, false);

        var bg = go.AddComponent<Image>();
        bg.color = new Color(0f, 0f, 0f, 0.25f);

        go.AddComponent<LayoutElement>().preferredHeight = 52;

        var txtGO = new GameObject("Text");
        txtGO.transform.SetParent(go.transform, false);
        var txt = txtGO.AddComponent<Text>();
        txt.text = "Kills: 0\nDamage: 0";
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.alignment = TextAnchor.MiddleCenter;
        txt.color = Color.white;
        txt.fontSize = 16;
        txt.fontStyle = FontStyle.Bold;
        txt.raycastTarget = false;
        var outline = txtGO.AddComponent<Outline>();
        outline.effectColor = Color.black;
        outline.effectDistance = new Vector2(1, -1);
        var rt = txtGO.GetComponent<RectTransform>();
        rt.anchorMin = Vector2.zero;
        rt.anchorMax = Vector2.one;
        rt.offsetMin = new Vector2(4, 2);
        rt.offsetMax = new Vector2(-4, -2);
        return txt;
    }

    void RefreshButtons()
    {
        if (_selectedTower == null) return;

        Hero hero = _selectedTower.GetComponent<Hero>();
        if (hero != null)
        {
            RefreshHeroButtons(hero);
            return;
        }

        var data = _selectedTower.GetComponent<TowerData>();
        if (data == null) return;

        var sellTxt = _sellButton.GetComponentInChildren<Text>();
        sellTxt.text = $"Sell (${data.SellValue})";

        if (_statsText != null)
            _statsText.text = $"Kills: {data.killCount}\nDamage: {data.totalDamage}";

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

    void RefreshHeroButtons(Hero hero)
    {
        _heroNameText.text = hero.heroType == "knight000" ? "Silent Knight" : hero.heroType;
        _heroLevelText.text = hero.level >= 10 ? "Level 10 (MAX)" : $"Level {hero.level}";

        if (hero.level >= 10)
        {
            _heroXpBarFill.rectTransform.anchorMax = new Vector2(1f, 1f);
        }
        else
        {
            int cur = hero.XpTowardNextLevel();
            int req = Mathf.Max(1, hero.XpRequiredForNextLevel());
            float ratio = Mathf.Clamp01(cur / (float)req);
            _heroXpBarFill.rectTransform.anchorMax = new Vector2(ratio, 1f);
        }

        _heroPassiveText.text = hero.passive != null
            ? $"{hero.passive.name}\n{hero.passive.description}"
            : "";

        if (_heroStatsText != null)
            _heroStatsText.text = $"Kills: {hero.killCount}\nDamage: {hero.totalDamage}";

        UpdateHeroLevelUpButton(hero);

        UpdateHeroAbilityButton(hero, hero.active1, _heroActive1Button, _heroActive1Cooldown, _heroActive1Lock, _heroActive1LockText);
        UpdateHeroAbilityButton(hero, hero.active2, _heroActive2Button, _heroActive2Cooldown, _heroActive2Lock, _heroActive2LockText);

        var sellTxt = _heroSellButton.GetComponentInChildren<Text>();
        int sellValue = HeroData.GetSellValue(hero.heroType);
        sellTxt.text = $"Sell (${sellValue})";
    }

    void UpdateHeroLevelUpButton(Hero hero)
    {
        if (_heroLevelUpButton == null) return;
        var txt = _heroLevelUpButton.GetComponentInChildren<Text>();

        if (hero.level >= 10)
        {
            txt.text = "Max Level";
            _heroLevelUpButton.interactable = false;
            return;
        }

        int remaining = Mathf.Max(0, hero.XpRequiredForNextLevel() - hero.XpTowardNextLevel());
        int cost = Mathf.Max(1, remaining / 10);
        txt.text = $"Level Up (${cost})";
        _heroLevelUpButton.interactable = EconomyManager.Instance != null && EconomyManager.Instance.CanAfford(cost);
    }

    void UpdateHeroAbilityButton(Hero hero, HeroAbility a, Button btn, Image cooldownFill, GameObject lockGO, Text lockTxt)
    {
        Text cdText = cooldownFill != null ? cooldownFill.transform.Find("CooldownText")?.GetComponent<Text>() : null;

        if (a == null)
        {
            btn.interactable = false;
            lockGO.SetActive(true);
            lockTxt.text = "—";
            cooldownFill.fillAmount = 0f;
            if (cdText != null) cdText.text = "";
            return;
        }

        var btnLabel = btn.transform.Find("Text")?.GetComponent<Text>();
        if (btnLabel != null) btnLabel.text = a.name;

        bool unlocked = a.IsUnlocked(hero.level);
        lockGO.SetActive(!unlocked);
        lockTxt.text = unlocked ? "" : $"L{a.unlockLevel}";

        float remaining = a.CooldownRemaining();
        cooldownFill.fillAmount = a.cooldown > 0f ? Mathf.Clamp01(remaining / a.cooldown) : 0f;

        if (cdText != null)
            cdText.text = remaining > 0.05f ? (remaining >= 10f ? Mathf.CeilToInt(remaining).ToString() : remaining.ToString("F1")) : "";

        btn.interactable = unlocked && remaining <= 0f;
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

    void OnHeroSell()
    {
        if (_selectedTower == null) return;
        Hero hero = _selectedTower.GetComponent<Hero>();
        if (hero == null) return;

        int refund = HeroData.GetSellValue(hero.heroType);
        Vector3 worldPos = hero.transform.position;

        if (HeroManager.Instance != null)
            HeroManager.Instance.UnregisterHero(hero);

        GameObject go = hero.gameObject;
        Deselect();

        if (refund > 0 && EconomyManager.Instance != null)
        {
            EconomyManager.Instance.money += refund;
            FloatingText.Spawn(worldPos, $"+${refund}", new Color(1f, 0.85f, 0.1f), 1.2f, 28, true, 80f);
        }

        Destroy(go);
    }

    void OnHeroLevelUp()
    {
        if (_selectedTower == null) return;
        Hero hero = _selectedTower.GetComponent<Hero>();
        if (hero == null) return;
        if (hero.level >= 10) return;

        int remaining = Mathf.Max(0, hero.XpRequiredForNextLevel() - hero.XpTowardNextLevel());
        int cost = Mathf.Max(1, remaining / 10);

        if (EconomyManager.Instance == null || !EconomyManager.Instance.TrySpend(cost)) return;

        hero.AddXp(remaining);
        FloatingText.Spawn(hero.transform.position, $"-${cost}", new Color(0.9f, 0.15f, 0.1f), 1.2f, 28, false, 80f);
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
