using UnityEngine;
using UnityEngine.UI;

public class Movement : MonoBehaviour
{
    public GameObject Waypoints;
    private Transform currentWaypoint;
    private int waypointIndex = 0;
    public float speed = 300.7f;
    public float rotationSpeed = 8f;

    public int health = 1;
    private int maxHealth;
    private int deaths = 0;
    public int insides = 1;

    private static Canvas _sharedCanvas;
    private GameObject _healthBarObj;
    private Image _healthFill;
    private RectTransform _healthBarRect;
    private float _feetOffset;
    private bool _feetOffsetReady;
    private Vector3 _healthBarWorldOffset = new Vector3(0, 3f, 0);

    void Start()
    {
        maxHealth = health;
        currentWaypoint = Waypoints.transform.GetChild(waypointIndex);
        CreateHealthBar();
    }

    void Update()
    {
        if (currentWaypoint == null) return;

        // Compute feet offset on first frame when renderer bounds are valid
        if (!_feetOffsetReady)
        {
            Renderer r = GetComponentInChildren<Renderer>();
            if (r != null)
                _feetOffset = transform.position.y - r.bounds.min.y;
            _feetOffsetReady = true;
            SnapToPath();
        }

        // Move in XZ toward waypoint, then set Y to stand on path
        Vector3 target = currentWaypoint.position;
        target.y = transform.position.y; // keep current Y so speed isn't wasted on vertical
        transform.position = Vector3.MoveTowards(transform.position, target, speed * Time.deltaTime);

        // Smoothly rotate toward the waypoint
        Vector3 lookTarget = currentWaypoint.position;
        lookTarget.y = transform.position.y;
        Vector3 direction = lookTarget - transform.position;
        if (direction.sqrMagnitude > 0.001f)
        {
            Quaternion targetRotation = Quaternion.LookRotation(direction);
            transform.rotation = Quaternion.Slerp(transform.rotation, targetRotation, rotationSpeed * Time.deltaTime);
        }

        SnapToPath();

        // Use XZ distance to check waypoint arrival
        float dx = transform.position.x - currentWaypoint.position.x;
        float dz = transform.position.z - currentWaypoint.position.z;
        if (dx * dx + dz * dz < 0.01f)
        {
            waypointIndex++;
            if (waypointIndex >= Waypoints.transform.childCount)
            {
                if (EconomyManager.Instance != null)
                    EconomyManager.Instance.LoseLives(health);
                Destroy(gameObject);
                return;
            }
            currentWaypoint = Waypoints.transform.GetChild(waypointIndex);
        }
    }

    void OnDestroy()
    {
        if (_healthBarObj != null)
            Destroy(_healthBarObj);
    }

    void SnapToPath()
    {
        // Place feet on path surface (waypoint Y + small offset for path thickness)
        float pathSurface = currentWaypoint.position.y + 0.05f;
        Vector3 pos = transform.position;
        pos.y = pathSurface + _feetOffset;
        transform.position = pos;
    }

    static Canvas GetOrCreateSharedCanvas()
    {
        if (_sharedCanvas != null) return _sharedCanvas;

        var canvasObj = new GameObject("HealthBarCanvas");
        DontDestroyOnLoad(canvasObj);
        _sharedCanvas = canvasObj.AddComponent<Canvas>();
        _sharedCanvas.renderMode = RenderMode.ScreenSpaceOverlay;
        _sharedCanvas.sortingOrder = 100;

        var scaler = canvasObj.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920, 1080);

        canvasObj.AddComponent<GraphicRaycaster>();
        return _sharedCanvas;
    }

    void CreateHealthBar()
    {
        Canvas canvas = GetOrCreateSharedCanvas();

        _healthBarObj = new GameObject("HealthBar_" + gameObject.GetInstanceID());
        _healthBarObj.transform.SetParent(canvas.transform, false);
        _healthBarRect = _healthBarObj.AddComponent<RectTransform>();
        _healthBarRect.sizeDelta = new Vector2(60f, 8f);

        // Background (dark)
        GameObject bg = new GameObject("BG");
        bg.transform.SetParent(_healthBarObj.transform, false);
        Image bgImg = bg.AddComponent<Image>();
        bgImg.color = new Color(0.2f, 0.2f, 0.2f, 0.8f);
        RectTransform bgrt = bg.GetComponent<RectTransform>();
        bgrt.anchorMin = Vector2.zero;
        bgrt.anchorMax = Vector2.one;
        bgrt.offsetMin = Vector2.zero;
        bgrt.offsetMax = Vector2.zero;

        // Fill (green)
        GameObject fill = new GameObject("Fill");
        fill.transform.SetParent(_healthBarObj.transform, false);
        _healthFill = fill.AddComponent<Image>();
        _healthFill.color = Color.green;
        RectTransform frt = fill.GetComponent<RectTransform>();
        frt.anchorMin = Vector2.zero;
        frt.anchorMax = Vector2.one;
        frt.pivot = new Vector2(0, 0.5f);
        frt.offsetMin = Vector2.zero;
        frt.offsetMax = Vector2.zero;
    }

    void LateUpdate()
    {
        if (_healthBarRect == null || Camera.main == null) return;

        Vector3 worldPos = transform.position + _healthBarWorldOffset;
        Vector3 screenPos = Camera.main.WorldToScreenPoint(worldPos);

        if (screenPos.z > 0)
        {
            _healthBarRect.position = screenPos;
            _healthBarObj.SetActive(true);
        }
        else
        {
            _healthBarObj.SetActive(false);
        }
    }

    void UpdateHealthBar()
    {
        if (_healthFill == null) return;
        float ratio = Mathf.Clamp01((float)health / maxHealth);
        RectTransform frt = _healthFill.GetComponent<RectTransform>();
        frt.anchorMax = new Vector2(ratio, 1);

        if (ratio > 0.5f)
            _healthFill.color = Color.green;
        else if (ratio > 0.25f)
            _healthFill.color = Color.yellow;
        else
            _healthFill.color = Color.red;
    }

    public void Death()
    {
        if (deaths == 0)
        {
            deaths++;
            for (int i = 0; i < insides; i++)
            {
                GameObject newUnit = Instantiate(gameObject, transform.position, Quaternion.identity);
                newUnit.transform.position += new Vector3(Random.Range(-1f, 1f), 0f, Random.Range(-1f, 1f));
                newUnit.transform.parent = SceneContainers.Units;
                newUnit.transform.localScale = Vector3.one;

                Movement m = newUnit.GetComponent<Movement>();
                m.waypointIndex = waypointIndex;
                m.health = 1;
                m.insides = 0;
            }
        }

        // Disable movement and health bar, play death animation
        enabled = false;
        if (_healthBarObj != null)
            Destroy(_healthBarObj);

        // Move out of UnitsParent so the dying unit doesn't count as a target
        transform.SetParent(SceneContainers.Effects);

        gameObject.AddComponent<DeathAnimation>();
    }

    internal HitReport Hit(int v)
    {
        var judged = GetComponent<JudgedEffect>();
        if (judged != null)
            v = Mathf.Max(1, Mathf.RoundToInt(v * judged.damageMultiplier));

        int dealt = Mathf.Max(0, Mathf.Min(v, health));
        bool wasAlive = deaths == 0 && health > 0;

        FloatingText.Spawn(transform.position + _healthBarWorldOffset, v.ToString(), Color.red, 0.9f, 24, true, 60f);
        health -= v;
        UpdateHealthBar();

        bool killed = false;
        if (health <= 0)
        {
            killed = wasAlive;
            Death();
        }
        return new HitReport(dealt, killed);
    }
}

public readonly struct HitReport
{
    public readonly int damageDealt;
    public readonly bool killed;
    public HitReport(int damageDealt, bool killed)
    {
        this.damageDealt = damageDealt;
        this.killed = killed;
    }
}
