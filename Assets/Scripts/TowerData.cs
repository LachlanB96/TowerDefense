using UnityEngine;

public class TowerData : MonoBehaviour, IDamageCredit
{
    public string towerType = "tack000";
    public int upgradePath1Level = 0;
    public int upgradePath2Level = 0;
    public int upgradePath3Level = 0;
    public int totalInvested = 0;

    public int killCount = 0;
    public int totalDamage = 0;

    public int SellValue => Mathf.RoundToInt(totalInvested * 0.75f);

    public void Credit(int damageDealt, bool killed)
    {
        totalDamage += damageDealt;
        if (killed) killCount++;
    }
}
