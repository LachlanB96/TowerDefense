using UnityEngine;

public class FlyOutward : MonoBehaviour
{
    public Vector3 direction;
    public float speed = 15f;
    public float lifetime = 0.5f;

    void Start()
    {
        Destroy(gameObject, lifetime);
    }

    void Update()
    {
        transform.position += direction * speed * Time.deltaTime;
    }
}
