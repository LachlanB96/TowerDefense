using UnityEngine;
using UnityEngine.UI;

public static class FloatingText
{
    private static Canvas _canvas;

    public static void Spawn(Vector3 worldPos, string text, Color color,
        float duration = 1.2f, int fontSize = 28, bool floatUp = true, float floatDistance = 80f)
    {
        Canvas canvas = GetOrCreateCanvas();
        if (canvas == null || Camera.main == null) return;

        var go = new GameObject("FloatingText");
        go.transform.SetParent(canvas.transform, false);

        var txt = go.AddComponent<Text>();
        txt.text = text;
        txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        txt.fontSize = fontSize;
        txt.color = color;
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

        var anim = go.AddComponent<FloatingTextAnim>();
        anim.Init(rt, txt, outline, color, duration, floatUp, floatDistance);
    }

    static Canvas GetOrCreateCanvas()
    {
        if (_canvas != null) return _canvas;

        foreach (var c in Object.FindObjectsByType<Canvas>(FindObjectsSortMode.None))
        {
            if (c.renderMode == RenderMode.ScreenSpaceOverlay && c.sortingOrder >= 100)
            {
                _canvas = c;
                return c;
            }
        }

        var go = new GameObject("FloatingTextCanvas");
        Object.DontDestroyOnLoad(go);
        _canvas = go.AddComponent<Canvas>();
        _canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        _canvas.sortingOrder = 100;
        var scaler = go.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920, 1080);
        return _canvas;
    }
}

public class FloatingTextAnim : MonoBehaviour
{
    private RectTransform _rt;
    private Text _txt;
    private Outline _outline;
    private Color _baseColor;
    private float _duration;
    private bool _floatUp;
    private float _floatDistance;
    private Vector3 _startPos;
    private float _elapsed;

    public void Init(RectTransform rt, Text txt, Outline outline, Color baseColor,
        float duration, bool floatUp, float floatDistance)
    {
        _rt = rt;
        _txt = txt;
        _outline = outline;
        _baseColor = baseColor;
        _duration = duration;
        _floatUp = floatUp;
        _floatDistance = floatDistance;
        _startPos = rt.position;
    }

    void Update()
    {
        _elapsed += Time.deltaTime;
        float t = _elapsed / _duration;

        float dir = _floatUp ? 1f : -1f;
        _rt.position = _startPos + Vector3.up * (_floatDistance * t * dir);

        float alpha = t < 0.4f ? 1f : 1f - (t - 0.4f) / 0.6f;
        _txt.color = new Color(_baseColor.r, _baseColor.g, _baseColor.b, alpha);
        _outline.effectColor = new Color(0f, 0f, 0f, alpha);

        if (_elapsed >= _duration)
            Destroy(gameObject);
    }
}
