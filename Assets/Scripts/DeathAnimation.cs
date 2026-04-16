using UnityEngine;

public class DeathAnimation : MonoBehaviour
{
    private Animator _animator;
    private float _timer;
    private float _fadeDuration = 1.5f;
    private float _shrinkDuration = 0.2f;
    private Renderer[] _renderers;
    private Material[][] _materials;
    private Vector3 _startScale;
    private float _groundY;

    void Start()
    {
        _animator = GetComponentInChildren<Animator>();

        if (_animator != null)
            _animator.SetTrigger("Die");

        _startScale = transform.localScale;
        _groundY = transform.position.y;

        // Collect all renderers and prepare materials for fading
        _renderers = GetComponentsInChildren<Renderer>();
        _materials = new Material[_renderers.Length][];
        for (int i = 0; i < _renderers.Length; i++)
        {
            _materials[i] = _renderers[i].materials;
        }

        // Immediately tint all materials black and make transparent
        foreach (var mats in _materials)
        {
            foreach (var mat in mats)
            {
                MakeTransparent(mat);
                if (mat.HasProperty("_BaseColor"))
                    mat.SetColor("_BaseColor", new Color(0f, 0f, 0f, 1f));
            }
        }
    }

    void Update()
    {
        _timer += Time.deltaTime;

        // Shrink to half over 0.2s, anchored to ground
        if (_timer < _shrinkDuration)
        {
            float shrinkT = Mathf.SmoothStep(0f, 1f, _timer / _shrinkDuration);
            float s = Mathf.Lerp(1f, 0.5f, shrinkT);
            transform.localScale = _startScale * s;

            // Keep bottom anchored: offset Y up by half the lost height
            float fullHeight = _startScale.y;
            float newHeight = fullHeight * s;
            float yOffset = (fullHeight - newHeight) * 0.5f;
            Vector3 pos = transform.position;
            pos.y = _groundY - yOffset;
            transform.position = pos;
        }

        float fadeT = Mathf.Clamp01(_timer / _fadeDuration);
        float alpha = 1f - fadeT;

        for (int i = 0; i < _renderers.Length; i++)
        {
            foreach (var mat in _materials[i])
            {
                if (mat.HasProperty("_BaseColor"))
                {
                    Color c = mat.GetColor("_BaseColor");
                    c.a = alpha;
                    mat.SetColor("_BaseColor", c);
                }
            }
        }

        if (_timer >= _fadeDuration)
        {
            Destroy(gameObject);
        }
    }

    void MakeTransparent(Material mat)
    {
        mat.SetFloat("_Surface", 1);
        mat.SetOverrideTag("RenderType", "Transparent");
        mat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
        mat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
        mat.SetInt("_ZWrite", 0);
        mat.renderQueue = 3000;
        mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
    }
}
