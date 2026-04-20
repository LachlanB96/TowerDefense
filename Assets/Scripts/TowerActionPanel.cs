using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class TowerActionPanel
{
    private readonly GameObject _root;
    private readonly Dictionary<string, GameObject> _upgradePrefabs;
    private readonly Dictionary<string, Action<GameObject>> _upgradeSetup;
    private readonly Action _onDeselected;
    private readonly Action<GameObject> _onUpgraded;

    private GameObject _tower;
    private readonly Button _sellButton;
    private readonly Text _statsText;
    private readonly Button[] _upgradeButtons = new Button[3];
    private readonly Image[] _upgradeIcons = new Image[3];

    public GameObject Root => _root;

    public TowerActionPanel(Transform parent,
        Dictionary<string, GameObject> upgradePrefabs,
        Dictionary<string, Action<GameObject>> upgradeSetup,
        Action onDeselected,
        Action<GameObject> onUpgraded)
    {
        _upgradePrefabs = upgradePrefabs;
        _upgradeSetup = upgradeSetup;
        _onDeselected = onDeselected;
        _onUpgraded = onUpgraded;

        _root = new GameObject("TowerLayout", typeof(RectTransform));
        _root.transform.SetParent(parent, false);
        UIBuilder.Stretch(_root);

        var layout = _root.AddComponent<VerticalLayoutGroup>();
        layout.padding = new RectOffset(10, 10, 10, 10);
        layout.spacing = 8;
        layout.childForceExpandWidth = true;
        layout.childForceExpandHeight = false;
        layout.childAlignment = TextAnchor.UpperCenter;

        _sellButton = SelectionPanelBuilder.Button("Sell", _root.transform, new Color(0.7f, 0.15f, 0.15f));
        _sellButton.onClick.AddListener(Sell);

        _statsText = SelectionPanelBuilder.StatsBlock(_root.transform);

        SelectionPanelBuilder.Label("-- Upgrades --", _root.transform);

        Color btnColor = new Color(0.545f, 0.271f, 0.075f);
        string[] iconPaths = { "UI/tack100_icon", "UI/tack010_icon", "UI/tack001_icon" };
        for (int i = 0; i < 3; i++)
        {
            int captured = i + 1;
            _upgradeButtons[i] = MakeUpgradeButton($"Path {i + 1}", _root.transform, btnColor, iconPaths[i], out _upgradeIcons[i]);
            _upgradeButtons[i].onClick.AddListener(() => Upgrade(captured));
        }
    }

    public void SetTower(GameObject tower) => _tower = tower;
    public void SetVisible(bool v) => _root.SetActive(v);

    public void Refresh()
    {
        if (_tower == null) return;
        var data = _tower.GetComponent<TowerData>();
        if (data == null) return;

        _sellButton.GetComponentInChildren<Text>().text = $"Sell (${data.SellValue})";
        _statsText.text = $"Kills: {data.killCount}\nDamage: {data.totalDamage}";

        int[] levels = { data.upgradePath1Level, data.upgradePath2Level, data.upgradePath3Level };
        for (int i = 0; i < 3; i++)
        {
            bool available = TowerCosts.TryGetUpgrade(data.towerType, i, levels[i], out var info);
            bool canAfford = available && EconomyManager.Instance != null && EconomyManager.Instance.CanAfford(info.cost);
            bool hasPrefab = available && _upgradePrefabs.TryGetValue(info.resultType, out var prefab) && prefab != null;
            _upgradeButtons[i].interactable = available && canAfford && hasPrefab;

            var txt = _upgradeButtons[i].GetComponentInChildren<Text>();
            txt.text = available ? $"Path {i + 1} (${info.cost})" : $"Path {i + 1}";
        }
    }

    public void Sell()
    {
        if (_tower == null) return;
        var data = _tower.GetComponent<TowerData>();
        if (data == null) return;

        GameObject tower = _tower;
        int refund = data.SellValue;
        Vector3 worldPos = tower.transform.position;

        _onDeselected?.Invoke();

        if (refund > 0 && EconomyManager.Instance != null)
        {
            EconomyManager.Instance.money += refund;
            FloatingText.Spawn(worldPos, $"+${refund}", new Color(1f, 0.85f, 0.1f), 1.2f, 28, true, 80f);
        }

        UnityEngine.Object.Destroy(tower);
    }

    public void Upgrade(int path)
    {
        if (_tower == null) return;
        var data = _tower.GetComponent<TowerData>();
        if (data == null) return;

        int pathIndex = path - 1;
        int currentLevel = pathIndex == 0 ? data.upgradePath1Level
                         : pathIndex == 1 ? data.upgradePath2Level
                         : data.upgradePath3Level;

        if (!TowerCosts.TryGetUpgrade(data.towerType, pathIndex, currentLevel, out var upgradeInfo)) return;
        if (!_upgradePrefabs.TryGetValue(upgradeInfo.resultType, out var prefab) || prefab == null) return;
        if (EconomyManager.Instance == null || !EconomyManager.Instance.TrySpend(upgradeInfo.cost)) return;

        int previousInvestment = data.totalInvested;
        Vector3 pos = _tower.transform.position;
        Quaternion rot = _tower.transform.rotation;

        _onDeselected?.Invoke();
        UnityEngine.Object.Destroy(data.gameObject);

        GameObject newTower = UnityEngine.Object.Instantiate(prefab, pos, rot);
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

        _onUpgraded?.Invoke(newTower);
    }

    static Button MakeUpgradeButton(string label, Transform parent, Color bg, string spritePath, out Image iconImage)
    {
        var go = new GameObject(label);
        go.transform.SetParent(parent, false);

        go.AddComponent<Image>().color = bg;

        var btn = go.AddComponent<Button>();
        UIBuilder.ApplyStandardColors(btn);

        go.AddComponent<LayoutElement>().preferredHeight = 55;

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

        var txt = UIBuilder.Text("Text", go.transform, label, 15, Color.white);
        var trt = txt.GetComponent<RectTransform>();
        trt.anchorMin = new Vector2(0.35f, 0f);
        trt.anchorMax = Vector2.one;
        trt.offsetMin = Vector2.zero;
        trt.offsetMax = Vector2.zero;

        return btn;
    }
}
