using UnityEngine;
using UnityEngine.UIElements;

public class UIInit : MonoBehaviour
{
    public int tickCount = 0;
    public int money = 0;


    public VisualElement ui;
    public Button baseTower;
    public Button bladeTower;
    public Button baseCreep;
    public GameObject towerSpawner;

    public enum TowerType
    {
        BaseTower,
        BladeTower,
        SplashTower
    }

    public enum CreepType
    {
        BaseCreep,
        FastCreep,
        DupCreep
    }

    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {

        towerSpawner = GameObject.Find("Spawner");
        ui = GetComponent<UIDocument>().rootVisualElement;
        
        baseTower = ui.Q<Button>("baseTower");
        baseCreep = ui.Q<Button>("baseCreep");

        //baseTower.clicked += tower()
        baseCreep.clicked += CreepSpawn(CreepType.BaseCreep);
        baseTower.clicked += TowerSpawn(TowerType.BaseTower);
    }

    void OnEnable()
    {

    }

    // Update is called once per frame
    void Update()
    {
        tickCount++;
        ui.Q<Label>("money").text = "Money: " + money;
        if(tickCount % 10 == 0)
        {
            ui.Q<ProgressBar>("moneyBar").value += 0.5f;
            if(ui.Q<ProgressBar>("moneyBar").value >= 100f)
            {
                ui.Q<ProgressBar>("moneyBar").value = 0.0f;
                money += 100;
            }
        }
    }

    private System.Action CreepSpawn(CreepType type)
    {
        return () => towerSpawner.GetComponent<Spawn>().SpawnUnit(type);
    }
    
    private System.Action TowerSpawn(TowerType type)
    {
        return () => towerSpawner.GetComponent<Build>().BuildBaseTower();
    }
}
