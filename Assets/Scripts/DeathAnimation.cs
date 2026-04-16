using UnityEngine;

public class DeathAnimation : MonoBehaviour
{
    private Animator _animator;
    private float _timer;
    private float _fadeDuration = 1.5f;
    private float _fadeDelay;
    private float _totalDuration;
    private Renderer[] _renderers;
    private Material[][] _materials;
    private bool _fading;

    void Start()
    {
        _animator = GetComponentInChildren<Animator>();

        if (_animator != null)
        {
            _animator.SetTrigger("Die");

            // Get the Die clip length to know when to destroy
            var clips = _animator.runtimeAnimatorController.animationClips;
            float dieLength = 0f;
            foreach (var clip in clips)
            {
                if (clip.name == "Die")
                {
                    dieLength = clip.length;
                    break;
                }
            }

            // Start fading partway through the animation (when it lies on the ground)
            _fadeDelay = dieLength * 0.55f;
            _totalDuration = _fadeDelay + _fadeDuration;
        }
        else
        {
            // Fallback if no animator
            _fadeDelay = 0.5f;
            _totalDuration = _fadeDelay + _fadeDuration;
        }

        // Collect all renderers and prepare materials for fading
        _renderers = GetComponentsInChildren<Renderer>();
        _materials = new Material[_renderers.Length][];
        for (int i = 0; i < _renderers.Length; i++)
        {
            _materials[i] = _renderers[i].materials;
        }
    }

    void Update()
    {
        _timer += Time.deltaTime;

        // Start fading after the fall portion of the animation
        if (_timer > _fadeDelay && !_fading)
        {
            _fading = true;
            foreach (var mats in _materials)
                foreach (var mat in mats)
                    MakeTransparent(mat);
        }

        if (_fading)
        {
            float fadeT = (_timer - _fadeDelay) / _fadeDuration;
            fadeT = Mathf.Clamp01(fadeT);
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
        }

        if (_timer >= _totalDuration)
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
