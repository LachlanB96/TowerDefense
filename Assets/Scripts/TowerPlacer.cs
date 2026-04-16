using System.Collections;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

public class TowerPlacer : MonoBehaviour
{
    [SerializeField] private GameObject _towerPrefab;
    [SerializeField] private GameObject _sniperPrefab;
    [SerializeField] private LayerMask _groundLayer;
    [SerializeField] private float _overlapRadius = 1.4f;

    [Header("Projectile Appearance")]
    [SerializeField] private Color _projectileColor = new Color(0.76f, 0.6f, 0.42f);
    [SerializeField] private float _projectileMetallic = 0f;
    [SerializeField] private float _projectileSmoothness = 0.2f;

    public bool IsPlacing => _isPlacing;

    private GameObject _preview;
    private GameObject _rangeIndicator;
    private bool _isPlacing;
    private bool _canPlace;
    private int _skipFrames;
    private Material[][] _originalMaterials;
    private Renderer[] _previewRenderers;
    private string _placingType = "tack000";

    // ── Dev Tools ──────────────────────────────────────
    private static readonly bool DEV_AUTO_PLACE = true;
    private static readonly Vector3 DEV_TACK_POS = new Vector3(13.96f, -0.05f, 8.70f);
    private static readonly Vector3 DEV_SNIPER_POS = new Vector3(10f, -0.05f, 6f);
    // ─────────────────────────────────────────────────────

    void Start()
    {
        // Hide the old scene button
        var oldBtn = GameObject.Find("PlaceTowerButton");
        if (oldBtn != null)
            oldBtn.SetActive(false);

        BuildShopPanel();

        if (DEV_AUTO_PLACE)
        {
            DevPlaceTack(DEV_TACK_POS);
            DevPlaceSniper(DEV_SNIPER_POS);
        }
    }

    void DevPlaceTack(Vector3 pos)
    {
        var tower = Instantiate(_towerPrefab);
        tower.name = "tack000";
        tower.transform.position = pos;

        foreach (var col in tower.GetComponentsInChildren<Collider>(true))
            col.enabled = true;

        if (tower.GetComponentInChildren<Collider>() == null)
        {
            Bounds bounds = new Bounds(tower.transform.position, Vector3.zero);
            foreach (var r in tower.GetComponentsInChildren<Renderer>())
                bounds.Encapsulate(r.bounds);
            BoxCollider box = tower.AddComponent<BoxCollider>();
            box.center = tower.transform.InverseTransformPoint(bounds.center);
            box.size = bounds.size;
        }

        TowerData data = tower.GetComponent<TowerData>() ?? tower.AddComponent<TowerData>();
        data.towerType = "tack000";
        data.totalInvested = 0;

        TackAttack attack = tower.GetComponent<TackAttack>() ?? tower.AddComponent<TackAttack>();
        attack.diskColor = _projectileColor;
        attack.diskMetallic = _projectileMetallic;
        attack.diskSmoothness = _projectileSmoothness;
    }

    void DevPlaceSniper(Vector3 pos)
    {
        if (_sniperPrefab == null) return;

        var tower = Instantiate(_sniperPrefab);
        tower.name = "sniper000";
        tower.transform.position = pos;

        foreach (var col in tower.GetComponentsInChildren<Collider>(true))
            col.enabled = true;

        if (tower.GetComponentInChildren<Collider>() == null)
        {
            Bounds bounds = new Bounds(tower.transform.position, Vector3.zero);
            foreach (var r in tower.GetComponentsInChildren<Renderer>())
                bounds.Encapsulate(r.bounds);
            BoxCollider box = tower.AddComponent<BoxCollider>();
            box.center = tower.transform.InverseTransformPoint(bounds.center);
            box.size = bounds.size;
        }

        TowerData data = tower.GetComponent<TowerData>() ?? tower.AddComponent<TowerData>();
        data.towerType = "sniper000";
        data.totalInvested = 0;

        if (tower.GetComponent<SniperIdle>() == null)
            tower.AddComponent<SniperIdle>();
        if (tower.GetComponent<SniperAttack>() == null)
            tower.AddComponent<SniperAttack>();
    }

    void BuildShopPanel()
    {
        // Canvas
        var canvasGO = new GameObject("ShopUI");
        var canvas = canvasGO.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 10;

        var scaler = canvasGO.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920, 1080);

        canvasGO.AddComponent<GraphicRaycaster>();

        // Panel anchored to left side (mirroring selection panel on right)
        var panel = new GameObject("ShopPanel");
        panel.transform.SetParent(canvasGO.transform, false);

        var prt = panel.AddComponent<RectTransform>();
        prt.anchorMin = new Vector2(0, 0.3f);
        prt.anchorMax = new Vector2(0, 0.7f);
        prt.pivot = new Vector2(0, 0.5f);
        prt.anchoredPosition = Vector2.zero;
        prt.sizeDelta = new Vector2(170, 0);

        panel.AddComponent<Image>().color = new Color(0.627f, 0.322f, 0.176f, 0.95f);

        var layout = panel.AddComponent<VerticalLayoutGroup>();
        layout.padding = new RectOffset(10, 10, 10, 10);
        layout.spacing = 8;
        layout.childForceExpandWidth = true;
        layout.childForceExpandHeight = false;
        layout.childAlignment = TextAnchor.UpperCenter;

        // Header
        MakeLabel("-- Towers --", panel.transform);

        // Tack tower icon button (large)
        MakeTowerButton("tack000", panel.transform);

        // Sniper tower icon button
        MakeTowerButton("sniper000", panel.transform);
    }

    void MakeTowerButton(string towerType, Transform parent)
    {
        int cost = TowerCosts.GetPlacementCost(towerType);
        string iconName = towerType == "sniper000" ? "UI/sniper_icon" : "UI/tack_icon";
        Sprite iconSprite = Resources.Load<Sprite>(iconName);

        // Button container
        var go = new GameObject("TowerBtn_" + towerType);
        go.transform.SetParent(parent, false);

        go.AddComponent<LayoutElement>().preferredHeight = 150;

        var btn = go.AddComponent<Button>();
        string capturedType = towerType;
        btn.onClick.AddListener(() => BeginPlacement(capturedType));

        ColorBlock cb = btn.colors;
        cb.normalColor = Color.white;
        cb.highlightedColor = new Color(1.2f, 1.2f, 1.2f, 1f);
        cb.pressedColor = new Color(0.8f, 0.8f, 0.8f, 1f);
        btn.colors = cb;

        // Background
        var bg = go.AddComponent<Image>();
        bg.color = new Color(0.545f, 0.271f, 0.075f);

        // Icon image (fills most of the button)
        var iconGO = new GameObject("Icon");
        iconGO.transform.SetParent(go.transform, false);

        var iconImg = iconGO.AddComponent<Image>();
        if (iconSprite != null)
        {
            iconImg.sprite = iconSprite;
            iconImg.preserveAspect = true;
        }
        iconImg.color = Color.white;

        var iconRT = iconGO.GetComponent<RectTransform>();
        iconRT.anchorMin = new Vector2(0.05f, 0.2f);
        iconRT.anchorMax = new Vector2(0.95f, 0.95f);
        iconRT.offsetMin = Vector2.zero;
        iconRT.offsetMax = Vector2.zero;

        // Price label at the bottom
        var priceGO = new GameObject("PriceLabel");
        priceGO.transform.SetParent(go.transform, false);

        var priceTxt = priceGO.AddComponent<Text>();
        priceTxt.text = $"${cost}";
        priceTxt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        priceTxt.fontSize = 20;
        priceTxt.color = Color.white;
        priceTxt.alignment = TextAnchor.MiddleCenter;
        priceTxt.fontStyle = FontStyle.Bold;

        var outline = priceGO.AddComponent<Outline>();
        outline.effectColor = Color.black;
        outline.effectDistance = new Vector2(1, -1);

        var priceRT = priceGO.GetComponent<RectTransform>();
        priceRT.anchorMin = new Vector2(0, 0);
        priceRT.anchorMax = new Vector2(1, 0.22f);
        priceRT.offsetMin = Vector2.zero;
        priceRT.offsetMax = Vector2.zero;
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

    public void BeginPlacement(string towerType = "tack000")
    {
        if (_isPlacing) return;
        _placingType = towerType;
        SpawnPreview();
    }

    GameObject GetPrefab(string towerType)
    {
        if (towerType == "sniper000" && _sniperPrefab != null) return _sniperPrefab;
        return _towerPrefab;
    }

    float GetTowerRange(string towerType)
    {
        return towerType == "sniper000" ? 7f : 3f;
    }

    void SpawnPreview()
    {
        _isPlacing = true;
        _skipFrames = 2;
        _canPlace = false;

        _preview = Instantiate(GetPrefab(_placingType));
        _preview.name = _placingType + "_preview";

        foreach (var col in _preview.GetComponentsInChildren<Collider>())
            col.enabled = false;

        // Save original materials before modifying
        _previewRenderers = _preview.GetComponentsInChildren<Renderer>();
        _originalMaterials = new Material[_previewRenderers.Length][];
        for (int i = 0; i < _previewRenderers.Length; i++)
            _originalMaterials[i] = _previewRenderers[i].sharedMaterials;

        SetPreviewColor(new Color(1f, 1f, 1f, 0.4f));

        _rangeIndicator = RangeIndicator.Create(GetTowerRange(_placingType), _preview.transform);
    }

    void Update()
    {
        if (!_isPlacing || _preview == null) return;

        var mouse = Mouse.current;
        if (mouse == null) return;

        if (_skipFrames > 0)
        {
            _skipFrames--;
            return;
        }

        Ray ray = Camera.main.ScreenPointToRay(mouse.position.ReadValue());
        if (Physics.Raycast(ray, out RaycastHit hit, 500f, _groundLayer))
        {
            _preview.transform.position = hit.point;
            _canPlace = !CheckOverlap(hit.point);
            SetPreviewColor(_canPlace ? new Color(1f, 1f, 1f, 0.4f) : new Color(1f, 0.15f, 0.15f, 0.5f));
        }
        else
        {
            _canPlace = false;
        }

        if (mouse.leftButton.wasPressedThisFrame && _canPlace)
        {
            int cost = TowerCosts.GetPlacementCost(_placingType);
            if (EconomyManager.Instance == null || !EconomyManager.Instance.TrySpend(cost))
                return;

            PlaceTower();

            if (Keyboard.current.leftShiftKey.isPressed || Keyboard.current.rightShiftKey.isPressed)
                SpawnPreview();
        }

        if (mouse.rightButton.wasPressedThisFrame)
        {
            CancelPlacement();
        }
    }

    bool CheckOverlap(Vector3 position)
    {
        Collider[] hits = Physics.OverlapSphere(position, _overlapRadius);
        foreach (var col in hits)
        {
            if (col.transform.IsChildOf(_preview.transform)) continue;
            if (col.gameObject.layer == 8) continue; // Ground layer
            return true;
        }

        if (IsOnPath(position)) return true;

        return false;
    }

    bool IsOnPath(Vector3 position)
    {
        var pathRenderer = FindAnyObjectByType<PathRenderer>();
        if (pathRenderer == null) return false;

        var waypoints = pathRenderer.Waypoints;
        float pathWidth = pathRenderer.PathWidth;
        if (waypoints == null || waypoints.childCount < 2) return false;

        float halfWidth = pathWidth / 2f + _overlapRadius;
        Vector2 pos2D = new Vector2(position.x, position.z);

        for (int i = 0; i < waypoints.childCount - 1; i++)
        {
            Vector3 a = waypoints.GetChild(i).position;
            Vector3 b = waypoints.GetChild(i + 1).position;
            Vector2 a2 = new Vector2(a.x, a.z);
            Vector2 b2 = new Vector2(b.x, b.z);

            float dist = DistanceToSegment(pos2D, a2, b2);
            if (dist < halfWidth) return true;
        }
        return false;
    }

    float DistanceToSegment(Vector2 p, Vector2 a, Vector2 b)
    {
        Vector2 ab = b - a;
        float t = Mathf.Clamp01(Vector2.Dot(p - a, ab) / ab.sqrMagnitude);
        Vector2 closest = a + ab * t;
        return Vector2.Distance(p, closest);
    }

    void PlaceTower()
    {
        // Remove range indicator before placing
        if (_rangeIndicator != null)
        {
            Destroy(_rangeIndicator);
            _rangeIndicator = null;
        }

        _preview.name = _placingType;

        foreach (var col in _preview.GetComponentsInChildren<Collider>(true))
            col.enabled = true;

        // Ensure tower has a collider for click detection
        if (_preview.GetComponentInChildren<Collider>() == null)
        {
            Bounds bounds = new Bounds(_preview.transform.position, Vector3.zero);
            foreach (var r in _preview.GetComponentsInChildren<Renderer>())
                bounds.Encapsulate(r.bounds);
            BoxCollider box = _preview.AddComponent<BoxCollider>();
            box.center = _preview.transform.InverseTransformPoint(bounds.center);
            box.size = bounds.size;
        }

        // Restore original materials (with Blender colors)
        for (int i = 0; i < _previewRenderers.Length; i++)
            _previewRenderers[i].sharedMaterials = _originalMaterials[i];

        // Tower data for selection system
        TowerData data = _preview.GetComponent<TowerData>();
        if (data == null)
            data = _preview.AddComponent<TowerData>();
        data.towerType = _placingType;
        int cost = TowerCosts.GetPlacementCost(_placingType);
        data.totalInvested = cost;

        SpawnCostText(_preview.transform.position, cost);

        // Attack behavior depends on tower type
        if (_placingType == "sniper000")
        {
            if (_preview.GetComponent<SniperIdle>() == null)
                _preview.AddComponent<SniperIdle>();
            if (_preview.GetComponent<SniperAttack>() == null)
                _preview.AddComponent<SniperAttack>();
        }
        else
        {
            TackAttack attack = _preview.GetComponent<TackAttack>();
            if (attack == null)
                attack = _preview.AddComponent<TackAttack>();
            attack.diskColor = _projectileColor;
            attack.diskMetallic = _projectileMetallic;
            attack.diskSmoothness = _projectileSmoothness;
        }

        _preview = null;
        _previewRenderers = null;
        _originalMaterials = null;
        _isPlacing = false;
    }

    void CancelPlacement()
    {
        if (_rangeIndicator != null)
        {
            Destroy(_rangeIndicator);
            _rangeIndicator = null;
        }
        if (_preview != null)
            Destroy(_preview);
        _preview = null;
        _isPlacing = false;
    }

    void SetPreviewColor(Color tint)
    {
        foreach (var r in _preview.GetComponentsInChildren<Renderer>())
        {
            foreach (var mat in r.materials)
            {
                MakeTransparent(mat);
                if (mat.HasProperty("_BaseColor"))
                    mat.SetColor("_BaseColor", tint);
                if (mat.HasProperty("_Color"))
                    mat.SetColor("_Color", tint);
            }
        }
    }

    void MakeTransparent(Material mat)
    {
        mat.SetFloat("_Surface", 1);
        mat.SetOverrideTag("RenderType", "Transparent");
        mat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
        mat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
        mat.SetInt("_ZWrite", 0);
        mat.renderQueue = 3000;
        mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
    }

    static Canvas _floatingTextCanvas;

    static Canvas GetFloatingTextCanvas()
    {
        if (_floatingTextCanvas != null) return _floatingTextCanvas;

        // Try to find existing overlay canvas
        foreach (var c in FindObjectsByType<Canvas>(FindObjectsSortMode.None))
        {
            if (c.renderMode == RenderMode.ScreenSpaceOverlay)
            {
                _floatingTextCanvas = c;
                return c;
            }
        }

        // Create one
        var go = new GameObject("FloatingTextCanvas");
        _floatingTextCanvas = go.AddComponent<Canvas>();
        _floatingTextCanvas.renderMode = RenderMode.ScreenSpaceOverlay;
        _floatingTextCanvas.sortingOrder = 100;
        go.AddComponent<CanvasScaler>();
        return _floatingTextCanvas;
    }

    void SpawnCostText(Vector3 worldPos, int amount)
    {
        Canvas canvas = GetFloatingTextCanvas();
        if (canvas == null) return;

        var go = new GameObject("CostText");
        go.transform.SetParent(canvas.transform, false);

        var txt = go.AddComponent<Text>();
        txt.text = $"-${amount}";
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.fontSize = 28;
        txt.color = new Color(0.9f, 0.15f, 0.1f);
        txt.alignment = TextAnchor.MiddleCenter;
        txt.fontStyle = FontStyle.Bold;
        txt.raycastTarget = false;

        var outline = go.AddComponent<Outline>();
        outline.effectColor = Color.black;
        outline.effectDistance = new Vector2(2, -2);

        var rt = go.GetComponent<RectTransform>();
        rt.sizeDelta = new Vector2(200, 40);

        Vector3 screenPos = Camera.main.WorldToScreenPoint(worldPos);
        rt.position = screenPos;

        StartCoroutine(FloatDown(rt, txt, outline));
    }

    IEnumerator FloatDown(RectTransform rt, Text txt, Outline outline)
    {
        float duration = 1.2f;
        float elapsed = 0f;
        Vector3 startPos = rt.position;

        while (elapsed < duration)
        {
            elapsed += Time.deltaTime;
            float t = elapsed / duration;

            rt.position = startPos + Vector3.down * (80f * t);

            float alpha = t < 0.5f ? 1f : 1f - (t - 0.5f) / 0.5f;
            txt.color = new Color(0.9f, 0.15f, 0.1f, alpha);
            outline.effectColor = new Color(0, 0, 0, alpha);

            yield return null;
        }

        Destroy(rt.gameObject);
    }
}
