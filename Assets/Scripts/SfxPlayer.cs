using UnityEngine;

public static class SfxPlayer
{
    public static void PlayOneShot(string resourcePath, Vector3 worldPos, float volume = 1f)
    {
        var clip = Resources.Load<AudioClip>(resourcePath);
        if (clip == null)
        {
            Debug.LogWarning($"SfxPlayer: clip '{resourcePath}' not found in Resources");
            return;
        }

        var go = new GameObject("_Sfx_" + clip.name);
        go.transform.position = worldPos;
        var src = go.AddComponent<AudioSource>();
        src.clip = clip;
        src.volume = volume;
        src.spatialBlend = 0f;
        src.playOnAwake = false;
        src.Play();

        Object.Destroy(go, clip.length + 0.1f);
    }
}
