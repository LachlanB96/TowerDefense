using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

public class TowerPlacer : MonoBehaviour
{
    [SerializeField] private GameObject _towerPrefab;
    [SerializeField] private GameObject _sniperPrefab;
    [SerializeField] private GameObject _knightPrefab;
    [SerializeField] private LayerMask _groundLayer;
    [SerializeField] private LayerMask _waterLayer;
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

    private Dictionary<string, GameObject> _prefabs;
    private Dictionary<string, System.Action<GameObject>> _placementSetup;
    private PathRenderer _pathRenderer;

    // ── Dev Tools ──────────────────────────────────────
    private static readonly bool DEV_AUTO_PLACE = true;
    private static readonly Vector3 DEV_TACK_POS = new Vector3(13.96f, -0.05f, 8.70f);
    private static readonly Vector3 DEV_SNIPER_POS = new Vector3(10f, -0.05f, 6f);
    private static readonly Vector3 DEV_KNIGHT_POS = new Vector3(15.56f, -0.05f, 8.70f);
    // ─────────────────────────────────────────────────────

    void Start()
    {
        _pathRenderer = FindAnyObjectByType<PathRenderer>();

        _prefabs = new Dictionary<string, GameObject>
        {
            { "tack000", _towerPrefab },
            { "sniper000", _sniperPrefab },
            { "knight000", _knightPrefab },
        };

        _placementSetup = new Dictionary<string, System.Action<GameObject>>
        {
            { "tack000", tower =>
                {
                    var attack = tower.GetComponent<TackAttack>() ?? tower.AddComponent<TackAttack>();
                    attack.diskColor = _projectileColor;
                    attack.diskMetallic = _projectileMetallic;
                    attack.diskSmoothness = _projectileSmoothness;
                }
            },
            { "sniper000", tower =>
                {
                    if (tower.GetComponent<SniperIdle>() == null)
                        tower.AddComponent<SniperIdle>();
                    if (tower.GetComponent<SniperAttack>() == null)
                        tower.AddComponent<SniperAttack>();
                }
            },
            { "knight000", hero =>
                {
                    SilentKnightSetup.Configure(hero);
                }
            },
        };

        BuildShopPanel();

        if (DEV_AUTO_PLACE)
        {
            DevPlaceTower("tack000", DEV_TACK_POS);
            DevPlaceTower("sniper000", DEV_SNIPER_POS);
            DevPlaceTower("knight000", DEV_KNIGHT_POS);
        }
    }

    void DevPlaceTower(string type, Vector3 pos)
    {
        if (!_prefabs.TryGetValue(type, out var prefab) || prefab == null) return;

        var tower = Instantiate(prefab);
        tower.name = type;
        tower.transform.position = pos;

        foreach (var col in tower.GetComponentsInChildren<Collider>(true))
            col.enabled = true;

        TowerUtils.EnsureCollider(tower);

        if (!HeroData.Exists(type))
        {
            TowerData data = tower.GetComponent<TowerData>() ?? tower.AddComponent<TowerData>();
            data.towerType = type;
            data.totalInvested = 0;
        }

        if (_placementSetup.TryGetValue(type, out var setup))
            setup(tower);
    }

    void BuildShopPanel()
    {
        var canvasGO = UIBuilder.Canvas("ShopUI", 10);

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

        // Tower buttons
        MakeTowerButton("tack000", panel.transform);
        MakeTowerButton("sniper000", panel.transform);

        // Heroes
        MakeLabel("-- Heroes --", panel.transform);
        MakeHeroButton("knight000", panel.transform);
    }

    void MakeTowerButton(string towerType, Transform parent)
    {
        int cost = TowerCosts.GetPlacementCost(towerType);
        string iconPath = TowerCosts.GetIconPath(towerType);
        Sprite iconSprite = iconPath != null ? Resources.Load<Sprite>(iconPath) : null;

        // Button container
        var go = new GameObject("TowerBtn_" + towerType);
        go.transform.SetParent(parent, false);

        go.AddComponent<LayoutElement>().preferredHeight = 150;

        var btn = go.AddComponent<Button>();
        string capturedType = towerType;
        btn.onClick.AddListener(() => BeginPlacement(capturedType));
        UIBuilder.ApplyStandardColors(btn);

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
        var priceTxt = UIBuilder.Text("PriceLabel", go.transform, $"${cost}", 20, Color.white, bold: true);
        UIBuilder.AddOutline(priceTxt.gameObject);

        var priceRT = priceTxt.GetComponent<RectTransform>();
        priceRT.anchorMin = new Vector2(0, 0);
        priceRT.anchorMax = new Vector2(1, 0.22f);
        priceRT.offsetMin = Vector2.zero;
        priceRT.offsetMax = Vector2.zero;
    }

    void MakeHeroButton(string heroType, Transform parent)
    {
        int cost = HeroData.GetCost(heroType);
        string iconPath = HeroData.GetIconPath(heroType);
        Sprite iconSprite = iconPath != null ? Resources.Load<Sprite>(iconPath) : null;
        string displayName = heroType == "knight000" ? "SILENT KNIGHT" : heroType.ToUpperInvariant();

        var go = new GameObject("HeroBtn_" + heroType);
        go.transform.SetParent(parent, false);
        go.AddComponent<LayoutElement>().preferredHeight = 150;

        var btn = go.AddComponent<Button>();
        string capturedType = heroType;
        btn.onClick.AddListener(() =>
        {
            if (HeroManager.Instance != null && HeroManager.Instance.IsHeroOwned) return;
            BeginPlacement(capturedType);
        });

        ColorBlock cb = btn.colors;
        cb.normalColor = Color.white;
        cb.highlightedColor = new Color(1.15f, 1.15f, 1.2f, 1f);
        cb.pressedColor = new Color(0.8f, 0.8f, 0.85f, 1f);
        cb.disabledColor = new Color(0.5f, 0.5f, 0.5f, 0.5f);
        btn.colors = cb;

        // Deep navy background (Templar blue)
        var bg = go.AddComponent<Image>();
        bg.color = new Color(0.14f, 0.18f, 0.34f);

        // Gold trim strip between icon and price
        var trimGO = new GameObject("GoldTrim");
        trimGO.transform.SetParent(go.transform, false);
        var trimImg = trimGO.AddComponent<Image>();
        trimImg.color = new Color(0.92f, 0.78f, 0.28f);
        trimImg.raycastTarget = false;
        var trimRT = trimGO.GetComponent<RectTransform>();
        trimRT.anchorMin = new Vector2(0f, 0.22f);
        trimRT.anchorMax = new Vector2(1f, 0.24f);
        trimRT.offsetMin = Vector2.zero;
        trimRT.offsetMax = Vector2.zero;

        // Icon (or stylized name fallback when sprite is missing)
        if (iconSprite != null)
        {
            var iconGO = new GameObject("Icon");
            iconGO.transform.SetParent(go.transform, false);
            var iconImg = iconGO.AddComponent<Image>();
            iconImg.sprite = iconSprite;
            iconImg.preserveAspect = true;
            iconImg.color = Color.white;
            iconImg.raycastTarget = false;
            var iconRT = iconGO.GetComponent<RectTransform>();
            iconRT.anchorMin = new Vector2(0.05f, 0.25f);
            iconRT.anchorMax = new Vector2(0.95f, 0.95f);
            iconRT.offsetMin = Vector2.zero;
            iconRT.offsetMax = Vector2.zero;
        }
        else
        {
            var nameTxt = UIBuilder.Text("NameLabel", go.transform, displayName, 18, new Color(0.92f, 0.78f, 0.28f), bold: true);
            nameTxt.raycastTarget = false;
            UIBuilder.AddOutline(nameTxt.gameObject);
            var nameRT = nameTxt.GetComponent<RectTransform>();
            nameRT.anchorMin = new Vector2(0f, 0.25f);
            nameRT.anchorMax = new Vector2(1f, 0.95f);
            nameRT.offsetMin = Vector2.zero;
            nameRT.offsetMax = Vector2.zero;
        }

        // Price label at bottom
        var priceTxt = UIBuilder.Text("PriceLabel", go.transform, $"${cost}", 20, Color.white, bold: true);
        priceTxt.raycastTarget = false;
        UIBuilder.AddOutline(priceTxt.gameObject);

        var priceRT = priceTxt.GetComponent<RectTransform>();
        priceRT.anchorMin = new Vector2(0f, 0f);
        priceRT.anchorMax = new Vector2(1f, 0.22f);
        priceRT.offsetMin = Vector2.zero;
        priceRT.offsetMax = Vector2.zero;
    }

    void MakeLabel(string text, Transform parent)
    {
        var txt = UIBuilder.Text("Label", parent, text, 14, new Color(1f, 1f, 1f, 0.6f));
        txt.gameObject.AddComponent<LayoutElement>().preferredHeight = 25;
    }

    public void BeginPlacement(string towerType = "tack000")
    {
        if (_isPlacing) return;
        _placingType = towerType;
        SpawnPreview();
    }

    void SpawnPreview()
    {
        _isPlacing = true;
        _skipFrames = 2;
        _canPlace = false;

        if (!_prefabs.TryGetValue(_placingType, out var prefab) || prefab == null)
            prefab = _towerPrefab;

        _preview = Instantiate(prefab);
        _preview.name = _placingType + "_preview";

        foreach (var col in _preview.GetComponentsInChildren<Collider>())
            col.enabled = false;

        // Save original materials before modifying
        _previewRenderers = _preview.GetComponentsInChildren<Renderer>();
        _originalMaterials = new Material[_previewRenderers.Length][];
        for (int i = 0; i < _previewRenderers.Length; i++)
            _originalMaterials[i] = _previewRenderers[i].sharedMaterials;

        SetPreviewColor(new Color(1f, 1f, 1f, 0.4f));

        float previewRange = HeroData.Exists(_placingType)
            ? HeroData.GetRange(_placingType)
            : TowerCosts.GetRange(_placingType);
        _rangeIndicator = RangeIndicator.Create(previewRange, _preview.transform);
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
        LayerMask requiredMask = TowerCosts.GetSurface(_placingType) == TowerCosts.SurfaceType.Water
            ? _waterLayer
            : _groundLayer;
        int combinedMask = _groundLayer | _waterLayer;
        if (Physics.Raycast(ray, out RaycastHit hit, 500f, combinedMask))
        {
            _preview.transform.position = hit.point;
            bool surfaceMatch = ((1 << hit.collider.gameObject.layer) & requiredMask.value) != 0;
            _canPlace = surfaceMatch && !CheckOverlap(hit.point);
            SetPreviewColor(_canPlace ? new Color(1f, 1f, 1f, 0.4f) : new Color(1f, 0.15f, 0.15f, 0.5f));
        }
        else
        {
            _canPlace = false;
        }

        if (mouse.leftButton.wasPressedThisFrame && _canPlace)
        {
            int cost = HeroData.Exists(_placingType)
                ? HeroData.GetCost(_placingType)
                : TowerCosts.GetPlacementCost(_placingType);
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
            if (col.gameObject.layer == 4) continue; // Water layer
            return true;
        }

        if (_pathRenderer != null && _pathRenderer.IsPointOnPath(new Vector2(position.x, position.z), _overlapRadius))
            return true;

        return false;
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

        TowerUtils.EnsureCollider(_preview);

        // Restore original materials (with Blender colors)
        for (int i = 0; i < _previewRenderers.Length; i++)
            _previewRenderers[i].sharedMaterials = _originalMaterials[i];

        bool isHero = HeroData.Exists(_placingType);
        int cost = isHero ? HeroData.GetCost(_placingType) : TowerCosts.GetPlacementCost(_placingType);

        if (!isHero)
        {
            TowerData data = _preview.GetComponent<TowerData>() ?? _preview.AddComponent<TowerData>();
            data.towerType = _placingType;
            data.totalInvested = cost;
        }

        FloatingText.Spawn(_preview.transform.position, $"-${cost}", new Color(0.9f, 0.15f, 0.1f), 1.2f, 28, false, 80f);

        if (_placementSetup.TryGetValue(_placingType, out var setup))
            setup(_preview);

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
                MaterialUtils.MakeTransparent(mat);
                if (mat.HasProperty("_BaseColor"))
                    mat.SetColor("_BaseColor", tint);
                if (mat.HasProperty("_Color"))
                    mat.SetColor("_Color", tint);
            }
        }
    }
}
