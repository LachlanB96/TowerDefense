using UnityEngine;

public class SniperIdle : MonoBehaviour
{
    public float scanSpeed = 25f;
    public float scanAngle = 45f;

    private Transform _turretPivot;
    private float _baseAngle;
    private float _time;

    void Awake()
    {
        // Group all barrel/scope parts under a pivot so they rotate together
        _turretPivot = new GameObject("_SniperPivot").transform;
        _turretPivot.SetParent(transform, false);
        _turretPivot.localPosition = new Vector3(0f, 0.93f, 0f);

        for (int i = transform.childCount - 1; i >= 0; i--)
        {
            Transform child = transform.GetChild(i);
            if (child == _turretPivot) continue;

            string n = child.name;
            if (n.StartsWith("SniperBarrel") || n.StartsWith("SniperMuzzle") ||
                n.StartsWith("SniperScope") || n.StartsWith("ScopeLens") ||
                n.StartsWith("ScopeMount") || n.StartsWith("SniperStock") ||
                n.StartsWith("SniperTurret"))
            {
                child.SetParent(_turretPivot, true);
            }
        }

        _baseAngle = _turretPivot.localEulerAngles.y;
    }

    void Update()
    {
        if (_turretPivot == null) return;
        _time += Time.deltaTime * scanSpeed * Mathf.Deg2Rad;
        float angle = _baseAngle + Mathf.Sin(_time) * scanAngle;
        _turretPivot.localEulerAngles = new Vector3(0f, angle, 0f);
    }

    /// <summary>
    /// Snap the turret to face a world position (used by SniperAttack to aim).
    /// Returns the pivot so attack can animate recoil.
    /// </summary>
    public Transform AimAt(Vector3 worldTarget)
    {
        if (_turretPivot == null) return null;

        Vector3 local = transform.InverseTransformPoint(worldTarget);
        float targetAngle = Mathf.Atan2(local.x, local.z) * Mathf.Rad2Deg;
        _turretPivot.localEulerAngles = new Vector3(0f, targetAngle, 0f);

        // Reset scan timer so it resumes from the aimed direction
        _baseAngle = targetAngle;
        _time = 0f;

        return _turretPivot;
    }
}
