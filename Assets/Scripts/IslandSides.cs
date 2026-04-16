using UnityEngine;

[RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
public class IslandSides : MonoBehaviour
{
    [SerializeField] private float _width = 20f;
    [SerializeField] private float _depth = 15f;
    [SerializeField] private float _sideHeight = 3f;
    [SerializeField] private float _taperInset = 0.8f;
    [SerializeField] private float _rimHeight = 0.15f;
    [SerializeField] private float _rimOutset = 0.12f;
    [SerializeField] private int _segments = 20;

    void Awake()
    {
        GenerateMesh();
        GenerateTexture();
    }

    void GenerateMesh()
    {
        Mesh mesh = new Mesh();
        mesh.name = "IslandSidesMesh";

        // Top corners of ground
        Vector3[] topCorners = {
            new Vector3(0, 0, 0),             // bottom-left
            new Vector3(_width, 0, 0),        // bottom-right
            new Vector3(_width, 0, _depth),   // top-right
            new Vector3(0, 0, _depth)         // top-left
        };

        // Bottom corners (tapered inward)
        Vector3[] bottomCorners = {
            new Vector3(_taperInset, -_sideHeight, _taperInset),
            new Vector3(_width - _taperInset, -_sideHeight, _taperInset),
            new Vector3(_width - _taperInset, -_sideHeight, _depth - _taperInset),
            new Vector3(_taperInset, -_sideHeight, _depth - _taperInset)
        };

        // Rim corners (slightly outward and raised)
        Vector3[] rimCorners = {
            new Vector3(-_rimOutset, _rimHeight, -_rimOutset),
            new Vector3(_width + _rimOutset, _rimHeight, -_rimOutset),
            new Vector3(_width + _rimOutset, _rimHeight, _depth + _rimOutset),
            new Vector3(-_rimOutset, _rimHeight, _depth + _rimOutset)
        };

        // Each side: rim top → ground edge → bottom edge
        // 4 sides × 2 quads each (rim face + dirt face) × subdivided
        var verts = new System.Collections.Generic.List<Vector3>();
        var uvs = new System.Collections.Generic.List<Vector2>();
        var tris = new System.Collections.Generic.List<int>();

        Vector3 center = new Vector3(_width / 2f, 0, _depth / 2f);

        for (int side = 0; side < 4; side++)
        {
            int next = (side + 1) % 4;

            Vector3 rimL = rimCorners[side];
            Vector3 rimR = rimCorners[next];
            Vector3 topL = topCorners[side];
            Vector3 topR = topCorners[next];
            Vector3 botL = bottomCorners[side];
            Vector3 botR = bottomCorners[next];

            // Determine outward direction for this side
            Vector3 sideMid = (topL + topR) / 2f;
            Vector3 outward = (sideMid - center).normalized;

            for (int i = 0; i < _segments; i++)
            {
                float t0 = (float)i / _segments;
                float t1 = (float)(i + 1) / _segments;

                // Rim face (small strip from rim to ground edge)
                Vector3 r0 = Vector3.Lerp(rimL, rimR, t0);
                Vector3 r1 = Vector3.Lerp(rimL, rimR, t1);
                Vector3 g0 = Vector3.Lerp(topL, topR, t0);
                Vector3 g1 = Vector3.Lerp(topL, topR, t1);

                int b = verts.Count;
                verts.Add(r0); uvs.Add(new Vector2(t0, 1f));
                verts.Add(r1); uvs.Add(new Vector2(t1, 1f));
                verts.Add(g0); uvs.Add(new Vector2(t0, 0.9f));
                verts.Add(g1); uvs.Add(new Vector2(t1, 0.9f));

                // Check winding: compute face normal and flip if pointing inward
                Vector3 faceNormal = Vector3.Cross(g0 - r0, r1 - r0);
                if (Vector3.Dot(faceNormal, outward) > 0)
                {
                    tris.Add(b); tris.Add(b + 2); tris.Add(b + 1);
                    tris.Add(b + 1); tris.Add(b + 2); tris.Add(b + 3);
                }
                else
                {
                    tris.Add(b); tris.Add(b + 1); tris.Add(b + 2);
                    tris.Add(b + 1); tris.Add(b + 3); tris.Add(b + 2);
                }

                // Dirt face (from ground edge to bottom)
                Vector3 b0 = Vector3.Lerp(botL, botR, t0);
                Vector3 b1 = Vector3.Lerp(botL, botR, t1);

                b = verts.Count;
                verts.Add(g0); uvs.Add(new Vector2(t0, 0.9f));
                verts.Add(g1); uvs.Add(new Vector2(t1, 0.9f));
                verts.Add(b0); uvs.Add(new Vector2(t0, 0f));
                verts.Add(b1); uvs.Add(new Vector2(t1, 0f));

                faceNormal = Vector3.Cross(b0 - g0, g1 - g0);
                if (Vector3.Dot(faceNormal, outward) > 0)
                {
                    tris.Add(b); tris.Add(b + 2); tris.Add(b + 1);
                    tris.Add(b + 1); tris.Add(b + 2); tris.Add(b + 3);
                }
                else
                {
                    tris.Add(b); tris.Add(b + 1); tris.Add(b + 2);
                    tris.Add(b + 1); tris.Add(b + 3); tris.Add(b + 2);
                }
            }
        }

        // Bottom face (facing downward)
        int bi = verts.Count;
        verts.Add(bottomCorners[0]); uvs.Add(new Vector2(0, 0));
        verts.Add(bottomCorners[1]); uvs.Add(new Vector2(1, 0));
        verts.Add(bottomCorners[2]); uvs.Add(new Vector2(1, 1));
        verts.Add(bottomCorners[3]); uvs.Add(new Vector2(0, 1));
        tris.Add(bi); tris.Add(bi + 2); tris.Add(bi + 1);
        tris.Add(bi); tris.Add(bi + 3); tris.Add(bi + 2);

        mesh.vertices = verts.ToArray();
        mesh.uv = uvs.ToArray();
        mesh.triangles = tris.ToArray();
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();

        GetComponent<MeshFilter>().mesh = mesh;
    }

    void GenerateTexture()
    {
        int size = 512;
        Texture2D tex = new Texture2D(size, size);
        tex.filterMode = FilterMode.Bilinear;

        // Colors for the cross-section layers
        Color rimGrey = new Color(0.35f, 0.35f, 0.38f);
        Color rimDark = new Color(0.28f, 0.28f, 0.30f);
        Color topSoil = new Color(0.35f, 0.22f, 0.10f);
        Color midDirt = new Color(0.72f, 0.45f, 0.20f);
        Color deepDirt = new Color(0.60f, 0.35f, 0.15f);
        Color rockBottom = new Color(0.40f, 0.28f, 0.15f);

        for (int y = 0; y < size; y++)
        {
            float v = (float)y / size; // 0 = bottom, 1 = top

            for (int x = 0; x < size; x++)
            {
                float u = (float)x / size;
                Color c;

                if (v > 0.9f)
                {
                    // Rim zone — grey stone
                    float rimT = (v - 0.9f) / 0.1f;
                    float n = Mathf.PerlinNoise(u * 20f + 100f, rimT * 5f + 100f);
                    c = Color.Lerp(rimDark, rimGrey, n);
                }
                else
                {
                    // Dirt zone (v from 0 to 0.9)
                    float dirtV = v / 0.9f; // normalize to 0..1

                    if (dirtV > 0.85f)
                    {
                        // Top soil — dark brown
                        c = topSoil;
                    }
                    else if (dirtV > 0.3f)
                    {
                        // Mid dirt — orange-brown
                        float t = (dirtV - 0.3f) / 0.55f;
                        float n = Mathf.PerlinNoise(u * 8f + 50f, dirtV * 8f + 50f);
                        c = Color.Lerp(midDirt, deepDirt, n * 0.4f);
                        // Add horizontal streaks for layered earth look
                        float streak = Mathf.PerlinNoise(u * 3f + 200f, dirtV * 30f + 200f);
                        c = Color.Lerp(c, deepDirt, streak * 0.3f);
                    }
                    else
                    {
                        // Bottom — darker rocky dirt
                        float n = Mathf.PerlinNoise(u * 10f + 150f, dirtV * 10f + 150f);
                        c = Color.Lerp(rockBottom, deepDirt, n * 0.3f);
                    }

                    // Add subtle noise across all dirt
                    float fine = Mathf.PerlinNoise(u * 25f + 300f, v * 25f + 300f);
                    c = Color.Lerp(c, c * 0.85f, (fine - 0.5f) * 0.3f);
                }

                tex.SetPixel(x, y, c);
            }
        }

        tex.Apply();
        tex.wrapMode = TextureWrapMode.Clamp;

        var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        mat.SetTexture("_BaseMap", tex);
        mat.SetFloat("_Smoothness", 0f);

        GetComponent<MeshRenderer>().material = mat;
    }
}
