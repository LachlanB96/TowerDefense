using UnityEngine;
using UnityEngine.UI;

public class EconomyManager : MonoBehaviour
{
    public static EconomyManager Instance { get; private set; }

    public int money = 500;
    public int economy = 250;

    private float _incomeTimer;
    private const float INCOME_INTERVAL = 6f;

    private Text _moneyText;
    private Text _economyText;
    private Image _incomeBarFill;

    void Awake()
    {
        Instance = this;
    }

    void Start()
    {
        BuildUI();
    }

    void Update()
    {
        _incomeTimer += Time.deltaTime;
        if (_incomeTimer >= INCOME_INTERVAL)
        {
            _incomeTimer -= INCOME_INTERVAL;
            money += economy;
        }

        _moneyText.text = $"${money}";
        _economyText.text = $"Economy: {economy}";

        float ratio = Mathf.Clamp01(_incomeTimer / INCOME_INTERVAL);
        _incomeBarFill.rectTransform.anchorMax = new Vector2(ratio, 1);
    }

    public void AddEconomy(int amount)
    {
        economy += amount;
    }

    void BuildUI()
    {
        // Find or create a top-bar canvas
        var canvasGO = new GameObject("EconomyCanvas");
        var canvas = canvasGO.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 20;

        var scaler = canvasGO.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920, 1080);

        canvasGO.AddComponent<GraphicRaycaster>();

        // Background panel at top center
        var panel = new GameObject("TopBar");
        panel.transform.SetParent(canvasGO.transform, false);

        var panelRT = panel.AddComponent<RectTransform>();
        panelRT.anchorMin = new Vector2(0.3f, 1f);
        panelRT.anchorMax = new Vector2(0.7f, 1f);
        panelRT.pivot = new Vector2(0.5f, 1f);
        panelRT.anchoredPosition = Vector2.zero;
        panelRT.sizeDelta = new Vector2(0, 50);

        var panelImg = panel.AddComponent<Image>();
        panelImg.color = new Color(0.15f, 0.15f, 0.15f, 0.85f);

        var layout = panel.AddComponent<HorizontalLayoutGroup>();
        layout.padding = new RectOffset(20, 20, 5, 5);
        layout.spacing = 40;
        layout.childAlignment = TextAnchor.MiddleCenter;
        layout.childForceExpandWidth = false;
        layout.childForceExpandHeight = true;

        // Money text
        _moneyText = MakeText("MoneyText", panel.transform, 24, Color.yellow);
        _moneyText.text = $"${money}";

        // Economy text
        _economyText = MakeText("EconomyText", panel.transform, 18, new Color(0.6f, 0.9f, 0.6f));
        _economyText.text = $"Economy: {economy}";

        // Income progress bar
        var barContainer = new GameObject("IncomeBar");
        barContainer.transform.SetParent(panel.transform, false);
        barContainer.AddComponent<LayoutElement>().preferredWidth = 120;

        var barBg = new GameObject("BarBG");
        barBg.transform.SetParent(barContainer.transform, false);
        var bgImg = barBg.AddComponent<Image>();
        bgImg.color = new Color(0.1f, 0.1f, 0.1f, 0.8f);
        var bgRt = barBg.GetComponent<RectTransform>();
        bgRt.anchorMin = Vector2.zero;
        bgRt.anchorMax = Vector2.one;
        bgRt.offsetMin = new Vector2(0, 10);
        bgRt.offsetMax = new Vector2(0, -10);

        var barFill = new GameObject("BarFill");
        barFill.transform.SetParent(barContainer.transform, false);
        _incomeBarFill = barFill.AddComponent<Image>();
        _incomeBarFill.color = new Color(0.4f, 0.85f, 0.4f);
        var fillRt = barFill.GetComponent<RectTransform>();
        fillRt.anchorMin = Vector2.zero;
        fillRt.anchorMax = new Vector2(0, 1);
        fillRt.pivot = new Vector2(0, 0.5f);
        fillRt.offsetMin = new Vector2(0, 10);
        fillRt.offsetMax = new Vector2(0, -10);
    }

    Text MakeText(string name, Transform parent, int fontSize, Color color)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);

        var txt = go.AddComponent<Text>();
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.fontSize = fontSize;
        txt.color = color;
        txt.alignment = TextAnchor.MiddleCenter;

        var le = go.AddComponent<LayoutElement>();
        le.preferredWidth = 200;

        return txt;
    }
}
