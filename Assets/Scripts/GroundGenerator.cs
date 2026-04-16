using UnityEngine;

[RequireComponent(typeof(MeshFilter), typeof(MeshRenderer), typeof(BoxCollider))]
public class GroundGenerator : MonoBehaviour
{
    [SerializeField] private int _xSegments = 80;
    [SerializeField] private int _zSegments = 60;
    [SerializeField] private float _width = 20f;
    [SerializeField] private float _depth = 15f;
    [SerializeField] private float _noiseScale = 0.3f;
    [SerializeField] private float _noiseHeight = 0.15f;
    [SerializeField] private float _seed = 42f;

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

                float n1 = Mathf.PerlinNoise((xPos + _seed) * _noiseScale, (zPos + _seed) * _noiseScale);
                float n2 = Mathf.PerlinNoise((xPos + _seed) * _noiseScale * 2.5f, (zPos + _seed) * _noiseScale * 2.5f);
                float y = n1 * _noiseHeight + n2 * _noiseHeight * 0.3f;

                int index = z * vertCountX + x;
                vertices[index] = new Vector3(xPos, y, zPos);
                uvs[index] = new Vector2(xPos * 0.5f, zPos * 0.5f);
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
        int size = 256;
        Texture2D tex = new Texture2D(size, size);
        tex.filterMode = FilterMode.Point;

        Color grassGreen = new Color(0.3f, 0.65f, 0.2f);
        Color grassDark = new Color(0.18f, 0.45f, 0.12f);
        Color grassLight = new Color(0.45f, 0.8f, 0.3f);
        Color clover = new Color(0.22f, 0.55f, 0.18f);

        for (int y = 0; y < size; y++)
        {
            for (int x = 0; x < size; x++)
            {
                float fx = x / (float)size;
                float fy = y / (float)size;

                // Large patches
                float n1 = Mathf.PerlinNoise(fx * 6f + 10f, fy * 6f + 10f);
                // Medium detail
                float n2 = Mathf.PerlinNoise(fx * 15f + 30f, fy * 15f + 30f);
                // Fine grass blades
                float n3 = Mathf.PerlinNoise(fx * 40f, fy * 40f);

                Color c = Color.Lerp(grassDark, grassLight, n1);
                c = Color.Lerp(c, grassGreen, n2 * 0.4f);

                // Grass blade highlights
                if (n3 > 0.6f)
                    c = Color.Lerp(c, grassLight, (n3 - 0.6f) * 1.5f);

                // Dark clover patches
                float patch = Mathf.PerlinNoise(fx * 10f + 70f, fy * 10f + 70f);
                if (patch > 0.65f)
                    c = Color.Lerp(c, clover, (patch - 0.65f) * 2f);

                // Slight yellow flowers scattered
                float flower = Mathf.PerlinNoise(fx * 50f + 200f, fy * 50f + 200f);
                if (flower > 0.82f)
                    c = Color.Lerp(c, new Color(0.85f, 0.85f, 0.25f), 0.5f);

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

    void SetupCollider()
    {
        BoxCollider col = GetComponent<BoxCollider>();
        col.center = new Vector3(_width / 2f, 0f, _depth / 2f);
        col.size = new Vector3(_width, 0.01f, _depth);
    }
}
