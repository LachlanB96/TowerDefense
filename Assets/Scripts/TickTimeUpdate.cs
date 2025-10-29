using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class TickTimeUpdate : MonoBehaviour
{

    public TMP_Text label;
    private int tickCount = 0;
    private int money = 0;
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        tickCount++;
        money += 10;
        label.text = "Ticks: " + tickCount + " | Money: " + money;
    }
}
