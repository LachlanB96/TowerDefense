using UnityEngine;

public class NatureAttack : MonoBehaviour
{
    public float range = 3f;
    public float cooldown = 2f;
    public int damage = 1;
    public float treeLifetime = 10f;

    private float _lastPlaceTime = -999f;
    private Transform _waypoints;
    private float _pathWidth;

    void Start()
    {
        var pathRenderer = FindAnyObjectByType<PathRenderer>();
        if (pathRenderer != null)
        {
            var wpField = typeof(PathRenderer).GetField("_waypoints",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            var widthField = typeof(PathRenderer).GetField("_pathWidth",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            if (wpField != null)
                _waypoints = wpField.GetValue(pathRenderer) as Transform;
            if (widthField != null)
                _pathWidth = (float)widthField.GetValue(pathRenderer);
        }
    }

    void Update()
    {
        if (Time.time - _lastPlaceTime < cooldown) return;
        if (_waypoints == null || _waypoints.childCount < 2) return;

        Vector3? spot = FindRandomPathSpotInRange();
        if (spot.HasValue)
        {
            _lastPlaceTime = Time.time;
            SpawnTree(spot.Value);
        }
    }

    Vector3? FindRandomPathSpotInRange()
    {
        // Collect all path segments within range
        var candidates = new System.Collections.Generic.List<(Vector3 a, Vector3 b)>();

        for (int i = 0; i < _waypoints.childCount - 1; i++)
        {
            Vector3 a = _waypoints.GetChild(i).position;
            Vector3 b = _waypoints.GetChild(i + 1).position;

            // Check if any part of this segment is within range
            Vector3 closest = ClosestPointOnSegment(transform.position, a, b);
            float dist = Vector3.Distance(
                new Vector3(transform.position.x, 0, transform.position.z),
                new Vector3(closest.x, 0, closest.z));
            if (dist <= range)
                candidates.Add((a, b));
        }

        if (candidates.Count == 0) return null;

        // Try a few random spots on candidate segments
        for (int attempt = 0; attempt < 10; attempt++)
        {
            var (a, b) = candidates[Random.Range(0, candidates.Count)];
            float t = Random.Range(0f, 1f);
            Vector3 pointOnPath = Vector3.Lerp(a, b, t);

            // Offset sideways randomly within path width
            Vector3 dir = (b - a).normalized;
            Vector3 right = Vector3.Cross(Vector3.up, dir).normalized;
            float offset = Random.Range(-_pathWidth * 0.3f, _pathWidth * 0.3f);
            pointOnPath += right * offset;

            // Check it's actually within range
            float dist = Vector3.Distance(
                new Vector3(transform.position.x, 0, transform.position.z),
                new Vector3(pointOnPath.x, 0, pointOnPath.z));
            if (dist <= range)
            {
                pointOnPath.y = a.y + 0.06f;
                return pointOnPath;
            }
        }

        return null;
    }

    Vector3 ClosestPointOnSegment(Vector3 p, Vector3 a, Vector3 b)
    {
        Vector3 ab = b - a;
        float t = Mathf.Clamp01(Vector3.Dot(p - a, ab) / ab.sqrMagnitude);
        return a + ab * t;
    }

    void SpawnTree(Vector3 position)
    {
        GameObject tree = new GameObject("PathTree");
        tree.transform.position = position;

        // Trunk
        GameObject trunk = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        trunk.transform.SetParent(tree.transform, false);
        trunk.transform.localPosition = new Vector3(0, 0.15f, 0);
        trunk.transform.localScale = new Vector3(0.08f, 0.15f, 0.08f);
        Destroy(trunk.GetComponent<Collider>());
        var trunkMat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        trunkMat.SetColor("_BaseColor", new Color(0.4f, 0.25f, 0.1f));
        trunk.GetComponent<Renderer>().sharedMaterial = trunkMat;

        // Canopy (three layered cones)
        var canopyMat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        canopyMat.SetColor("_BaseColor", new Color(0.15f, 0.55f, 0.1f));

        float[] heights = { 0.25f, 0.38f, 0.50f };
        float[] scales = { 0.35f, 0.28f, 0.20f };

        for (int i = 0; i < 3; i++)
        {
            GameObject leaf = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            leaf.transform.SetParent(tree.transform, false);
            leaf.transform.localPosition = new Vector3(0, heights[i], 0);
            leaf.transform.localScale = new Vector3(scales[i], 0.15f, scales[i]);
            Destroy(leaf.GetComponent<Collider>());
            leaf.GetComponent<Renderer>().sharedMaterial = canopyMat;
        }

        PathTree pt = tree.AddComponent<PathTree>();
        pt.damage = damage;
        pt.lifetime = treeLifetime;
    }
}
