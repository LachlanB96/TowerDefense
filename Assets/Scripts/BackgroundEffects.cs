using System.Collections.Generic;
using UnityEngine;

public class BackgroundEffects : MonoBehaviour
{
    [Header("Particles")]
    [SerializeField] private int _maxParticles = 35;
    [SerializeField] private float _particleSpawnInterval = 0.4f;
    [SerializeField] private float _particleLifetime = 7f;

    [Header("Lights")]
    [SerializeField] private int _maxLights = 8;
    [SerializeField] private float _lightSpawnInterval = 1.2f;
    [SerializeField] private float _lightLifetime = 3.5f;

    private float _groundWidth = 20f;
    private float _groundDepth = 15f;
    private Vector3 _groundCenter;
    private float _lastParticleTime;
    private float _lastLightTime;

    private Material _particleMat;
    private Transform _container;
    private readonly List<Particle> _particles = new List<Particle>();
    private readonly List<GlowLight> _lights = new List<GlowLight>();

    // Dim glowing colors against black
    private static readonly Color[] ParticleColors =
    {
        new Color(0.3f, 0.1f, 0.5f),    // purple
        new Color(0.1f, 0.2f, 0.45f),   // blue
        new Color(0.45f, 0.08f, 0.12f), // red
        new Color(0.08f, 0.35f, 0.28f), // teal
        new Color(0.25f, 0.08f, 0.4f),  // indigo
        new Color(0.4f, 0.22f, 0.05f),  // ember
    };

    private static readonly Color[] LightColors =
    {
        new Color(0.7f, 0.2f, 0.9f),    // purple
        new Color(0.2f, 0.4f, 0.9f),    // blue
        new Color(0.9f, 0.15f, 0.2f),   // red
        new Color(0.15f, 0.75f, 0.55f), // teal
        new Color(0.9f, 0.5f, 0.1f),    // amber
        new Color(0.5f, 0.2f, 0.85f),   // indigo
    };

    class Particle
    {
        public GameObject go;
        public float spawnTime;
        public float lifetime;
        public Vector3 drift;
        public float rotSpeed;
        public Color baseColor;
        public Renderer renderer;
        public MaterialPropertyBlock mpb;
    }

    class GlowLight
    {
        public GameObject go;
        public Light light;
        public Renderer orb;
        public MaterialPropertyBlock orbMpb;
        public Color color;
        public float spawnTime;
        public float lifetime;
        public float maxIntensity;
    }

    void Start()
    {
        var ground = FindAnyObjectByType<GroundGenerator>();
        if (ground != null)
        {
            var col = ground.GetComponent<BoxCollider>();
            if (col != null)
            {
                _groundWidth = col.size.x;
                _groundDepth = col.size.z;
                _groundCenter = ground.transform.position + col.center;
            }
        }

        _container = new GameObject("_BG_Effects").transform;

        // Unlit material for glowing particles
        _particleMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        MaterialUtils.MakeTransparent(_particleMat);
        _particleMat.renderQueue = 2999;
    }

    void Update()
    {
        if (Time.time - _lastParticleTime > _particleSpawnInterval && _particles.Count < _maxParticles)
        {
            _lastParticleTime = Time.time;
            SpawnParticle();
        }

        if (Time.time - _lastLightTime > _lightSpawnInterval && _lights.Count < _maxLights)
        {
            _lastLightTime = Time.time;
            SpawnGlowLight();
        }

        UpdateParticles();
        UpdateGlowLights();
    }

    void UpdateParticles()
    {
        for (int i = _particles.Count - 1; i >= 0; i--)
        {
            var p = _particles[i];
            float age = Time.time - p.spawnTime;

            if (age >= p.lifetime)
            {
                Destroy(p.go);
                _particles.RemoveAt(i);
                continue;
            }

            p.go.transform.position += p.drift * Time.deltaTime;
            p.go.transform.Rotate(p.rotSpeed * Time.deltaTime, p.rotSpeed * 0.7f * Time.deltaTime, 0f);

            // Breathe: scale pulses slowly
            float breathe = 1f + Mathf.Sin(age * 1.5f) * 0.15f;
            float baseSize = p.go.transform.localScale.x; // approximate
            // skip re-scaling to avoid drift, just affect alpha

            // Fade in → hold → fade out
            float t = age / p.lifetime;
            float alpha;
            if (t < 0.15f)
                alpha = t / 0.15f;
            else if (t > 0.7f)
                alpha = (1f - t) / 0.3f;
            else
                alpha = 1f;

            // Subtle flicker, keep translucent
            alpha *= 0.35f + Mathf.Sin(age * 3f) * 0.1f + Mathf.Sin(age * 7f) * 0.05f;
            alpha = Mathf.Clamp01(alpha);

            p.mpb.SetColor("_BaseColor", new Color(p.baseColor.r, p.baseColor.g, p.baseColor.b, alpha));
            p.renderer.SetPropertyBlock(p.mpb);
        }
    }

    void UpdateGlowLights()
    {
        for (int i = _lights.Count - 1; i >= 0; i--)
        {
            var gl = _lights[i];
            float age = Time.time - gl.spawnTime;

            if (age >= gl.lifetime)
            {
                Destroy(gl.go);
                _lights.RemoveAt(i);
                continue;
            }

            float t = age / gl.lifetime;
            float intensity;
            if (t < 0.2f)
                intensity = t / 0.2f;
            else if (t > 0.55f)
                intensity = (1f - t) / 0.45f;
            else
                intensity = 1f;

            // Flicker
            float flicker = 1f + Mathf.Sin(age * 14f) * 0.2f + Mathf.Sin(age * 23f) * 0.1f;
            float finalIntensity = gl.maxIntensity * intensity * flicker;
            gl.light.intensity = finalIntensity;

            // Update orb glow to match
            if (gl.orb != null)
            {
                float orbAlpha = Mathf.Clamp01(intensity * flicker * 0.8f);
                gl.orbMpb.SetColor("_BaseColor", new Color(gl.color.r * 1.5f, gl.color.g * 1.5f, gl.color.b * 1.5f, orbAlpha));
                gl.orb.SetPropertyBlock(gl.orbMpb);

                // Pulse scale
                float scale = (0.2f + intensity * 0.15f) * flicker;
                gl.orb.transform.localScale = Vector3.one * scale;
            }
        }
    }

    void SpawnParticle()
    {
        Vector3 pos = GetRandomVoidPosition();

        // Random shapes
        PrimitiveType shape;
        float roll = Random.value;
        if (roll < 0.5f) shape = PrimitiveType.Sphere;
        else if (roll < 0.8f) shape = PrimitiveType.Capsule;
        else shape = PrimitiveType.Cube;

        var go = GameObject.CreatePrimitive(shape);
        go.name = "_bgParticle";
        Destroy(go.GetComponent<Collider>());
        go.transform.SetParent(_container, false);
        go.transform.position = pos;

        float size = Random.Range(0.15f, 0.5f);
        go.transform.localScale = new Vector3(
            size * Random.Range(0.5f, 1.5f),
            size * Random.Range(0.3f, 1.2f),
            size * Random.Range(0.5f, 1.5f));
        go.transform.rotation = Random.rotation;

        var r = go.GetComponent<Renderer>();
        r.sharedMaterial = _particleMat;
        r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        r.receiveShadows = false;

        Color col = ParticleColors[Random.Range(0, ParticleColors.Length)];
        var mpb = new MaterialPropertyBlock();
        mpb.SetColor("_BaseColor", new Color(col.r, col.g, col.b, 0f));
        r.SetPropertyBlock(mpb);

        _particles.Add(new Particle
        {
            go = go,
            spawnTime = Time.time,
            lifetime = _particleLifetime + Random.Range(-2f, 3f),
            drift = new Vector3(Random.Range(-0.2f, 0.2f), Random.Range(-0.05f, 0.1f), Random.Range(-0.2f, 0.2f)),
            rotSpeed = Random.Range(-20f, 20f),
            baseColor = col,
            renderer = r,
            mpb = mpb
        });
    }

    void SpawnGlowLight()
    {
        Vector3 pos = GetRandomVoidPosition();
        pos.y = Random.Range(0.2f, 2.5f);

        Color col = LightColors[Random.Range(0, LightColors.Length)];

        var go = new GameObject("_bgGlow");
        go.transform.SetParent(_container, false);
        go.transform.position = pos;

        // Point light
        var light = go.AddComponent<Light>();
        light.type = LightType.Point;
        light.color = col;
        light.range = Random.Range(3f, 7f);
        light.intensity = 0f;
        light.shadows = LightShadows.None;

        // Visible glowing orb
        var orb = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        orb.name = "_orb";
        Destroy(orb.GetComponent<Collider>());
        orb.transform.SetParent(go.transform, false);
        orb.transform.localScale = Vector3.one * 0.3f;

        var orbR = orb.GetComponent<Renderer>();
        orbR.sharedMaterial = _particleMat;
        orbR.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        orbR.receiveShadows = false;

        var orbMpb = new MaterialPropertyBlock();
        orbMpb.SetColor("_BaseColor", new Color(col.r * 2f, col.g * 2f, col.b * 2f, 0f));
        orbR.SetPropertyBlock(orbMpb);

        _lights.Add(new GlowLight
        {
            go = go,
            light = light,
            orb = orbR,
            orbMpb = orbMpb,
            color = col,
            spawnTime = Time.time,
            lifetime = _lightLifetime + Random.Range(-0.5f, 2f),
            maxIntensity = Random.Range(2f, 5f)
        });
    }

    Vector3 GetRandomVoidPosition()
    {
        // Spawn in the dark void areas around the ground edges
        // Ground goes from (0,0,0) to (20,0,15)
        float margin = 1f;
        float spread = 5f;

        int side = Random.Range(0, 4);
        float x, z;
        switch (side)
        {
            case 0: // left of ground
                x = Random.Range(-spread, -margin);
                z = Random.Range(-spread, _groundDepth + spread);
                break;
            case 1: // right of ground
                x = _groundWidth + Random.Range(margin, spread);
                z = Random.Range(-spread, _groundDepth + spread);
                break;
            case 2: // in front (camera side, negative Z)
                x = Random.Range(-spread, _groundWidth + spread);
                z = Random.Range(-spread * 1.5f, -margin);
                break;
            default: // behind ground
                x = Random.Range(-spread, _groundWidth + spread);
                z = _groundDepth + Random.Range(margin, spread);
                break;
        }

        return new Vector3(x, Random.Range(-0.5f, 1f), z);
    }
}
