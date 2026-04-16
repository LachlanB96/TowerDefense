using UnityEngine;
using UnityEngine.EventSystems;

public class TestInput : MonoBehaviour, IPointerEnterHandler
{
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        
    }

    public void OnPointerEnter(PointerEventData eventData)
    {
        Debug.Log("Pointer entered using the new Event System!");
        //_highlight.SetActive(true);
    }
}
