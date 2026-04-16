using System.Collections.Generic;
using UnityEngine;

[ExecuteAlways]
[RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
public class PathRenderer : MonoBehaviour
{
    [SerializeField] private Transform _waypoints;
    [SerializeField] private float _pathWidth = 1.5f;
    [SerializeField] private float _pathHeight = 0.12f;
    [SerializeField] private float _slopeWidth = 0.35f;

    public Transform Waypoints => _waypoints;
    public float PathWidth => _pathWidth;

    private List<GameObject> _borderObjects = new List<GameObject>();

    void OnEnable()
    {
        Regenerate();
    }

    void Regenerate()
    {
        if (_waypoints == null || _waypoints.childCount < 2) return;
        ClearBorder();
        GenerateMesh();
        GenerateMaterial();
        GenerateBorderRocks();
    }

    // ── Raised path mesh with beveled edges ─────────────────────────────────

    void GenerateMesh()
    {
        int count = _waypoints.childCount;
        if (count < 2) return;

        Vector3[] points = new Vector3[count];
        for (int i = 0; i < count; i++)
            points[i] = _waypoints.GetChild(i).position;

        // Cross-section profile (6 verts per waypoint):
        //  0: outer-left  (ground)
        //  1: slope-left   (mid height)
        //  2: top-left     (full height)
        //  3: top-right    (full height)
        //  4: slope-right  (mid height)
        //  5: outer-right  (ground)
        int vertsPerRow = 6;
        Vector3[] vertices = new Vector3[count * vertsPerRow];
        Vector2[] uvs = new Vector2[count * vertsPerRow];
        int[] triangles = new int[(count - 1) * (vertsPerRow - 1) * 6];

        float halfW = _pathWidth / 2f;
        float uvDist = 0f;

        // Profile offsets from center (x = lateral, y = height)
        float outerX = halfW + _slopeWidth;
        float slopeX = halfW;
        float topX = halfW - 0.05f;
        float slopeY = _pathHeight * 0.5f;

        // UV x positions for the profile
        float totalCrossWidth = outerX * 2f;
        float[] uOffsets = {
            0f,
            _slopeWidth / totalCrossWidth,
            (_slopeWidth + 0.05f) / totalCrossWidth,
            1f - (_slopeWidth + 0.05f) / totalCrossWidth,
            1f - _slopeWidth / totalCrossWidth,
            1f
        };

        for (int i = 0; i < count; i++)
        {
            Vector3 forward;
            if (i == 0)
                forward = (points[1] - points[0]).normalized;
            else if (i == count - 1)
                forward = (points[i] - points[i - 1]).normalized;
            else
                forward = ((points[i + 1] - points[i]).normalized + (points[i] - points[i - 1]).normalized).normalized;

            Vector3 right = Vector3.Cross(Vector3.up, forward).normalized;

            if (i > 0)
                uvDist += Vector3.Distance(points[i], points[i - 1]);
            float v = uvDist / _pathWidth;

            Vector3 p = points[i];
            int row = i * vertsPerRow;

            vertices[row + 0] = p + right * outerX;
            vertices[row + 1] = p + right * slopeX + Vector3.up * slopeY;
            vertices[row + 2] = p + right * topX + Vector3.up * _pathHeight;
            vertices[row + 3] = p - right * topX + Vector3.up * _pathHeight;
            vertices[row + 4] = p - right * slopeX + Vector3.up * slopeY;
            vertices[row + 5] = p - right * outerX;

            for (int j = 0; j < vertsPerRow; j++)
                uvs[row + j] = new Vector2(uOffsets[j], v);
        }

        int tri = 0;
        for (int i = 0; i < count - 1; i++)
        {
            int row = i * vertsPerRow;
            int nextRow = (i + 1) * vertsPerRow;
            for (int j = 0; j < vertsPerRow - 1; j++)
            {
                int bl = row + j;
                int br = row + j + 1;
                int tl = nextRow + j;
                int tr = nextRow + j + 1;

                triangles[tri++] = bl;
                triangles[tri++] = br;
                triangles[tri++] = tl;
                triangles[tri++] = br;
                triangles[tri++] = tr;
                triangles[tri++] = tl;
            }
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

    // ── Sand texture ────────────────────────────────────────────────────────

    void GenerateMaterial()
    {
        int size = 256;
        Texture2D tex = new Texture2D(size, size);
        tex.filterMode = FilterMode.Bilinear;

        Color sandA = new Color(0.78f, 0.68f, 0.50f);
        Color sandB = new Color(0.70f, 0.58f, 0.40f);
        Color sandC = new Color(0.86f, 0.78f, 0.62f);
        Color pebble = new Color(0.55f, 0.48f, 0.36f);

        for (int y = 0; y < size; y++)
        {
            for (int x = 0; x < size; x++)
            {
                // Large-scale variation
                float n1 = Mathf.PerlinNoise(x * 0.03f + 37f, y * 0.03f + 37f);
                // Medium grain
                float n2 = Mathf.PerlinNoise(x * 0.1f + 91f, y * 0.1f + 91f);
                // Fine grain
                float n3 = Mathf.PerlinNoise(x * 0.25f + 200f, y * 0.25f + 200f);
                // Ripple pattern (subtle wind lines)
                float ripple = Mathf.PerlinNoise(x * 0.02f + 50f, y * 0.15f + 50f);

                float t = n1 * 0.4f + n2 * 0.3f + n3 * 0.15f + ripple * 0.15f;
                Color c = Color.Lerp(sandB, sandC, t);

                // Darken edges (vignette across width for depth)
                float ux = (float)x / size;
                float edgeDarken = 1f - Mathf.Pow(Mathf.Abs(ux - 0.5f) * 2f, 3f) * 0.15f;
                c *= edgeDarken;

                // Scattered pebbles
                float pebbleNoise = Mathf.PerlinNoise(x * 0.4f + 300f, y * 0.4f + 300f);
                float pebbleDetail = Mathf.PerlinNoise(x * 0.8f + 500f, y * 0.8f + 500f);
                if (pebbleNoise > 0.72f && pebbleDetail > 0.45f)
                    c = Color.Lerp(c, pebble, 0.4f);

                // Tiny bright grains
                float grain = Mathf.PerlinNoise(x * 1.5f + 700f, y * 1.5f + 700f);
                if (grain > 0.78f)
                    c = Color.Lerp(c, sandC * 1.1f, 0.2f);

                tex.SetPixel(x, y, c);
            }
        }
        tex.Apply();
        tex.wrapMode = TextureWrapMode.Repeat;

        // Normal map from height
        Texture2D normal = GenerateNormalMap(tex, 1.5f);

        var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        mat.SetTexture("_BaseMap", tex);
        mat.SetTexture("_BumpMap", normal);
        mat.SetFloat("_BumpScale", 0.6f);
        mat.SetFloat("_Smoothness", 0.08f);

        GetComponent<MeshRenderer>().material = mat;
    }

    Texture2D GenerateNormalMap(Texture2D source, float strength)
    {
        int w = source.width;
        int h = source.height;
        var normal = new Texture2D(w, h, TextureFormat.RGBA32, false);
        normal.filterMode = FilterMode.Bilinear;
        normal.wrapMode = TextureWrapMode.Repeat;

        for (int y = 0; y < h; y++)
        {
            for (int x = 0; x < w; x++)
            {
                float left = source.GetPixel((x - 1 + w) % w, y).grayscale;
                float right = source.GetPixel((x + 1) % w, y).grayscale;
                float down = source.GetPixel(x, (y - 1 + h) % h).grayscale;
                float up = source.GetPixel(x, (y + 1) % h).grayscale;

                float dx = (left - right) * strength;
                float dy = (down - up) * strength;

                Vector3 n = new Vector3(dx, dy, 1f).normalized;
                normal.SetPixel(x, y, new Color(n.x * 0.5f + 0.5f, n.y * 0.5f + 0.5f, n.z * 0.5f + 0.5f, 1f));
            }
        }
        normal.Apply();
        return normal;
    }

    // ── Border rocks and sand mounds ────────────────────────────────────────

    void GenerateBorderRocks()
    {
        int count = _waypoints.childCount;
        if (count < 2) return;

        // Create parent for border objects
        var borderParent = new GameObject("_PathBorder");
        borderParent.transform.SetParent(transform, false);
        _borderObjects.Add(borderParent);

        // Rock material
        var rockMat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        rockMat.SetColor("_BaseColor", new Color(0.52f, 0.46f, 0.38f));
        rockMat.SetFloat("_Smoothness", 0.15f);

        // Sand mound material
        var moundMat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        moundMat.SetColor("_BaseColor", new Color(0.75f, 0.65f, 0.48f));
        moundMat.SetFloat("_Smoothness", 0.05f);

        float halfW = _pathWidth / 2f;

        // Walk along each segment and place rocks/mounds
        for (int i = 0; i < count - 1; i++)
        {
            Vector3 a = _waypoints.GetChild(i).position;
            Vector3 b = _waypoints.GetChild(i + 1).position;
            Vector3 dir = (b - a).normalized;
            Vector3 right = Vector3.Cross(Vector3.up, dir).normalized;
            float segLen = Vector3.Distance(a, b);

            // Place objects along the segment
            float spacing = 0.5f;
            int steps = Mathf.Max(1, Mathf.FloorToInt(segLen / spacing));

            for (int s = 0; s <= steps; s++)
            {
                float t = (float)s / steps;
                Vector3 center = Vector3.Lerp(a, b, t);

                // Deterministic random from position
                float seed = center.x * 73.17f + center.z * 91.53f + i * 37f;

                // Left side
                PlaceBorderObject(center, right, halfW, seed, borderParent.transform, rockMat, moundMat);
                // Right side
                PlaceBorderObject(center, -right, halfW, seed + 500f, borderParent.transform, rockMat, moundMat);
            }
        }
    }

    void PlaceBorderObject(Vector3 center, Vector3 outward, float halfW, float seed,
        Transform parent, Material rockMat, Material moundMat)
    {
        float rand1 = Frac(Mathf.Sin(seed) * 43758.5453f);
        float rand2 = Frac(Mathf.Sin(seed + 1f) * 22578.1459f);
        float rand3 = Frac(Mathf.Sin(seed + 2f) * 10003.2987f);
        float rand4 = Frac(Mathf.Sin(seed + 3f) * 67890.1234f);

        // Skip some spots for natural randomness
        if (rand1 < 0.55f) return;

        float edgeDist = halfW + _slopeWidth * (0.3f + rand2 * 0.7f);
        Vector3 pos = center + outward * edgeDist;
        pos.y = center.y + _pathHeight * 0.1f;

        if (rand3 > 0.4f)
        {
            // Rock
            var rock = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            rock.name = "_rock";
            if (Application.isPlaying)
                Destroy(rock.GetComponent<Collider>());
            else
                DestroyImmediate(rock.GetComponent<Collider>());
            rock.transform.SetParent(parent, false);
            rock.transform.position = pos;

            float scaleBase = 0.06f + rand4 * 0.1f;
            rock.transform.localScale = new Vector3(
                scaleBase * (0.8f + rand1 * 0.6f),
                scaleBase * (0.5f + rand2 * 0.4f),
                scaleBase * (0.8f + rand3 * 0.6f));
            rock.transform.rotation = Quaternion.Euler(rand1 * 30f, rand2 * 360f, rand3 * 20f);
            rock.GetComponent<Renderer>().sharedMaterial = rockMat;
        }
        else
        {
            // Sand mound
            var mound = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            mound.name = "_mound";
            if (Application.isPlaying)
                Destroy(mound.GetComponent<Collider>());
            else
                DestroyImmediate(mound.GetComponent<Collider>());
            mound.transform.SetParent(parent, false);
            mound.transform.position = pos;

            float sx = 0.15f + rand4 * 0.2f;
            mound.transform.localScale = new Vector3(sx, 0.04f + rand1 * 0.04f, sx * (0.7f + rand2 * 0.5f));
            mound.GetComponent<Renderer>().sharedMaterial = moundMat;
        }
    }

    float Frac(float v) { return v - Mathf.Floor(v); }

    void ClearBorder()
    {
        foreach (var obj in _borderObjects)
        {
            if (obj != null)
            {
                if (Application.isPlaying) Destroy(obj);
                else DestroyImmediate(obj);
            }
        }
        _borderObjects.Clear();

        // Also clean up any leftover border from previous runs
        for (int i = transform.childCount - 1; i >= 0; i--)
        {
            var child = transform.GetChild(i);
            if (child.name == "_PathBorder")
            {
                if (Application.isPlaying) Destroy(child.gameObject);
                else DestroyImmediate(child.gameObject);
            }
        }
    }
}
