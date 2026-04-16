using System.Collections;
using UnityEditor.Experimental.GraphView;
using UnityEngine;
using UnityEngine.EventSystems;

public class Tile : MonoBehaviour, IPointerEnterHandler, IPointerExitHandler, IPointerClickHandler
{

    [SerializeField] private Material _baseMaterial, _offsetMaterial;
    //[SerializeField] private MeshRenderer _renderer;
    [SerializeField] private Material _highlightMaterial;

    private bool isOffset;
    private bool isTileSelected;

    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {

    }

    // Update is called once per frame
    void Update()
    {

    }

    public void Init(bool isOffset)
    {
        this.isOffset = isOffset;
        transform.GetComponent<Renderer>().material = this.isOffset ? _offsetMaterial : _baseMaterial;
        //_renderer.material = isOffset ? _offsetMaterial : _baseMaterial;
    }

    void OnMouseEnter()
    {
        Debug.Log("Mouse Entered");
        transform.GetComponent<Renderer>().material = _highlightMaterial;
    }

    public void OnPointerEnter(PointerEventData eventData)
    {
        Debug.Log("Pointer entered using the new Event System!");
        transform.GetComponent<Renderer>().material = _highlightMaterial;
    }

    public void OnPointerExit(PointerEventData eventData)
    {
        if (isTileSelected)
        {
            transform.GetComponent<Renderer>().material = isOffset ? _offsetMaterial : _baseMaterial;
            StartCoroutine(RotateOverTime(0.5f, -1f));
            StartCoroutine(ScaleOverTime(0.5f, -1f));
            isTileSelected = false;
        }
        else
        {
            transform.GetComponent<Renderer>().material = isOffset ? _offsetMaterial : _baseMaterial;
        }
    }

    public void OnPointerClick(PointerEventData eventData)
    {
        if (isTileSelected) return;
        isTileSelected = true;
        transform.position += new Vector3(0, 0.1f, 0);
        StartCoroutine(RotateOverTime(0.5f));
        StartCoroutine(ScaleOverTime(0.5f));
    }

    private IEnumerator RotateOverTime(float duration, float direction = 1f)
    {
        float elapsed = 0f;
        while (elapsed < duration)
        {
            transform.Rotate(new Vector3(0, 1, 0) * Time.deltaTime * 180 * direction);
            elapsed += Time.deltaTime;
            yield return null;
        }
    }

    private IEnumerator ScaleOverTime(float duration, float direction = 1f)
    {
        float elapsed = 0f;
        while (elapsed < duration)
        {
            transform.localScale += new Vector3(0.1f, 0.1f, 0.1f) * Time.deltaTime * direction;
            elapsed += Time.deltaTime;
            yield return null;
        }
    }
}
