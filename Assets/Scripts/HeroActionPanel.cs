using System;
using UnityEngine;
using UnityEngine.UI;

public class HeroActionPanel
{
    private readonly GameObject _root;
    private readonly Action _onDeselected;

    private Hero _hero;
    private readonly Text _nameText;
    private readonly Text _levelText;
    private readonly Image _xpBarFill;
    private readonly Text _passiveText;
    private readonly Text _statsText;
    private readonly Button _levelUpButton;
    private readonly Button _sellButton;
    private readonly Button _active1Button;
    private readonly Image _active1Cooldown;
    private readonly GameObject _active1Lock;
    private readonly Text _active1LockText;
    private readonly Button _active2Button;
    private readonly Image _active2Cooldown;
    private readonly GameObject _active2Lock;
    private readonly Text _active2LockText;

    public GameObject Root => _root;

    public HeroActionPanel(Transform parent, Action onDeselected)
    {
        _onDeselected = onDeselected;

        _root = new GameObject("HeroLayout", typeof(RectTransform));
        _root.transform.SetParent(parent, false);
        UIBuilder.Stretch(_root);

        var layout = _root.AddComponent<VerticalLayoutGroup>();
        layout.padding = new RectOffset(10, 10, 10, 10);
        layout.spacing = 6;
        layout.childForceExpandWidth = true;
        layout.childForceExpandHeight = false;
        layout.childAlignment = TextAnchor.UpperCenter;

        _nameText = MakeHeroText("NameText", _root.transform, 20, Color.white, 30);
        _levelText = MakeHeroText("LevelText", _root.transform, 14, new Color(1f, 0.85f, 0.3f), 20);

        var xpBar = new GameObject("XpBar");
        xpBar.transform.SetParent(_root.transform, false);
        xpBar.AddComponent<LayoutElement>().preferredHeight = 10;
        xpBar.AddComponent<Image>().color = new Color(0.1f, 0.1f, 0.1f, 0.8f);

        var xpFill = new GameObject("Fill");
        xpFill.transform.SetParent(xpBar.transform, false);
        _xpBarFill = xpFill.AddComponent<Image>();
        _xpBarFill.color = new Color(0.9f, 0.75f, 0.2f);
        var frt = xpFill.GetComponent<RectTransform>();
        frt.anchorMin = Vector2.zero;
        frt.anchorMax = new Vector2(0f, 1f);
        frt.pivot = new Vector2(0f, 0.5f);
        frt.offsetMin = Vector2.zero;
        frt.offsetMax = Vector2.zero;

        _levelUpButton = SelectionPanelBuilder.Button("Level Up", _root.transform, new Color(0.2f, 0.45f, 0.75f));
        _levelUpButton.onClick.AddListener(LevelUp);

        _statsText = SelectionPanelBuilder.StatsBlock(_root.transform);

        SelectionPanelBuilder.Label("-- Passive --", _root.transform);
        _passiveText = MakeHeroText("PassiveText", _root.transform, 12, new Color(1f, 1f, 1f, 0.9f), 48);
        _passiveText.alignment = TextAnchor.UpperCenter;

        SelectionPanelBuilder.Label("-- Abilities --", _root.transform);

        (_active1Button, _active1Cooldown, _active1Lock, _active1LockText) =
            MakeAbilityButton("Active 1", _root.transform, 0);
        (_active2Button, _active2Cooldown, _active2Lock, _active2LockText) =
            MakeAbilityButton("Active 2", _root.transform, 1);

        _sellButton = SelectionPanelBuilder.Button("Sell", _root.transform, new Color(0.7f, 0.15f, 0.15f));
        _sellButton.onClick.AddListener(Sell);
    }

    public void SetHero(Hero hero) => _hero = hero;
    public void SetVisible(bool v) => _root.SetActive(v);

    public void Refresh()
    {
        if (_hero == null) return;

        _nameText.text = _hero.heroType == "knight000" ? "Silent Knight" : _hero.heroType;
        _levelText.text = _hero.level >= 10 ? "Level 10 (MAX)" : $"Level {_hero.level}";

        if (_hero.level >= 10)
        {
            _xpBarFill.rectTransform.anchorMax = new Vector2(1f, 1f);
        }
        else
        {
            int cur = _hero.XpTowardNextLevel();
            int req = Mathf.Max(1, _hero.XpRequiredForNextLevel());
            float ratio = Mathf.Clamp01(cur / (float)req);
            _xpBarFill.rectTransform.anchorMax = new Vector2(ratio, 1f);
        }

        _passiveText.text = _hero.passive != null
            ? $"{_hero.passive.name}\n{_hero.passive.description}"
            : "";

        _statsText.text = $"Kills: {_hero.killCount}\nDamage: {_hero.totalDamage}";

        UpdateLevelUpButton();
        UpdateAbilityButton(_hero.active1, _active1Button, _active1Cooldown, _active1Lock, _active1LockText);
        UpdateAbilityButton(_hero.active2, _active2Button, _active2Cooldown, _active2Lock, _active2LockText);

        int sellValue = HeroData.GetSellValue(_hero.heroType);
        _sellButton.GetComponentInChildren<Text>().text = $"Sell (${sellValue})";
    }

    void UpdateLevelUpButton()
    {
        var txt = _levelUpButton.GetComponentInChildren<Text>();

        if (_hero.level >= 10)
        {
            txt.text = "Max Level";
            _levelUpButton.interactable = false;
            return;
        }

        int remaining = Mathf.Max(0, _hero.XpRequiredForNextLevel() - _hero.XpTowardNextLevel());
        int cost = Mathf.Max(1, remaining / 10);
        txt.text = $"Level Up (${cost})";
        _levelUpButton.interactable = EconomyManager.Instance != null && EconomyManager.Instance.CanAfford(cost);
    }

    void UpdateAbilityButton(HeroAbility a, Button btn, Image cooldownFill, GameObject lockGO, Text lockTxt)
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

        bool unlocked = a.IsUnlocked(_hero.level);
        lockGO.SetActive(!unlocked);
        lockTxt.text = unlocked ? "" : $"L{a.unlockLevel}";

        float remaining = a.CooldownRemaining();
        cooldownFill.fillAmount = a.cooldown > 0f ? Mathf.Clamp01(remaining / a.cooldown) : 0f;

        if (cdText != null)
            cdText.text = remaining > 0.05f ? (remaining >= 10f ? Mathf.CeilToInt(remaining).ToString() : remaining.ToString("F1")) : "";

        btn.interactable = unlocked && remaining <= 0f;
    }

    public void Sell()
    {
        if (_hero == null) return;

        int refund = HeroData.GetSellValue(_hero.heroType);
        Vector3 worldPos = _hero.transform.position;

        if (HeroManager.Instance != null)
            HeroManager.Instance.UnregisterHero(_hero);

        GameObject go = _hero.gameObject;
        _onDeselected?.Invoke();

        if (refund > 0 && EconomyManager.Instance != null)
        {
            EconomyManager.Instance.money += refund;
            FloatingText.Spawn(worldPos, $"+${refund}", new Color(1f, 0.85f, 0.1f), 1.2f, 28, true, 80f);
        }

        UnityEngine.Object.Destroy(go);
    }

    public void LevelUp()
    {
        if (_hero == null) return;
        if (_hero.level >= 10) return;

        int remaining = Mathf.Max(0, _hero.XpRequiredForNextLevel() - _hero.XpTowardNextLevel());
        int cost = Mathf.Max(1, remaining / 10);

        if (EconomyManager.Instance == null || !EconomyManager.Instance.TrySpend(cost)) return;

        _hero.AddXp(remaining);
        FloatingText.Spawn(_hero.transform.position, $"-${cost}", new Color(0.9f, 0.15f, 0.1f), 1.2f, 28, false, 80f);
    }

    static Text MakeHeroText(string name, Transform parent, int fontSize, Color color, float height)
    {
        var t = UIBuilder.Text(name, parent, "", fontSize, color);
        t.gameObject.AddComponent<LayoutElement>().preferredHeight = height;
        return t;
    }

    static (Button, Image, GameObject, Text) MakeAbilityButton(string label, Transform parent, int index)
    {
        var go = new GameObject(label);
        go.transform.SetParent(parent, false);
        go.AddComponent<LayoutElement>().preferredHeight = 45;

        go.AddComponent<Image>().color = new Color(0.25f, 0.1f, 0.1f);

        var btn = go.AddComponent<Button>();
        int captured = index;
        btn.onClick.AddListener(() => {
            if (HeroManager.Instance != null) HeroManager.Instance.CastAbility(captured);
        });
        UIBuilder.ApplyStandardColors(btn);

        var t = UIBuilder.Text("Text", go.transform, label, 15, Color.white);
        UIBuilder.Stretch(t.gameObject);

        var cdImg = UIBuilder.RadialCooldown("Cooldown", go.transform, new Color(0f, 0f, 0f, 0.6f));
        cdImg.fillClockwise = true;

        var cdTxt = UIBuilder.Text("CooldownText", cdImg.transform, "", 20, Color.white, bold: true);
        cdTxt.raycastTarget = false;
        UIBuilder.AddOutline(cdTxt.gameObject);
        UIBuilder.Stretch(cdTxt.gameObject);

        var lockGO = new GameObject("Lock");
        lockGO.transform.SetParent(go.transform, false);
        var lockImg = lockGO.AddComponent<Image>();
        lockImg.color = new Color(0f, 0f, 0f, 0.75f);
        lockImg.raycastTarget = false;
        UIBuilder.Stretch(lockGO);

        var lt = UIBuilder.Text("LockText", lockGO.transform, "", 16, Color.white, bold: true);
        UIBuilder.Stretch(lt.gameObject);

        return (btn, cdImg, lockGO, lt);
    }
}
