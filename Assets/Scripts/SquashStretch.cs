using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class SquashStretch : MonoBehaviour
{
    public Vector3 squashScale = new Vector3(1.15f, 0.8f, 1.15f);
    public float squashDuration = 0.08f;
    public Vector3 stretchScale = new Vector3(0.95f, 1.05f, 0.95f);
    public float stretchDuration = 0.1f;
    public float settleDuration = 0.08f;

    private readonly List<Transform> _parts = new List<Transform>();
    private readonly List<Vector3> _originalScales = new List<Vector3>();
    private Coroutine _routine;

    public void AddPart(Transform part)
    {
        _parts.Add(part);
        _originalScales.Add(part.localScale);
    }

    public void Play()
    {
        if (_parts.Count == 0) return;
        if (_routine != null) StopCoroutine(_routine);
        _routine = StartCoroutine(RunSquash());
    }

    IEnumerator RunSquash()
    {
        yield return ScaleTo(squashScale, squashDuration);
        yield return ScaleTo(stretchScale, stretchDuration);
        yield return ScaleTo(Vector3.one, settleDuration);
        _routine = null;
    }

    IEnumerator ScaleTo(Vector3 scaleMultiplier, float duration)
    {
        Vector3[] startScales = new Vector3[_parts.Count];
        for (int i = 0; i < _parts.Count; i++)
            startScales[i] = _parts[i] != null ? _parts[i].localScale : _originalScales[i];

        Vector3[] targetScales = new Vector3[_parts.Count];
        for (int i = 0; i < _parts.Count; i++)
            targetScales[i] = Vector3.Scale(_originalScales[i], scaleMultiplier);

        float elapsed = 0f;
        while (elapsed < duration)
        {
            elapsed += Time.deltaTime;
            float t = Mathf.SmoothStep(0f, 1f, elapsed / duration);
            for (int i = 0; i < _parts.Count; i++)
            {
                if (_parts[i] == null) continue;
                _parts[i].localScale = Vector3.LerpUnclamped(startScales[i], targetScales[i], t);
            }
            yield return null;
        }

        for (int i = 0; i < _parts.Count; i++)
        {
            if (_parts[i] != null)
                _parts[i].localScale = targetScales[i];
        }
    }
}
