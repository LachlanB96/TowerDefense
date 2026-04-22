using System;
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
    private GameObject _actionPanelRoot;

    private SelectionOutline _outline;
    private TowerActionPanel _towerPanel;
    private HeroActionPanel _heroPanel;

    void Start()
    {
        _outline = new SelectionOutline();

        var upgradePrefabs = new Dictionary<string, GameObject>
        {
            { "tack100", tack100Prefab },
            { "tack200", tack200Prefab },
            { "tack010", tack010Prefab },
            { "tack001", tack001Prefab },
        };

        var upgradeSetup = new Dictionary<string, Action<GameObject>>
        {
            { "tack100", tower =>
                {
                    var attack = tower.AddComponent<TackAttack>();
                    attack.damage = 0;
                    attack.strategy = new FireballBurstStrategy();
                }
            },
            { "tack200", tower =>
                {
                    var attack = tower.AddComponent<TackAttack>();
                    attack.range = 2f;
                    attack.damage = 3;
                    attack.pierce = 20;
                    attack.strategy = new AreaPulseStrategy { applyBurn = true };
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
                    attack.pierce = 2;
                    attack.strategy = new AirPuffBurstStrategy();
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

        BuildUI(upgradePrefabs, upgradeSetup);
    }

    void BuildUI(Dictionary<string, GameObject> upgradePrefabs, Dictionary<string, Action<GameObject>> upgradeSetup)
    {
        var panelCanvas = UIBuilder.Canvas("SelectionUI", 10);

        _actionPanelRoot = new GameObject("ActionPanel");
        _actionPanelRoot.transform.SetParent(panelCanvas.transform, false);

        var prt = _actionPanelRoot.AddComponent<RectTransform>();
        prt.anchorMin = new Vector2(1, 0.3f);
        prt.anchorMax = new Vector2(1, 0.7f);
        prt.pivot = new Vector2(1, 0.5f);
        prt.anchoredPosition = Vector2.zero;
        prt.sizeDelta = new Vector2(220, 0);

        _actionPanelRoot.AddComponent<Image>().color = new Color(0.627f, 0.322f, 0.176f, 0.95f);

        _towerPanel = new TowerActionPanel(_actionPanelRoot.transform, upgradePrefabs, upgradeSetup,
            onDeselected: Deselect, onUpgraded: Select);
        _heroPanel = new HeroActionPanel(_actionPanelRoot.transform, onDeselected: Deselect);

        _heroPanel.SetVisible(false);
        _actionPanelRoot.SetActive(false);
    }

    void Update()
    {
        HandleKeyboardShortcuts();

        if (_selectedTower != null)
        {
            if (_selectedTower.GetComponent<Hero>() != null) _heroPanel.Refresh();
            else _towerPanel.Refresh();
        }

        if (Mouse.current == null || !Mouse.current.leftButton.wasPressedThisFrame) return;

        var placer = FindAnyObjectByType<TowerPlacer>();
        if (placer != null && placer.IsPlacing) return;

        if (_actionPanelRoot != null && _actionPanelRoot.activeSelf)
        {
            RectTransform panelRect = _actionPanelRoot.GetComponent<RectTransform>();
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
            foreach (var td in FindObjectsByType<TowerData>(FindObjectsInactive.Exclude))
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
            foreach (var h in FindObjectsByType<Hero>(FindObjectsInactive.Exclude))
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
        if (_selectedTower.GetComponent<Hero>() != null) return;

        var kb = Keyboard.current;
        if (kb == null) return;

        if (kb.digit1Key.wasPressedThisFrame) _towerPanel.Upgrade(1);
        else if (kb.digit2Key.wasPressedThisFrame) _towerPanel.Upgrade(2);
        else if (kb.digit3Key.wasPressedThisFrame) _towerPanel.Upgrade(3);
        else if (kb.qKey.wasPressedThisFrame) _towerPanel.Sell();
    }

    public void Select(GameObject selected)
    {
        if (_selectedTower == selected) return;
        Deselect();
        _selectedTower = selected;
        _outline.Add(selected);
        ShowRangeIndicator();
        _actionPanelRoot.SetActive(true);

        bool isHero = selected.GetComponent<Hero>() != null;
        _towerPanel.SetVisible(!isHero);
        _heroPanel.SetVisible(isHero);

        if (isHero)
        {
            _heroPanel.SetHero(selected.GetComponent<Hero>());
            _heroPanel.Refresh();
        }
        else
        {
            _towerPanel.SetTower(selected);
            _towerPanel.Refresh();
        }
    }

    public void Deselect()
    {
        if (_selectedTower == null) return;
        _outline.Clear();
        HideRangeIndicator();
        _actionPanelRoot.SetActive(false);
        _towerPanel.SetTower(null);
        _heroPanel.SetHero(null);
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
}
