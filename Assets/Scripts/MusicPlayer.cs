using UnityEngine;

[RequireComponent(typeof(AudioSource))]
public class MusicPlayer : MonoBehaviour
{
    public AudioClip clip;
    [Range(0f, 1f)] public float volume = 0.6f;

    static MusicPlayer _instance;

    void Awake()
    {
        if (_instance != null && _instance != this)
        {
            Destroy(gameObject);
            return;
        }
        _instance = this;
        DontDestroyOnLoad(gameObject);

        var src = GetComponent<AudioSource>();
        src.clip = clip;
        src.loop = true;
        src.volume = volume;
        src.playOnAwake = false;
        src.spatialBlend = 0f;
        if (clip != null) src.Play();
    }
}
