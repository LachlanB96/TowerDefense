using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

public class CameraController : MonoBehaviour
{
    [Header("Pan")]
    public float panSpeed = 15f;
    public float minX = -8f;
    public float maxX = 28f;
    public float minZ = -16f;
    public float maxZ = 24f;

    [Header("Zoom")]
    public float zoomSpeed = 300f;
    public float dragZoomSpeed = 40f;
    public float minY = 5f;
    public float maxY = 30f;

    [Header("Rotation")]
    public float rotateSpeed = 0.3f;
    public float minPitch = 15f;
    public float maxPitch = 80f;

    private Vector3 _defaultPosition;
    private Quaternion _defaultRotation;
    private bool _isDragZooming;
    private bool _isRotating;
    private Vector2 _lastMousePos;

    private int _speedIndex = 0;
    private readonly float[] _speeds = { 1f, 2f, 4f, 0.5f };
    private Text _speedText;

    void Start()
    {
        _defaultPosition = transform.position;
        _defaultRotation = transform.rotation;
        CreateButtons();
    }

    void Update()
    {
        var kb = Keyboard.current;
        var mouse = Mouse.current;
        if (kb == null || mouse == null) return;

        HandlePan(kb);
        HandleZoom(kb, mouse);
        HandleRotation(kb, mouse);
    }

    void HandlePan(Keyboard kb)
    {
        Vector3 move = Vector3.zero;

        if (kb.wKey.isPressed) move += transform.forward;
        if (kb.sKey.isPressed) move -= transform.forward;
        if (kb.dKey.isPressed) move += transform.right;
        if (kb.aKey.isPressed) move -= transform.right;

        move.y = 0f;
        if (move.sqrMagnitude > 0.001f)
            move.Normalize();

        Vector3 pos = transform.position + move * panSpeed * Time.deltaTime;
        pos.x = Mathf.Clamp(pos.x, minX, maxX);
        pos.z = Mathf.Clamp(pos.z, minZ, maxZ);
        transform.position = pos;
    }

    void HandleZoom(Keyboard kb, Mouse mouse)
    {
        float zoomDelta = 0f;

        // Scroll wheel zoom
        float scroll = mouse.scroll.ReadValue().y;
        if (Mathf.Abs(scroll) > 0.01f)
            zoomDelta = -Mathf.Sign(scroll) * zoomSpeed * 0.01f;

        // Shift + left click drag zoom
        if (kb.leftShiftKey.isPressed && mouse.leftButton.isPressed)
        {
            if (!_isDragZooming)
            {
                _isDragZooming = true;
                _lastMousePos = mouse.position.ReadValue();
            }
            else
            {
                Vector2 currentPos = mouse.position.ReadValue();
                float dragDelta = currentPos.y - _lastMousePos.y;
                zoomDelta = -dragDelta * dragZoomSpeed * Time.deltaTime;
                _lastMousePos = currentPos;
            }
        }
        else
        {
            _isDragZooming = false;
        }

        if (Mathf.Abs(zoomDelta) > 0.001f)
        {
            Vector3 pos = transform.position + transform.forward * -zoomDelta;
            pos.y = Mathf.Clamp(pos.y, minY, maxY);
            transform.position = pos;
        }
    }

    void HandleRotation(Keyboard kb, Mouse mouse)
    {
        bool rightHeld = mouse.rightButton.isPressed;
        bool ctrlLeftHeld = (kb.leftCtrlKey.isPressed || kb.rightCtrlKey.isPressed) && mouse.leftButton.isPressed;

        if (rightHeld || ctrlLeftHeld)
        {
            if (!_isRotating)
            {
                _isRotating = true;
                _lastMousePos = mouse.position.ReadValue();
            }
            else
            {
                Vector2 currentPos = mouse.position.ReadValue();
                Vector2 delta = currentPos - _lastMousePos;
                _lastMousePos = currentPos;

                // Rotate in-place — camera stays at same position
                Vector3 euler = transform.eulerAngles;
                float yaw = euler.y + delta.x * rotateSpeed;
                float pitch = euler.x + -delta.y * rotateSpeed;
                if (pitch > 180f) pitch -= 360f;
                pitch = Mathf.Clamp(pitch, minPitch, maxPitch);
                transform.eulerAngles = new Vector3(pitch, yaw, 0f);
            }
        }
        else
        {
            _isRotating = false;
        }
    }

    public void ResetCamera()
    {
        transform.position = _defaultPosition;
        transform.rotation = _defaultRotation;
    }

    void CreateButtons()
    {
        var canvasObj = UIBuilder.Canvas("BottomLeftUI", 5);

        MakeBottomLeftButton("Reset Camera", new Vector2(10, 10), ResetCamera, canvasObj.transform);

        var speedBtn = MakeBottomLeftButton("Speed 1x", new Vector2(150, 10), ToggleSpeed, canvasObj.transform);
        _speedText = speedBtn.GetComponentInChildren<Text>();
    }

    GameObject MakeBottomLeftButton(string label, Vector2 pos, UnityEngine.Events.UnityAction action, Transform parent)
    {
        var btnObj = new GameObject(label);
        btnObj.transform.SetParent(parent, false);

        var rt = btnObj.AddComponent<RectTransform>();
        rt.anchorMin = Vector2.zero;
        rt.anchorMax = Vector2.zero;
        rt.pivot = Vector2.zero;
        rt.anchoredPosition = pos;
        rt.sizeDelta = new Vector2(130, 35);

        btnObj.AddComponent<Image>().color = new Color(0.25f, 0.25f, 0.25f, 0.85f);

        var btn = btnObj.AddComponent<Button>();
        btn.onClick.AddListener(action);
        UIBuilder.ApplyStandardColors(btn);

        var txt = UIBuilder.Text("Text", btnObj.transform, label, 14, Color.white);
        UIBuilder.Stretch(txt.gameObject);

        return btnObj;
    }

    void ToggleSpeed()
    {
        _speedIndex = (_speedIndex + 1) % _speeds.Length;
        Time.timeScale = _speeds[_speedIndex];
        _speedText.text = $"Speed {_speeds[_speedIndex]}x";
    }
}
