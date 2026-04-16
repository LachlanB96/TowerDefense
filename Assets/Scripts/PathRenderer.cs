using UnityEngine;

[ExecuteAlways]
[RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
public class PathRenderer : MonoBehaviour
{
    [SerializeField] private Transform _waypoints;
    [SerializeField] private float _pathWidth = 1.5f;
    [SerializeField] private float _pathHeight = 0.05f;

    private bool _generated;

    void OnEnable()
    {
        Regenerate();
    }

    void Regenerate()
    {
        if (_waypoints == null || _waypoints.childCount < 2) return;
        GenerateMesh();
        GenerateMaterial();
        _generated = true;
    }

    void GenerateMesh()
    {
        int count = _waypoints.childCount;
        if (count < 2) return;

        Vector3[] points = new Vector3[count];
        for (int i = 0; i < count; i++)
            points[i] = _waypoints.GetChild(i).position;

        Vector3[] vertices = new Vector3[count * 2];
        Vector2[] uvs = new Vector2[count * 2];
        int[] triangles = new int[(count - 1) * 6];

        float halfW = _pathWidth / 2f;
        float uvDist = 0f;

        for (int i = 0; i < count; i++)
        {
            Vector3 forward;
            if (i == 0)
                forward = (points[1] - points[0]).normalized;
            else if (i == count - 1)
                forward = (points[i] - points[i - 1]).normalized;
            else
                forward = ((points[i + 1] - points[i]).normalized + (points[i] - points[i - 1]).normalized).normalized;

            Vector3 right = Vector3.Cross(Vector3.up, forward).normalized * halfW;
            float y = _pathHeight;

            vertices[i * 2] = points[i] + right + Vector3.up * y;
            vertices[i * 2 + 1] = points[i] - right + Vector3.up * y;

            if (i > 0)
                uvDist += Vector3.Distance(points[i], points[i - 1]);

            float v = uvDist / _pathWidth;
            uvs[i * 2] = new Vector2(0, v);
            uvs[i * 2 + 1] = new Vector2(1, v);
        }

        for (int i = 0; i < count - 1; i++)
        {
            int vi = i * 2;
            int ti = i * 6;
            triangles[ti] = vi;
            triangles[ti + 1] = vi + 1;
            triangles[ti + 2] = vi + 2;
            triangles[ti + 3] = vi + 1;
            triangles[ti + 4] = vi + 3;
            triangles[ti + 5] = vi + 2;
        }

        Mesh mesh = new Mesh();
        mesh.name = "PathMesh";
        mesh.vertices = vertices;
        mesh.uv = uvs;
        mesh.triangles = triangles;
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();

        GetComponent<MeshFilter>().mesh = mesh;
    }

    void GenerateMaterial()
    {
        int size = 128;
        Texture2D tex = new Texture2D(size, size);
        tex.filterMode = FilterMode.Point;

        Color sandBase = new Color(0.82f, 0.72f, 0.55f);
        Color sandDark = new Color(0.7f, 0.6f, 0.42f);
        Color sandLight = new Color(0.9f, 0.82f, 0.65f);

        for (int y = 0; y < size; y++)
        {
            for (int x = 0; x < size; x++)
            {
                float n1 = Mathf.PerlinNoise(x * 0.08f + 50f, y * 0.08f + 50f);
                float n2 = Mathf.PerlinNoise(x * 0.2f + 100f, y * 0.2f + 100f);
                float t = n1 * 0.7f + n2 * 0.3f;
                Color c = Color.Lerp(sandDark, sandLight, t);

                // Add small pebble-like dots
                float dot = Mathf.PerlinNoise(x * 0.5f, y * 0.5f);
                if (dot > 0.7f)
                    c = Color.Lerp(c, sandDark, 0.3f);

                tex.SetPixel(x, y, c);
            }
        }
        tex.Apply();
        tex.wrapMode = TextureWrapMode.Repeat;

        var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        mat.SetTexture("_BaseMap", tex);
        mat.SetFloat("_Smoothness", 0.05f);

        GetComponent<MeshRenderer>().material = mat;
    }
}
