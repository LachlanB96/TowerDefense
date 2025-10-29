using UnityEngine;

public class Velocity : MonoBehaviour
{
    public GameObject target;
    public float speed;
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        transform.position = Vector3.MoveTowards(transform.position, target.transform.position, speed);
        if (Vector3.Distance(transform.position, target.transform.position) < 0.1f)
        {
            Destroy(gameObject);
            target.GetComponent<Movement>().Hit(1);
        }
    }
}
