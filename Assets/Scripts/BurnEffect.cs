using UnityEngine;

public class BurnEffect : MonoBehaviour
{
    public float duration = 6f;
    public float tickInterval = 2f;
    public int tickDamage = 1;
    public TowerData source;

    private float _startTime;
    private float _lastTickTime;
    private GameObject _fireVisual;

    void Start()
    {
        _startTime = Time.time;
        _lastTickTime = Time.time;
        CreateFireVisual();
    }

    void Update()
    {
        if (Time.time - _startTime >= duration)
        {
            RemoveEffect();
            return;
        }

        if (Time.time - _lastTickTime >= tickInterval)
        {
            _lastTickTime = Time.time;
            var movement = GetComponent<Movement>();
            if (movement != null && movement.enabled)
            {
                var report = movement.Hit(tickDamage);
                if (source != null)
                    source.Credit(report.damageDealt, report.killed);
            }
        }

        AnimateFire();
    }

    void CreateFireVisual()
    {
        _fireVisual = new GameObject("_BurnFX");
        _fireVisual.transform.SetParent(transform, false);
        _fireVisual.transform.localPosition = Vector3.up * 0.5f;

        // Inner flame glow
        var inner = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        inner.name = "_flame_inner";
        Destroy(inner.GetComponent<Collider>());
        inner.transform.SetParent(_fireVisual.transform, false);
        inner.transform.localScale = Vector3.one * 0.4f;

        var innerMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        innerMat.SetColor("_BaseColor", new Color(1f, 0.6f, 0.1f, 0.7f));
        MaterialUtils.MakeTransparent(innerMat);
        inner.GetComponent<Renderer>().material = innerMat;

        // Outer flame glow
        var outer = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        outer.name = "_flame_outer";
        Destroy(outer.GetComponent<Collider>());
        outer.transform.SetParent(_fireVisual.transform, false);
        outer.transform.localScale = Vector3.one * 0.65f;

        var outerMat = new Material(innerMat);
        outerMat.SetColor("_BaseColor", new Color(1f, 0.2f, 0.0f, 0.35f));
        outer.GetComponent<Renderer>().material = outerMat;

        // Tint the enemy's existing renderers orange
        foreach (var r in GetComponentsInChildren<Renderer>())
        {
            if (r.gameObject.name.StartsWith("_")) continue;
            foreach (var m in r.materials)
            {
                if (m.HasProperty("_BaseColor"))
                {
                    Color c = m.GetColor("_BaseColor");
                    m.SetColor("_BaseColor", Color.Lerp(c, new Color(1f, 0.3f, 0f), 0.4f));
                }
            }
        }
    }

    void AnimateFire()
    {
        if (_fireVisual == null) return;
        float t = (Time.time - _startTime) * 3f;
        float flicker = 1f + Mathf.Sin(t * 7f) * 0.15f + Mathf.Sin(t * 13f) * 0.1f;
        float fade = 1f - (Time.time - _startTime) / duration;

        foreach (Transform child in _fireVisual.transform)
        {
            child.localScale = child.name == "_flame_inner"
                ? Vector3.one * 0.4f * flicker
                : Vector3.one * 0.65f * flicker;
            child.localPosition = new Vector3(
                Mathf.Sin(t * 5f) * 0.05f,
                Mathf.Sin(t * 8f) * 0.1f,
                Mathf.Sin(t * 6f) * 0.05f);

            var renderer = child.GetComponent<Renderer>();
            if (renderer != null)
            {
                Color c = renderer.material.GetColor("_BaseColor");
                c.a = c.a > 0.5f ? 0.7f * fade : 0.35f * fade;
                renderer.material.SetColor("_BaseColor", c);
            }
        }
    }

    void RemoveEffect()
    {
        if (_fireVisual != null)
            Destroy(_fireVisual);
        Destroy(this);
    }
}
