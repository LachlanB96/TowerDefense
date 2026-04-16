using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

public class TowerPlacer : MonoBehaviour
{
    [SerializeField] private GameObject _towerPrefab;
    [SerializeField] private LayerMask _groundLayer;
    [SerializeField] private float _overlapRadius = 1.4f;

    [Header("Projectile Appearance")]
    [SerializeField] private Color _projectileColor = new Color(0.76f, 0.6f, 0.42f);
    [SerializeField] private float _projectileMetallic = 0f;
    [SerializeField] private float _projectileSmoothness = 0.2f;

    public bool IsPlacing => _isPlacing;

    private GameObject _preview;
    private GameObject _rangeIndicator;
    private bool _isPlacing;
    private bool _canPlace;
    private int _skipFrames;
    private Material[][] _originalMaterials;
    private Renderer[] _previewRenderers;

    void Start()
    {
        var btn = GameObject.Find("PlaceTowerButton");
        if (btn != null)
            btn.GetComponent<Button>().onClick.AddListener(BeginPlacement);
    }

    public void BeginPlacement()
    {
        if (_isPlacing) return;
        SpawnPreview();
    }

    void SpawnPreview()
    {
        _isPlacing = true;
        _skipFrames = 2;
        _canPlace = false;

        _preview = Instantiate(_towerPrefab);
        _preview.name = "tack_preview";

        foreach (var col in _preview.GetComponentsInChildren<Collider>())
            col.enabled = false;

        // Save original materials before modifying
        _previewRenderers = _preview.GetComponentsInChildren<Renderer>();
        _originalMaterials = new Material[_previewRenderers.Length][];
        for (int i = 0; i < _previewRenderers.Length; i++)
            _originalMaterials[i] = _previewRenderers[i].sharedMaterials;

        SetPreviewColor(new Color(1f, 1f, 1f, 0.4f));

        _rangeIndicator = RangeIndicator.Create(3f, _preview.transform);
    }

    void Update()
    {
        if (!_isPlacing || _preview == null) return;

        var mouse = Mouse.current;
        if (mouse == null) return;

        if (_skipFrames > 0)
        {
            _skipFrames--;
            return;
        }

        Ray ray = Camera.main.ScreenPointToRay(mouse.position.ReadValue());
        if (Physics.Raycast(ray, out RaycastHit hit, 500f, _groundLayer))
        {
            _preview.transform.position = hit.point;
            _canPlace = !CheckOverlap(hit.point);
            SetPreviewColor(_canPlace ? new Color(1f, 1f, 1f, 0.4f) : new Color(1f, 0.15f, 0.15f, 0.5f));
        }
        else
        {
            _canPlace = false;
        }

        if (mouse.leftButton.wasPressedThisFrame && _canPlace)
        {
            PlaceTower();

            if (Keyboard.current.leftShiftKey.isPressed || Keyboard.current.rightShiftKey.isPressed)
                SpawnPreview();
        }

        if (mouse.rightButton.wasPressedThisFrame)
        {
            CancelPlacement();
        }
    }

    bool CheckOverlap(Vector3 position)
    {
        Collider[] hits = Physics.OverlapSphere(position, _overlapRadius);
        foreach (var col in hits)
        {
            if (col.transform.IsChildOf(_preview.transform)) continue;
            if (col.gameObject.layer == 8) continue; // Ground layer
            if (col.GetComponent<Tile>() != null) continue;
            if (col.GetComponentInParent<GridManager>() != null) continue;
            return true;
        }

        if (IsOnPath(position)) return true;

        return false;
    }

    bool IsOnPath(Vector3 position)
    {
        var pathRenderer = FindAnyObjectByType<PathRenderer>();
        if (pathRenderer == null) return false;

        var wpField = typeof(PathRenderer).GetField("_waypoints", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        var widthField = typeof(PathRenderer).GetField("_pathWidth", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        if (wpField == null || widthField == null) return false;

        var waypoints = wpField.GetValue(pathRenderer) as Transform;
        float pathWidth = (float)widthField.GetValue(pathRenderer);
        if (waypoints == null || waypoints.childCount < 2) return false;

        float halfWidth = pathWidth / 2f + _overlapRadius;
        Vector2 pos2D = new Vector2(position.x, position.z);

        for (int i = 0; i < waypoints.childCount - 1; i++)
        {
            Vector3 a = waypoints.GetChild(i).position;
            Vector3 b = waypoints.GetChild(i + 1).position;
            Vector2 a2 = new Vector2(a.x, a.z);
            Vector2 b2 = new Vector2(b.x, b.z);

            float dist = DistanceToSegment(pos2D, a2, b2);
            if (dist < halfWidth) return true;
        }
        return false;
    }

    float DistanceToSegment(Vector2 p, Vector2 a, Vector2 b)
    {
        Vector2 ab = b - a;
        float t = Mathf.Clamp01(Vector2.Dot(p - a, ab) / ab.sqrMagnitude);
        Vector2 closest = a + ab * t;
        return Vector2.Distance(p, closest);
    }

    void PlaceTower()
    {
        // Remove range indicator before placing
        if (_rangeIndicator != null)
        {
            Destroy(_rangeIndicator);
            _rangeIndicator = null;
        }

        _preview.name = "tack000";

        foreach (var col in _preview.GetComponentsInChildren<Collider>(true))
            col.enabled = true;

        // Ensure tower has a collider for click detection
        if (_preview.GetComponentInChildren<Collider>() == null)
        {
            Bounds bounds = new Bounds(_preview.transform.position, Vector3.zero);
            foreach (var r in _preview.GetComponentsInChildren<Renderer>())
                bounds.Encapsulate(r.bounds);
            BoxCollider box = _preview.AddComponent<BoxCollider>();
            box.center = _preview.transform.InverseTransformPoint(bounds.center);
            box.size = bounds.size;
        }

        // Restore original materials (with Blender colors)
        for (int i = 0; i < _previewRenderers.Length; i++)
            _previewRenderers[i].sharedMaterials = _originalMaterials[i];

        // Tower data for selection system
        TowerData data = _preview.GetComponent<TowerData>();
        if (data == null)
            data = _preview.AddComponent<TowerData>();
        data.towerType = "tack000";

        // Attack behavior
        TackAttack attack = _preview.GetComponent<TackAttack>();
        if (attack == null)
            attack = _preview.AddComponent<TackAttack>();
        attack.diskColor = _projectileColor;
        attack.diskMetallic = _projectileMetallic;
        attack.diskSmoothness = _projectileSmoothness;

        _preview = null;
        _previewRenderers = null;
        _originalMaterials = null;
        _isPlacing = false;
    }

    void CancelPlacement()
    {
        if (_rangeIndicator != null)
        {
            Destroy(_rangeIndicator);
            _rangeIndicator = null;
        }
        if (_preview != null)
            Destroy(_preview);
        _preview = null;
        _isPlacing = false;
    }

    void SetPreviewColor(Color tint)
    {
        foreach (var r in _preview.GetComponentsInChildren<Renderer>())
        {
            foreach (var mat in r.materials)
            {
                MakeTransparent(mat);
                if (mat.HasProperty("_BaseColor"))
                    mat.SetColor("_BaseColor", tint);
                if (mat.HasProperty("_Color"))
                    mat.SetColor("_Color", tint);
            }
        }
    }

    void MakeTransparent(Material mat)
    {
        mat.SetFloat("_Surface", 1);
        mat.SetOverrideTag("RenderType", "Transparent");
        mat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
        mat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
        mat.SetInt("_ZWrite", 0);
        mat.renderQueue = 3000;
        mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
    }

}
