using UnityEngine;
using UnityEngine.UI;

public class HeroManager : MonoBehaviour
{
    public static HeroManager Instance { get; private set; }

    public Hero ActiveHero { get; private set; }
    public bool IsHeroOwned => ActiveHero != null;

    private RoundManager _rounds;

    // UI
    private GameObject _canvasObj;
    private GameObject _barRoot;
    private Image _portraitImage;
    private Text _levelBadge;
    private AbilityIconWidgets _passive;
    private AbilityIconWidgets _active1;
    private AbilityIconWidgets _active2;

    struct AbilityIconWidgets
    {
        public GameObject root;
        public Image icon;
        public Image cooldownSweep;
        public GameObject lockOverlay;
        public Text lockText;
        public Button button;
    }

    void Awake()
    {
        Instance = this;
    }

    void Start()
    {
        _rounds = FindAnyObjectByType<RoundManager>();
        if (_rounds != null)
            _rounds.OnRoundComplete += HandleRoundComplete;

        BuildUI();
        SetBarVisible(false);
    }

    void OnDestroy()
    {
        if (_rounds != null)
            _rounds.OnRoundComplete -= HandleRoundComplete;
        if (Instance == this) Instance = null;
    }

    void Update()
    {
        if (ActiveHero == null) return;
        RefreshAbilityWidgets();
    }

    public void RegisterHero(Hero hero)
    {
        if (ActiveHero != null && ActiveHero != hero) return;
        ActiveHero = hero;
        SetBarVisible(true);
        PopulatePortrait();
        RefreshAbilityWidgets();
    }

    public void UnregisterHero(Hero hero)
    {
        if (ActiveHero != hero) return;
        ActiveHero = null;
        SetBarVisible(false);
    }

    void HandleRoundComplete(int round)
    {
        if (ActiveHero == null) return;
        ActiveHero.AddXp(HeroData.GetXpForRound(round));
    }

    public bool CastAbility(int index)
    {
        if (ActiveHero == null) return false;
        return ActiveHero.CastAbility(index);
    }

    void BuildUI()
    {
        _canvasObj = new GameObject("HeroBarUI");
        var canvas = _canvasObj.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 25;

        var scaler = _canvasObj.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920, 1080);

        _canvasObj.AddComponent<GraphicRaycaster>();

        _barRoot = new GameObject("HeroBar");
        _barRoot.transform.SetParent(_canvasObj.transform, false);

        var rt = _barRoot.AddComponent<RectTransform>();
        rt.anchorMin = new Vector2(0.72f, 1f);
        rt.anchorMax = new Vector2(0.72f, 1f);
        rt.pivot = new Vector2(0f, 1f);
        rt.anchoredPosition = new Vector2(0f, -6f);
        rt.sizeDelta = new Vector2(260, 50);

        var bg = _barRoot.AddComponent<Image>();
        bg.color = new Color(0.15f, 0.15f, 0.15f, 0.85f);

        var layout = _barRoot.AddComponent<HorizontalLayoutGroup>();
        layout.padding = new RectOffset(6, 6, 5, 5);
        layout.spacing = 6;
        layout.childAlignment = TextAnchor.MiddleLeft;
        layout.childForceExpandWidth = false;
        layout.childForceExpandHeight = false;

        var portraitRoot = new GameObject("Portrait");
        portraitRoot.transform.SetParent(_barRoot.transform, false);
        portraitRoot.AddComponent<LayoutElement>().preferredWidth = 44;
        var portraitImg = portraitRoot.AddComponent<Image>();
        portraitImg.color = new Color(0.25f, 0.25f, 0.3f);
        _portraitImage = portraitImg;

        var badgeGO = new GameObject("LevelBadge");
        badgeGO.transform.SetParent(portraitRoot.transform, false);
        var badgeRT = badgeGO.AddComponent<RectTransform>();
        badgeRT.anchorMin = new Vector2(1f, 0f);
        badgeRT.anchorMax = new Vector2(1f, 0f);
        badgeRT.pivot = new Vector2(1f, 0f);
        badgeRT.sizeDelta = new Vector2(20, 18);
        var badgeBG = badgeGO.AddComponent<Image>();
        badgeBG.color = new Color(0f, 0f, 0f, 0.8f);

        _levelBadge = AddTextChild(badgeGO, "1", 12, Color.yellow);

        _passive = MakeAbilityWidget(_barRoot.transform, "Passive", 0, isPassive: true);
        _active1 = MakeAbilityWidget(_barRoot.transform, "Active1", 0, isPassive: false);
        _active2 = MakeAbilityWidget(_barRoot.transform, "Active2", 1, isPassive: false);
    }

    AbilityIconWidgets MakeAbilityWidget(Transform parent, string label, int castIndex, bool isPassive)
    {
        var widgets = new AbilityIconWidgets();

        var root = new GameObject(label);
        root.transform.SetParent(parent, false);
        root.AddComponent<LayoutElement>().preferredWidth = 44;

        var bg = root.AddComponent<Image>();
        bg.color = new Color(0.1f, 0.1f, 0.1f, 0.8f);
        widgets.root = root;

        var iconGO = new GameObject("Icon");
        iconGO.transform.SetParent(root.transform, false);
        var iconImg = iconGO.AddComponent<Image>();
        iconImg.preserveAspect = true;
        iconImg.raycastTarget = false;
        var iconRT = iconGO.GetComponent<RectTransform>();
        iconRT.anchorMin = new Vector2(0.1f, 0.1f);
        iconRT.anchorMax = new Vector2(0.9f, 0.9f);
        iconRT.offsetMin = Vector2.zero;
        iconRT.offsetMax = Vector2.zero;
        widgets.icon = iconImg;

        var sweepGO = new GameObject("CooldownSweep");
        sweepGO.transform.SetParent(root.transform, false);
        var sweepImg = sweepGO.AddComponent<Image>();
        sweepImg.color = new Color(0f, 0f, 0f, 0.55f);
        sweepImg.type = Image.Type.Filled;
        sweepImg.fillMethod = Image.FillMethod.Radial360;
        sweepImg.fillOrigin = (int)Image.Origin360.Top;
        sweepImg.fillAmount = 0f;
        sweepImg.raycastTarget = false;
        var sweepRT = sweepGO.GetComponent<RectTransform>();
        sweepRT.anchorMin = Vector2.zero;
        sweepRT.anchorMax = Vector2.one;
        sweepRT.offsetMin = Vector2.zero;
        sweepRT.offsetMax = Vector2.zero;
        widgets.cooldownSweep = sweepImg;

        var lockGO = new GameObject("Lock");
        lockGO.transform.SetParent(root.transform, false);
        var lockImg = lockGO.AddComponent<Image>();
        lockImg.color = new Color(0f, 0f, 0f, 0.75f);
        lockImg.raycastTarget = false;
        var lockRT = lockGO.GetComponent<RectTransform>();
        lockRT.anchorMin = Vector2.zero;
        lockRT.anchorMax = Vector2.one;
        lockRT.offsetMin = Vector2.zero;
        lockRT.offsetMax = Vector2.zero;
        widgets.lockOverlay = lockGO;
        widgets.lockText = AddTextChild(lockGO, "L?", 14, Color.white);

        if (!isPassive)
        {
            var btn = root.AddComponent<Button>();
            int captured = castIndex;
            btn.onClick.AddListener(() => CastAbility(captured));
            widgets.button = btn;
        }

        return widgets;
    }

    static Text AddTextChild(GameObject parent, string txt, int size, Color color)
    {
        var go = new GameObject("Text");
        go.transform.SetParent(parent.transform, false);
        var t = go.AddComponent<Text>();
        t.text = txt;
        t.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        t.alignment = TextAnchor.MiddleCenter;
        t.color = color;
        t.fontSize = size;
        t.fontStyle = FontStyle.Bold;
        t.raycastTarget = false;
        var outline = go.AddComponent<Outline>();
        outline.effectColor = Color.black;
        outline.effectDistance = new Vector2(1, -1);
        var rt = go.GetComponent<RectTransform>();
        rt.anchorMin = Vector2.zero;
        rt.anchorMax = Vector2.one;
        rt.offsetMin = Vector2.zero;
        rt.offsetMax = Vector2.zero;
        return t;
    }

    void SetBarVisible(bool visible)
    {
        if (_barRoot != null) _barRoot.SetActive(visible);
    }

    void PopulatePortrait()
    {
        if (ActiveHero == null) return;
        string iconPath = HeroData.GetIconPath(ActiveHero.heroType);
        var sprite = iconPath != null ? Resources.Load<Sprite>(iconPath) : null;
        if (sprite != null) _portraitImage.sprite = sprite;

        ApplyAbilityIcon(_passive, ActiveHero.passive);
        ApplyAbilityIcon(_active1, ActiveHero.active1);
        ApplyAbilityIcon(_active2, ActiveHero.active2);
    }

    static void ApplyAbilityIcon(AbilityIconWidgets w, HeroAbility a)
    {
        if (a == null) return;
        if (!string.IsNullOrEmpty(a.iconPath))
        {
            var sprite = Resources.Load<Sprite>(a.iconPath);
            if (sprite != null) w.icon.sprite = sprite;
        }
    }

    void RefreshAbilityWidgets()
    {
        if (ActiveHero == null) return;

        _levelBadge.text = ActiveHero.level.ToString();

        RefreshOne(_passive, ActiveHero.passive);
        RefreshOne(_active1, ActiveHero.active1);
        RefreshOne(_active2, ActiveHero.active2);
    }

    void RefreshOne(AbilityIconWidgets w, HeroAbility a)
    {
        if (a == null || ActiveHero == null)
        {
            w.lockOverlay.SetActive(true);
            w.lockText.text = "—";
            w.cooldownSweep.fillAmount = 0f;
            if (w.button != null) w.button.interactable = false;
            return;
        }

        bool unlocked = a.IsUnlocked(ActiveHero.level);
        w.lockOverlay.SetActive(!unlocked);
        w.lockText.text = unlocked ? "" : $"L{a.unlockLevel}";

        if (a.isPassive)
        {
            w.cooldownSweep.fillAmount = 0f;
            return;
        }

        float remaining = a.CooldownRemaining();
        w.cooldownSweep.fillAmount = a.cooldown > 0f ? Mathf.Clamp01(remaining / a.cooldown) : 0f;

        if (w.button != null)
            w.button.interactable = unlocked && remaining <= 0f;
    }
}
