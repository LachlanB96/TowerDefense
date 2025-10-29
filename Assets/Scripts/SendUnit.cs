using Unity.VisualScripting;
using UnityEngine;
using UnityEngine.EventSystems;

public class SendUnit : MonoBehaviour
{

    public GameObject unit;
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {

    }

    // Update is called once per frame
    void Update()
    {

    }

    public void OnMouseDown()
    {
        print("I was clicked");
        GameObject newUnit = Instantiate(unit, new Vector3(0, 0, 0), Quaternion.identity);
        newUnit.AddComponent<Movement>();
        
    }
}
