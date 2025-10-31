using UnityEngine;

public class Velocity : MonoBehaviour
{
    public GameObject target;
    public float speed;
    internal bool homing;

    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        if (homing)
        {
            transform.position = Vector3.MoveTowards(transform.position, target.transform.position, speed);
        }
        else if (!homing)
        {
            transform.Translate(Vector3.forward * speed);
        }
        
        if (Vector3.Distance(transform.position, target.transform.position) < 0.1f)
        {
            Destroy(gameObject);
            target.GetComponent<Movement>().Hit(1);
        }
    }
}
