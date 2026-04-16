using UnityEngine;

public class TreeAnimController : MonoBehaviour
{
    public float gustMinInterval = 8f;
    public float gustMaxInterval = 20f;
    public float birdMinInterval = 30f;
    public float birdMaxInterval = 60f;

    private Animator _animator;
    private float _nextGustTime;
    private float _nextBirdTime;

    void Start()
    {
        _animator = GetComponent<Animator>();
        _nextGustTime = Time.time + Random.Range(gustMinInterval, gustMaxInterval);
        _nextBirdTime = Time.time + Random.Range(birdMinInterval, birdMaxInterval);
    }

    void Update()
    {
        if (Time.time >= _nextGustTime)
        {
            _animator.SetTrigger("WindGust");
            _nextGustTime = Time.time + Random.Range(gustMinInterval, gustMaxInterval);
        }

        if (Time.time >= _nextBirdTime)
        {
            _animator.SetTrigger("BirdEmerge");
            _nextBirdTime = Time.time + Random.Range(birdMinInterval, birdMaxInterval);
        }
    }
}
