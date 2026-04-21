using UnityEngine;

/// <summary>
/// One-shot expanding + fading disc VFX used by the Boat for placement splash
/// and muzzle deck-splash. Designed to live on a flat cylinder prefab whose
/// Y scale is intentionally tiny (~0.02) so it reads as a water ring; only the
/// X and Z components are animated, never Y.
///
/// The GameObject self-destructs at the end of its lifetime.
/// </summary>
public class SplashRing : MonoBehaviour
{
    /// <summary>How long (seconds) the ring takes to finish expanding and fully fade out.</summary>
    public float lifetime = 0.4f;

    /// <summary>Initial XZ scale at t=0. Kept small so the ring appears to erupt from a point.</summary>
    public float startScale = 0.1f;

    /// <summary>Final XZ scale at t=lifetime. Linearly lerped from startScale.</summary>
    public float endScale = 1.0f;

    private float _elapsed;

    // Instance material clone (triggered by the first Renderer.material get), so tweaking
    // alpha here does not leak to other splash rings sharing the same source asset.
    private Material _mat;

    // Captured at Start so we can fade alpha off the prefab's authored color without
    // losing the RGB tint during the lerp.
    private Color _baseColor;

    void Start()
    {
        var r = GetComponent<Renderer>();
        if (r != null)
        {
            _mat = r.material;
            _baseColor = _mat.color;
        }

        // The prefab is authored as a flat disc (Y scale ~0.02). We animate only X and Z;
        // touching Y here would turn the ring into a tall cylinder on the first frame.
        transform.localScale = new Vector3(startScale, transform.localScale.y, startScale);
    }

    void Update()
    {
        _elapsed += Time.deltaTime;

        // u is the normalized progress through the animation (0 at spawn, 1 at end).
        float u = Mathf.Clamp01(_elapsed / lifetime);

        float s = Mathf.Lerp(startScale, endScale, u);
        transform.localScale = new Vector3(s, transform.localScale.y, s);

        // Fade alpha linearly with progress. Multiplying by _baseColor.a lets the prefab
        // set a starting opacity (e.g. 0.6) that we scale down to 0 over the lifetime.
        if (_mat != null)
        {
            var c = _baseColor;
            c.a = _baseColor.a * (1f - u);
            _mat.color = c;
        }

        if (_elapsed >= lifetime) Destroy(gameObject);
    }
}
