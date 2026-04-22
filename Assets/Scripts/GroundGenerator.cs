using UnityEngine;

[RequireComponent(typeof(MeshFilter), typeof(MeshRenderer), typeof(BoxCollider))]
public class GroundGenerator : MonoBehaviour
{
    [SerializeField] private int _xSegments = 80;
    [SerializeField] private int _zSegments = 60;
    [SerializeField] private float _width = 20f;
    [SerializeField] private float _depth = 15f;

    void Awake()
    {
        GenerateMesh();
        GenerateGrassTexture();
        SetupCollider();
    }

    void GenerateMesh()
    {
        Mesh mesh = new Mesh();
        mesh.name = "GroundMesh";

        int vertCountX = _xSegments + 1;
        int vertCountZ = _zSegments + 1;

        Vector3[] vertices = new Vector3[vertCountX * vertCountZ];
        Vector2[] uvs = new Vector2[vertices.Length];
        int[] triangles = new int[_xSegments * _zSegments * 6];

        for (int z = 0; z < vertCountZ; z++)
        {
            for (int x = 0; x < vertCountX; x++)
            {
                float xPos = (float)x / _xSegments * _width;
                float zPos = (float)z / _zSegments * _depth;

                float y = 0f;

                int index = z * vertCountX + x;
                vertices[index] = new Vector3(xPos, y, zPos);
                uvs[index] = new Vector2(xPos / _width, zPos / _depth);
            }
        }

        int tri = 0;
        for (int z = 0; z < _zSegments; z++)
        {
            for (int x = 0; x < _xSegments; x++)
            {
                int bl = z * vertCountX + x;
                int br = bl + 1;
                int tl = bl + vertCountX;
                int tr = tl + 1;

                triangles[tri++] = bl;
                triangles[tri++] = tl;
                triangles[tri++] = br;
                triangles[tri++] = br;
                triangles[tri++] = tl;
                triangles[tri++] = tr;
            }
        }

        mesh.vertices = vertices;
        mesh.uv = uvs;
        mesh.triangles = triangles;
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();

        GetComponent<MeshFilter>().mesh = mesh;
    }

    void GenerateGrassTexture()
    {
        int size = 2048;
        Texture2D tex = new Texture2D(size, size);
        tex.filterMode = FilterMode.Bilinear;

        // BTD-style bright, saturated cartoon greens
        Color mainGreen = new Color(0.30f, 0.72f, 0.18f);
        Color lightGreen = new Color(0.40f, 0.82f, 0.25f);
        Color darkGreen = new Color(0.22f, 0.58f, 0.12f);
        Color accentGreen = new Color(0.35f, 0.78f, 0.22f);

        for (int y = 0; y < size; y++)
        {
            for (int x = 0; x < size; x++)
            {
                float fx = x / (float)size;
                float fy = y / (float)size;

                // Large, soft patches — low frequency for clean cartoon look
                float broad = Mathf.PerlinNoise(fx * 2f + 5f, fy * 2f + 5f);
                Color c = Color.Lerp(darkGreen, lightGreen, broad);

                // Medium blobs for subtle variety
                float mid = Mathf.PerlinNoise(fx * 4f + 20f, fy * 4f + 20f);
                c = Color.Lerp(c, accentGreen, mid * 0.25f);

                // Soft radial lighter center (like BTD maps with lighter middle)
                float cx = fx - 0.5f;
                float cy = fy - 0.5f;
                float dist = Mathf.Sqrt(cx * cx + cy * cy);
                float vignette = Mathf.Clamp01(1f - dist * 0.6f);
                c = Color.Lerp(c, lightGreen, vignette * 0.15f);

                // Very subtle fine detail — just enough to avoid pure flat
                float fine = Mathf.PerlinNoise(fx * 12f + 50f, fy * 12f + 50f);
                c = Color.Lerp(c, mainGreen, (fine - 0.5f) * 0.1f);

                tex.SetPixel(x, y, c);
            }
        }
        tex.Apply();
        tex.wrapMode = TextureWrapMode.Clamp;

        var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        mat.SetTexture("_BaseMap", tex);
        mat.SetFloat("_Smoothness", 0.0f);

        GetComponent<MeshRenderer>().material = mat;
    }

    void SetupCollider()
    {
        BoxCollider col = GetComponent<BoxCollider>();
        col.center = new Vector3(_width / 2f, 0f, _depth / 2f);
        col.size = new Vector3(_width, 0.01f, _depth);
    }
}
