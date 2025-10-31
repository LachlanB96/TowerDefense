using System;
using UnityEngine;
using UnityEngine.InputSystem;

public class Attack : MonoBehaviour
{

    public Material rest;
    public Material attack;
    public Material build;
    public GameObject units;
    public GameObject projectile;

    public int range = 10;
    public int pierce = 1;
    public int damage = 1;
    public float speed = 5f;
    internal string attackType = "normal";
    private float lastShow = 0;

    private bool isBuildMode = true;

    private bool didNotAttack = true;

    void Start()
    {

    }

    void Update()
    {
        if (isBuildMode)
        {
            UpdateBuildMode();
            return;
        }

        UpdateAttackMode();
    }

    void UpdateAttackMode()
    {
        if (Time.time - lastShow < speed) return;
        if (units == null)
        {
            GetComponent<Renderer>().material = rest;
            return;
        }

        didNotAttack = true;
        foreach (Transform unit in units.transform)
        {
            GetComponent<Renderer>().material = attack;
            if (Vector3.Distance(transform.position, unit.position) < 10.0f)
            {
                SendAttackProjectiles(unit);
                return;
            }
        }
        if (didNotAttack)
        {
            GetComponent<Renderer>().material = rest;
        }
    }

    void SendAttackProjectiles(Transform unit)
    {
        if (attackType == "blade")
        {
            GetComponent<Renderer>().material = attack;
            GameObject newProjectile = Instantiate(projectile, transform.position, Quaternion.identity, unit);
            newProjectile.GetComponent<Velocity>().target = unit.gameObject;
            newProjectile.GetComponent<Velocity>().speed = 0.1f;
            newProjectile.GetComponent<Velocity>().homing = false;
            lastShow = Time.time;
            didNotAttack = false;
        }
        else
        {
            GetComponent<Renderer>().material = attack;
            GameObject newProjectile = Instantiate(projectile, transform.position, Quaternion.identity, unit);
            newProjectile.GetComponent<Velocity>().target = unit.gameObject;
            newProjectile.GetComponent<Velocity>().speed = 0.1f;
            newProjectile.GetComponent<Velocity>().homing = true;
            lastShow = Time.time;
            didNotAttack = false;
            return;
        }
    }

    void UpdateBuildMode()
    {
        transform.position = new Vector3(Mathf.Round(Mouse.current.position.x.ReadValue() / 160), Mathf.Round(Mouse.current.position.y.ReadValue() / 160), 0);
        GetComponent<Renderer>().material = build;
        if (Mouse.current.leftButton.wasPressedThisFrame)
        {
            isBuildMode = false;
        }
    }
}
