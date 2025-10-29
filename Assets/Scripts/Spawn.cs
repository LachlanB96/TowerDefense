using System.Collections.Generic;
using UnityEngine;

public class Spawn : MonoBehaviour
{

    public GameObject unit;
    private List<GameObject> spawnedUnits = new List<GameObject>();
    public GameObject Waypoints;

    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        SpawnUnit();
    }

    public void SpawnUnit()
    {
        print("Spawning unit");
        GameObject newUnit = Instantiate(unit, transform.position, Quaternion.identity);
        newUnit.GetComponent<Movement>().Waypoints = Waypoints;
        newUnit.transform.parent = transform;
        spawnedUnits.Add(newUnit);
    }

    public void SpawnYellowUnit()
    {
        print("Spawning yellow unit");
        GameObject newUnit = Instantiate(unit, transform.position, Quaternion.identity);
        newUnit.GetComponent<Movement>().Waypoints = Waypoints;
        newUnit.transform.parent = transform;
        spawnedUnits.Add(newUnit);
    }

    public List<GameObject> GetSpawnedUnits()
    {
        foreach (GameObject unit in spawnedUnits)
        {
            print(unit);
        }
        return spawnedUnits;
    }
}
