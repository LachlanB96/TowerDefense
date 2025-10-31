using System;
using UnityEngine;

public class Movement : MonoBehaviour
{
    public GameObject Waypoints;
    private GameObject currentWaypoint;
    private int waypointIndex = 0;
    public float speed = 1.0f;

    private int health = 1;
    private int deaths = 0;
    public int insides = 1;
    void Start()
    {
        print("Hello, Unity Console!");
        Debug.Log("Hello, Unity Console!");
        Console.WriteLine("Movement script started");
        currentWaypoint = Waypoints.GetComponent<Transform>().GetChild(waypointIndex).gameObject;
    }

    public void Test()
    {
        print("Hello, Unity Console!");
        transform.position = Vector3.MoveTowards(transform.position, Vector3.zero, 30);
    }

    void Update()
    {
        if (Vector3.Distance(transform.position, currentWaypoint.transform.position) < 0.1f)
        {
            currentWaypoint = Waypoints.GetComponent<Transform>().GetChild(++waypointIndex % Waypoints.transform.childCount).gameObject;
        }
        transform.position = Vector3.MoveTowards(transform.position, currentWaypoint.transform.position, speed);
        transform.Rotate(new Vector3(1, 2, 3), 0.1f);
        //transform.position.z += 0.01f;
    }

    public void Death()
    {
        if (deaths == 0)
        {
            deaths++;
            for (int i = 0; i < insides; i++)
            {
                GameObject newUnit = Instantiate(gameObject, transform.position, Quaternion.identity);
                newUnit.transform.position += new Vector3(UnityEngine.Random.Range(-1f, 1f), UnityEngine.Random.Range(-1f, 1f), UnityEngine.Random.Range(-1f, 1f));
                newUnit.transform.parent = transform.parent;
            }
        }
        Destroy(gameObject);
    }

    internal void Hit(int v)
    {
        if (v >= health)
        {
            Death();
        }
    }
}
