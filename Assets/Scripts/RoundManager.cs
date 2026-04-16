using System.Collections;
using UnityEngine;
using UnityEngine.UI;

public class RoundManager : MonoBehaviour
{
    public float roundInterval = 10f;
    public float spawnDelay = 0.4f;

    private int _round;
    private float _timer;
    private Spawn _spawner;

    void Start()
    {
        _spawner = FindAnyObjectByType<Spawn>();
        StartRound();
    }

    void Update()
    {
        _timer += Time.deltaTime;
        if (_timer >= roundInterval)
            StartRound();
    }

    void StartRound()
    {
        _timer = 0f;
        _round++;
        ShowRoundText(_round);
        StartCoroutine(SpawnWave(_round));
    }

    IEnumerator SpawnWave(int round)
    {
        int small = 0;
        int big = 0;

        switch (round)
        {
            case 1: small = 5; break;
            case 2: big = 2; break;
            case 3: big = 3; small = 5; break;
            default:
                // Round 4: 5 big, 10 small. Each round after: +2 big, +5 small
                int extra = round - 4;
                big = 5 + extra * 2;
                small = 10 + extra * 5;
                break;
        }

        // Spawn big units first, then small
        for (int i = 0; i < big; i++)
        {
            _spawner.SpawnBigUnit();
            yield return new WaitForSeconds(spawnDelay);
        }
        for (int i = 0; i < small; i++)
        {
            _spawner.SpawnUnit();
            yield return new WaitForSeconds(spawnDelay);
        }
    }

    void ShowRoundText(int round)
    {
        var canvasObj = new GameObject("RoundCanvas");
        var canvas = canvasObj.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 200;
        canvasObj.AddComponent<CanvasScaler>().uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        canvasObj.GetComponent<CanvasScaler>().referenceResolution = new Vector2(1920, 1080);

        var go = new GameObject("RoundText");
        go.transform.SetParent(canvasObj.transform, false);

        var txt = go.AddComponent<Text>();
        txt.text = $"Round {round}";
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.fontSize = 72;
        txt.color = Color.white;
        txt.alignment = TextAnchor.MiddleCenter;
        txt.fontStyle = FontStyle.Bold;
        txt.raycastTarget = false;

        var outline = go.AddComponent<Outline>();
        outline.effectColor = Color.black;
        outline.effectDistance = new Vector2(3, -3);

        var rt = go.GetComponent<RectTransform>();
        rt.anchorMin = new Vector2(0.5f, 0.5f);
        rt.anchorMax = new Vector2(0.5f, 0.5f);
        rt.pivot = new Vector2(0.5f, 0.5f);
        rt.anchoredPosition = Vector2.zero;
        rt.sizeDelta = new Vector2(600, 100);

        var popup = go.AddComponent<RoundPopup>();
        popup.Init(rt, txt, outline, canvasObj);
    }
}

public class RoundPopup : MonoBehaviour
{
    private RectTransform _rt;
    private Text _txt;
    private Outline _outline;
    private GameObject _canvas;
    private float _elapsed;
    private const float Duration = 2.5f;

    public void Init(RectTransform rt, Text txt, Outline outline, GameObject canvas)
    {
        _rt = rt;
        _txt = txt;
        _outline = outline;
        _canvas = canvas;
    }

    void Update()
    {
        _elapsed += Time.deltaTime;
        float t = _elapsed / Duration;

        // Scale from 1 to 1.5 (zoom toward user)
        float scale = 1f + t * 0.5f;
        _rt.localScale = Vector3.one * scale;

        // Fade out after 40%
        float alpha = t < 0.4f ? 1f : 1f - (t - 0.4f) / 0.6f;
        _txt.color = new Color(1f, 1f, 1f, alpha);
        _outline.effectColor = new Color(0f, 0f, 0f, alpha);

        if (_elapsed >= Duration)
            Destroy(_canvas);
    }
}
