using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class Spawn : MonoBehaviour
{

    public GameObject unit;
    private List<GameObject> spawnedUnits = new List<GameObject>();
    public GameObject Waypoints;

    void Start()
    {
        var btn = GameObject.Find("SpawnUnitButton");
        if (btn != null)
            btn.GetComponent<Button>().onClick.AddListener(SpawnOne);

        var bigBtn = GameObject.Find("SpawnBigUnitButton");
        if (bigBtn != null)
            bigBtn.GetComponent<Button>().onClick.AddListener(SpawnBigUnit);
    }

    public void SpawnOne()
    {
        SpawnUnit(UIInit.CreepType.BaseCreep);
    }

    public void SpawnUnit(UIInit.CreepType type)
    {
        print("Spawning unit");
        GameObject newUnit = Instantiate(unit, transform.position, Quaternion.identity);
        newUnit.GetComponent<Movement>().Waypoints = Waypoints;
        newUnit.transform.parent = transform;
        newUnit.transform.localScale = Vector3.one;
        spawnedUnits.Add(newUnit);

        if (EconomyManager.Instance != null)
            EconomyManager.Instance.AddEconomy(1);
    }

    public void SpawnBigUnit()
    {
        print("Spawning big unit");
        GameObject newUnit = Instantiate(unit, transform.position, Quaternion.identity);
        newUnit.GetComponent<Movement>().Waypoints = Waypoints;
        newUnit.transform.parent = transform;
        newUnit.transform.localScale = Vector3.one * 2f;
        Movement m = newUnit.GetComponent<Movement>();
        m.health = 5;
        m.insides = 2;
        spawnedUnits.Add(newUnit);

        if (EconomyManager.Instance != null)
            EconomyManager.Instance.AddEconomy(2);
    }

    public void SpawnYellowUnit()
    {
        print("Spawning yellow unit");
        GameObject newUnit = Instantiate(unit, transform.position, Quaternion.identity);
        newUnit.GetComponent<Movement>().Waypoints = Waypoints;
        newUnit.transform.parent = transform;
        newUnit.transform.localScale = Vector3.one;
        newUnit.GetComponent<Movement>().insides = 5;
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
