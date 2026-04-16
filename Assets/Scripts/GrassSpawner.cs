using UnityEngine;

public class GrassSpawner : MonoBehaviour
{
    public GameObject grassPrefab;
    public int count = 40;
    public float minX = 0.5f;
    public float maxX = 19.5f;
    public float minZ = 0.5f;
    public float maxZ = 14.5f;
    public float minScale = 0.6f;
    public float maxScale = 1.2f;

    private Transform _waypoints;
    private float _pathWidth;
    private Bounds _houseBounds;
    private bool _hasHouse;

    void Start()
    {
        var pathRenderer = FindAnyObjectByType<PathRenderer>();
        if (pathRenderer != null)
        {
            _waypoints = pathRenderer.Waypoints;
            _pathWidth = pathRenderer.PathWidth;
        }

        var house = GameObject.Find("BlueHouse");
        if (house != null)
        {
            _hasHouse = true;
            var renderers = house.GetComponentsInChildren<Renderer>();
            _houseBounds = renderers[0].bounds;
            foreach (var r in renderers)
                _houseBounds.Encapsulate(r.bounds);
            // Expand slightly so grass doesn't clip the edges
            _houseBounds.Expand(1f);
        }

        int spawned = 0;
        int attempts = 0;
        while (spawned < count && attempts < count * 10)
        {
            attempts++;
            float x = Random.Range(minX, maxX);
            float z = Random.Range(minZ, maxZ);

            if (IsOnPath(x, z) || IsInHouse(x, z))
                continue;

            float y = 0.05f;
            if (Physics.Raycast(new Vector3(x, 10f, z), Vector3.down, out RaycastHit hit, 20f))
                y = hit.point.y + 0.05f;

            float yOffset = Random.Range(-0.25f, -0.1f);
            GameObject grass = Instantiate(grassPrefab, new Vector3(x, y + yOffset, z), Quaternion.Euler(0, Random.Range(0f, 360f), 0));
            float baseScale = Random.Range(minScale, maxScale);
            float heightScale = baseScale * Random.Range(0.7f, 1.4f);
            grass.transform.localScale = new Vector3(baseScale, heightScale, baseScale);
            grass.transform.SetParent(transform);
            grass.AddComponent<GrassAnimation>();
            spawned++;
        }
    }

    bool IsOnPath(float x, float z)
    {
        if (_waypoints == null || _waypoints.childCount < 2) return false;

        float halfWidth = _pathWidth / 2f + 0.5f;
        Vector2 pos = new Vector2(x, z);

        for (int i = 0; i < _waypoints.childCount - 1; i++)
        {
            Vector3 a = _waypoints.GetChild(i).position;
            Vector3 b = _waypoints.GetChild(i + 1).position;
            Vector2 a2 = new Vector2(a.x, a.z);
            Vector2 b2 = new Vector2(b.x, b.z);

            Vector2 ab = b2 - a2;
            float t = Mathf.Clamp01(Vector2.Dot(pos - a2, ab) / ab.sqrMagnitude);
            Vector2 closest = a2 + ab * t;
            if (Vector2.Distance(pos, closest) < halfWidth)
                return true;
        }
        return false;
    }

    bool IsInHouse(float x, float z)
    {
        if (!_hasHouse) return false;
        return x >= _houseBounds.min.x && x <= _houseBounds.max.x
            && z >= _houseBounds.min.z && z <= _houseBounds.max.z;
    }
}
