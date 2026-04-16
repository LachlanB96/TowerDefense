using UnityEngine;

public class TackSpin : MonoBehaviour
{
    public float spinSpeed = 30f;

    private Transform _outerRing;
    private Transform _middleRing;

    void Awake()
    {
        _outerRing = new GameObject("_TackRingOuter").transform;
        _outerRing.SetParent(transform, false);

        _middleRing = new GameObject("_TackRingMiddle").transform;
        _middleRing.SetParent(transform, false);

        for (int i = transform.childCount - 1; i >= 0; i--)
        {
            Transform child = transform.GetChild(i);
            if (child == _outerRing || child == _middleRing) continue;

            string name = child.name;
            if (name.StartsWith("TackTip"))
                child.SetParent(_outerRing, true);
            else if (name.StartsWith("TackShaft"))
                child.SetParent(_middleRing, true);
            // TackHead stays parented to the tower (no rotation)
        }
    }

    void Update()
    {
        float dt = spinSpeed * Time.deltaTime;
        if (_outerRing != null)
            _outerRing.Rotate(0f, dt, 0f);
        if (_middleRing != null)
            _middleRing.Rotate(0f, -dt, 0f);
    }
}
