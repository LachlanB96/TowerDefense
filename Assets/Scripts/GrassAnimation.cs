using UnityEngine;

public class GrassAnimation : MonoBehaviour
{
    private Animator _animator;
    private float _nextTriggerTime;

    void Start()
    {
        _animator = GetComponentInChildren<Animator>();
        // Stagger initial timing so they don't all play at once
        _nextTriggerTime = Time.time + Random.Range(0f, 5f);
    }

    void Update()
    {
        if (_animator == null || Time.time < _nextTriggerTime) return;

        // Randomly pick wind or bugs
        bool playBugs = Random.value < 0.3f;
        _animator.SetBool("PlayBugs", playBugs);

        // Schedule next trigger in 5-10 seconds
        _nextTriggerTime = Time.time + Random.Range(5f, 10f);
    }
}
