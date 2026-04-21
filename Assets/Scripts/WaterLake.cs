using UnityEngine;

[RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
public class WaterLake : MonoBehaviour
{
    [SerializeField] private float bobAmplitude = 0.05f;
    [SerializeField] private float bobFrequency = 1.2f;
    [SerializeField] private Color colorA = new Color(0.15f, 0.45f, 0.75f);
    [SerializeField] private Color colorB = new Color(0.20f, 0.55f, 0.85f);
    [SerializeField] private float colorFrequency = 0.5f;

    private Mesh _mesh;
    private Vector3[] _originalVerts;
    private Vector3[] _workingVerts;
    private Material _materialInstance;

    void Start()
    {
        var mf = GetComponent<MeshFilter>();
        if (mf == null || mf.sharedMesh == null) return;

        // Per-instance mesh copy so vertex mutation doesn't leak to the asset.
        _mesh = Instantiate(mf.sharedMesh);
        mf.mesh = _mesh;

        _originalVerts = _mesh.vertices;
        _workingVerts = new Vector3[_originalVerts.Length];

        _materialInstance = GetComponent<MeshRenderer>().material;
    }

    void Update()
    {
        if (_mesh == null) return;

        float t = Time.time;
        for (int i = 0; i < _originalVerts.Length; i++)
        {
            var o = _originalVerts[i];
            float phase = o.x * 0.8f + o.z * 1.2f;
            _workingVerts[i] = new Vector3(
                o.x,
                o.y + bobAmplitude * Mathf.Sin(t * bobFrequency + phase),
                o.z);
        }
        _mesh.vertices = _workingVerts;
        _mesh.RecalculateNormals();

        if (_materialInstance != null)
        {
            float k = 0.5f + 0.5f * Mathf.Sin(t * colorFrequency);
            _materialInstance.color = Color.Lerp(colorA, colorB, k);
        }
    }
}
