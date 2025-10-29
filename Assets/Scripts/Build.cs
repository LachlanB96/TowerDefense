using UnityEngine;

public class Build : MonoBehaviour
{

    public GameObject baseTower;
    public GameObject projectile;
    public GameObject units;

    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {

    }

    // Update is called once per frame
    void Update()
    {

    }

    public void BuildBaseTower()
    {
        print("Building Base Tower");
        GameObject newTower = Instantiate(baseTower, new Vector3(0, 0, 0), Quaternion.identity);
        newTower.GetComponent<Attack>().units = units;
    
    }
}
