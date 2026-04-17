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

    private PathRenderer _pathRenderer;
    private Bounds _houseBounds;
    private bool _hasHouse;

    void Start()
    {
        _pathRenderer = FindAnyObjectByType<PathRenderer>();

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
        if (_pathRenderer == null) return false;
        return _pathRenderer.IsPointOnPath(new Vector2(x, z), 0.5f);
    }

    bool IsInHouse(float x, float z)
    {
        if (!_hasHouse) return false;
        return x >= _houseBounds.min.x && x <= _houseBounds.max.x
            && z >= _houseBounds.min.z && z <= _houseBounds.max.z;
    }
}
