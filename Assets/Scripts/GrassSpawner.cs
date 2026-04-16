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

    void Start()
    {
        for (int i = 0; i < count; i++)
        {
            float x = Random.Range(minX, maxX);
            float z = Random.Range(minZ, maxZ);
            float y = 0f;

            if (Physics.Raycast(new Vector3(x, 10f, z), Vector3.down, out RaycastHit hit, 20f))
                y = hit.point.y + 0.05f;

            GameObject grass = Instantiate(grassPrefab, new Vector3(x, y, z), Quaternion.Euler(0, Random.Range(0f, 360f), 0));
            grass.transform.localScale = Vector3.one * Random.Range(minScale, maxScale);
            grass.transform.SetParent(transform);
            grass.AddComponent<GrassAnimation>();
        }
    }
}
