using UnityEngine;

public class JudgedEffect : MonoBehaviour
{
    public float duration = 10f;
    public float damageMultiplier = 1.25f;

    private float _endTime;
    private GameObject _visual;

    void Start()
    {
        _endTime = Time.time + duration;
        CreateVisual();
    }

    public void Refresh()
    {
        _endTime = Time.time + duration;
    }

    void Update()
    {
        if (Time.time >= _endTime)
        {
            if (_visual != null) Destroy(_visual);
            Destroy(this);
        }
    }

    void CreateVisual()
    {
        _visual = new GameObject("_JudgedFX");
        _visual.transform.SetParent(transform, false);
        _visual.transform.localPosition = Vector3.up * 2.2f;

        var mat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        mat.SetColor("_BaseColor", new Color(0.9f, 0.05f, 0.15f));

        var vert = GameObject.CreatePrimitive(PrimitiveType.Cube);
        vert.name = "_cross_v";
        Destroy(vert.GetComponent<Collider>());
        vert.transform.SetParent(_visual.transform, false);
        vert.transform.localScale = new Vector3(0.12f, 0.55f, 0.12f);
        vert.GetComponent<Renderer>().sharedMaterial = mat;

        var horiz = GameObject.CreatePrimitive(PrimitiveType.Cube);
        horiz.name = "_cross_h";
        Destroy(horiz.GetComponent<Collider>());
        horiz.transform.SetParent(_visual.transform, false);
        horiz.transform.localPosition = Vector3.up * 0.08f;
        horiz.transform.localScale = new Vector3(0.36f, 0.12f, 0.12f);
        horiz.GetComponent<Renderer>().sharedMaterial = mat;
    }

    void LateUpdate()
    {
        if (_visual == null || Camera.main == null) return;
        _visual.transform.rotation = Quaternion.LookRotation(
            _visual.transform.position - Camera.main.transform.position);
    }
}
