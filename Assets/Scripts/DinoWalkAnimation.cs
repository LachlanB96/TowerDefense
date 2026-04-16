using UnityEngine;

public class DinoWalkAnimation : MonoBehaviour
{
    public float walkSpeed = 4f;

    private Transform _upperLegL, _lowerLegL;
    private Transform _upperLegR, _lowerLegR;
    private Transform _tail1, _tail2;
    private Transform _hip, _head;

    private Quaternion _ulLRest, _llLRest;
    private Quaternion _ulRRest, _llRRest;
    private Quaternion _tail1Rest, _tail2Rest;
    private Quaternion _hipRest, _headRest;

    private float _phase;
    private bool _initialized;

    void FindBones()
    {
        var smr = GetComponentInChildren<SkinnedMeshRenderer>();
        if (smr == null || smr.bones == null) return;

        foreach (var bone in smr.bones)
        {
            if (bone == null) continue;
            switch (bone.name)
            {
                case "UpperLeg_L": _upperLegL = bone; break;
                case "LowerLeg_L": _lowerLegL = bone; break;
                case "UpperLeg_R": _upperLegR = bone; break;
                case "LowerLeg_R": _lowerLegR = bone; break;
                case "Tail1": _tail1 = bone; break;
                case "Tail2": _tail2 = bone; break;
                case "Hip": _hip = bone; break;
                case "Head": _head = bone; break;
            }
        }

        if (_upperLegL == null || _upperLegR == null) return;

        // Store rest rotations
        _ulLRest = _upperLegL.localRotation;
        _llLRest = _lowerLegL.localRotation;
        _ulRRest = _upperLegR.localRotation;
        _llRRest = _lowerLegR.localRotation;
        _tail1Rest = _tail1 != null ? _tail1.localRotation : Quaternion.identity;
        _tail2Rest = _tail2 != null ? _tail2.localRotation : Quaternion.identity;
        _hipRest = _hip != null ? _hip.localRotation : Quaternion.identity;
        _headRest = _head != null ? _head.localRotation : Quaternion.identity;

        _initialized = true;

        // Disable Animator so it doesn't fight us
        var animator = GetComponentInChildren<Animator>();
        if (animator != null)
            animator.enabled = false;
    }

    void LateUpdate()
    {
        if (!_initialized)
        {
            FindBones();
            if (!_initialized) return;
        }

        _phase += Time.deltaTime * walkSpeed;

        float sin = Mathf.Sin(_phase);
        float cos = Mathf.Cos(_phase);

        // Leg stride: 30 degrees swing
        float stride = 30f;
        float kneeBend = 20f;

        // Left leg: forward when sin > 0
        float ulL = sin * stride;
        float llL = -Mathf.Abs(sin) * kneeBend; // knee always bends back

        // Right leg: opposite phase
        float ulR = -sin * stride;
        float llR = -Mathf.Abs(cos) * kneeBend;

        _upperLegL.localRotation = _ulLRest * Quaternion.Euler(ulL, 0, 0);
        _lowerLegL.localRotation = _llLRest * Quaternion.Euler(llL, 0, 0);
        _upperLegR.localRotation = _ulRRest * Quaternion.Euler(ulR, 0, 0);
        _lowerLegR.localRotation = _llRRest * Quaternion.Euler(llR, 0, 0);

        // Tail: smooth wave sway on Y axis, Tail2 lags behind
        if (_tail1 != null)
            _tail1.localRotation = _tail1Rest * Quaternion.Euler(0, Mathf.Sin(_phase * 0.7f) * 5f, 0);
        if (_tail2 != null)
            _tail2.localRotation = _tail2Rest * Quaternion.Euler(0, Mathf.Sin(_phase * 0.7f - 0.8f) * 8f, 0);

        // Subtle hip bob
        if (_hip != null)
            _hip.localRotation = _hipRest * Quaternion.Euler(sin * 1.5f, 0, 0);

        // Slight head bob
        if (_head != null)
            _head.localRotation = _headRest * Quaternion.Euler(sin * 2f, 0, 0);
    }
}
