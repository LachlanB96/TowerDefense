using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class NatureAttack : MonoBehaviour, ITowerAttack
{
    public float range = 3f;
    public float cooldown = 1f;
    public int damage = 1;
    public float treeLifetime = 10f;
    public float orbitSpeed = 25f;
    public float launchSpeed = 8f;
    public float attackSpeedMultiplier = 1f;

    public float Range => range;

    private float _lastAttackTime = -999f;
    private Transform _waypoints;
    private float _pathWidth;
    private Transform _orbitRing;
    private Material _purpleMat;
    private SquashStretch _squash;

    // Tree slots
    private List<TreeSlot> _slots = new List<TreeSlot>();
    private const int MAX_TREES = 8;

    class TreeSlot
    {
        public List<Transform> orbitParts = new List<Transform>();
        public bool deployed;
    }

    void Start()
    {
        var pathRenderer = FindAnyObjectByType<PathRenderer>();
        if (pathRenderer != null)
        {
            _waypoints = pathRenderer.Waypoints;
            _pathWidth = pathRenderer.PathWidth;
        }

        // Purple telekinesis material
        _purpleMat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
        _purpleMat.SetColor("_BaseColor", new Color(0.6f, 0.1f, 0.9f, 0.5f));
        MaterialUtils.MakeTransparent(_purpleMat);

        GroupTreeParts();
        SetupSquash();
    }

    void GroupTreeParts()
    {
        // Create orbit ring
        _orbitRing = new GameObject("_TreeOrbit").transform;
        _orbitRing.SetParent(transform, false);

        var treeGroups = new Dictionary<int, List<Transform>>();

        var allChildren = GetComponentsInChildren<Transform>(true);
        foreach (var child in allChildren)
        {
            if (child == transform) continue;
            if (!child.name.StartsWith("TreeSymbol")) continue;

            int index = GetTreeIndex(child.name);
            if (index <= 0) continue;
            int slot = index - 1;
            if (slot >= MAX_TREES) continue;

            if (!treeGroups.ContainsKey(slot))
                treeGroups[slot] = new List<Transform>();
            treeGroups[slot].Add(child);
        }

        for (int i = 0; i < MAX_TREES; i++)
        {
            var slot = new TreeSlot();
            if (treeGroups.ContainsKey(i))
            {
                slot.orbitParts = treeGroups[i];
                foreach (var part in slot.orbitParts)
                    part.SetParent(_orbitRing, true);
            }
            _slots.Add(slot);
        }
    }

    int GetTreeIndex(string name)
    {
        int lastUnderscore = name.LastIndexOf('_');
        if (lastUnderscore >= 0)
        {
            string suffix = name.Substring(lastUnderscore + 1);
            if (int.TryParse(suffix, out int num))
                return num + 1;
        }
        return 0;
    }

    void SetupSquash()
    {
        _squash = GetComponent<SquashStretch>();
        if (_squash == null) _squash = gameObject.AddComponent<SquashStretch>();

        foreach (Transform child in transform)
        {
            if (child == _orbitRing) continue;
            string n = child.name;
            if (n.StartsWith("TreeSymbol") || n.StartsWith("_")) continue;

            // Recurse into Model container if present
            if (n == "Model")
            {
                foreach (Transform sub in child)
                {
                    string sn = sub.name;
                    if (sn.StartsWith("TreeSymbol") || sn.StartsWith("_")) continue;
                    if (sn.StartsWith("TackHead") || sn.StartsWith("TackShaft") || sn.StartsWith("TackTip")) continue;
                    _squash.AddPart(sub);
                }
                continue;
            }

            if (n.StartsWith("TackHead") || n.StartsWith("TackShaft") || n.StartsWith("TackTip")) continue;
            _squash.AddPart(child);
        }
    }

    void Update()
    {
        // Rotate orbit
        if (_orbitRing != null)
            _orbitRing.Rotate(0f, orbitSpeed * Time.deltaTime, 0f);

        if (Time.time - _lastAttackTime < cooldown / Mathf.Max(0.01f, attackSpeedMultiplier)) return;
        if (_waypoints == null || _waypoints.childCount < 2) return;

        // Find available tree slot
        int slotIndex = -1;
        for (int i = 0; i < _slots.Count; i++)
        {
            if (!_slots[i].deployed && _slots[i].orbitParts.Count > 0)
            {
                slotIndex = i;
                break;
            }
        }
        if (slotIndex < 0) return;

        // Place tree on a random path spot within range
        Vector3? spot = FindRandomPathSpotInRange();
        if (!spot.HasValue) return;

        _lastAttackTime = Time.time;
        LaunchTree(slotIndex, spot.Value);
    }

    Vector3? FindRandomPathSpotInRange()
    {
        var candidates = new List<(Vector3 a, Vector3 b)>();

        for (int i = 0; i < _waypoints.childCount - 1; i++)
        {
            Vector3 a = _waypoints.GetChild(i).position;
            Vector3 b = _waypoints.GetChild(i + 1).position;
            Vector3 closest = ClosestPointOnSegment(transform.position, a, b);
            float dist = Vector3.Distance(
                new Vector3(transform.position.x, 0, transform.position.z),
                new Vector3(closest.x, 0, closest.z));
            if (dist <= range)
                candidates.Add((a, b));
        }

        if (candidates.Count == 0) return null;

        for (int attempt = 0; attempt < 10; attempt++)
        {
            var (a, b) = candidates[Random.Range(0, candidates.Count)];
            float t = Random.Range(0f, 1f);
            Vector3 point = Vector3.Lerp(a, b, t);

            float dist = Vector3.Distance(
                new Vector3(transform.position.x, 0, transform.position.z),
                new Vector3(point.x, 0, point.z));
            if (dist <= range)
            {
                point.y = a.y + 0.06f;
                return point;
            }
        }

        return null;
    }

    Vector3 ClosestPointOnSegment(Vector3 p, Vector3 a, Vector3 b)
    {
        Vector3 ab = b - a;
        float t = Mathf.Clamp01(Vector3.Dot(p - a, ab) / ab.sqrMagnitude);
        return a + ab * t;
    }

    void LaunchTree(int slotIndex, Vector3 targetPos)
    {
        var slot = _slots[slotIndex];
        slot.deployed = true;

        _squash.Play();

        // Get orbit world position of tree (average of parts)
        Vector3 orbitPos = Vector3.zero;
        foreach (var p in slot.orbitParts)
            orbitPos += p.position;
        orbitPos /= slot.orbitParts.Count;

        // Hide orbit parts
        foreach (var p in slot.orbitParts)
            p.gameObject.SetActive(false);

        // Create deployed tree clone
        GameObject deployed = CloneTreeWithOutline(slot, orbitPos);

        // Fly to target
        StartCoroutine(FlyTreeToTarget(deployed, orbitPos, targetPos, slotIndex));
    }

    GameObject CloneTreeWithOutline(TreeSlot slot, Vector3 position)
    {
        Vector3 avgMeshCenter = Vector3.zero;
        int meshCount = 0;
        foreach (var part in slot.orbitParts)
        {
            var mf = part.GetComponent<MeshFilter>();
            if (mf == null || mf.sharedMesh == null) continue;
            avgMeshCenter += mf.sharedMesh.bounds.center;
            meshCount++;
        }
        if (meshCount > 0)
            avgMeshCenter /= meshCount;

        float scale = 4.5f;
        var root = new GameObject("DeployedTree");
        root.transform.SetParent(SceneContainers.Projectiles, false);
        root.transform.position = position;
        root.transform.localScale = Vector3.one * scale;

        foreach (var part in slot.orbitParts)
        {
            var mf = part.GetComponent<MeshFilter>();
            var mr = part.GetComponent<MeshRenderer>();
            if (mf == null || mr == null) continue;

            var clone = new GameObject(part.name);
            clone.transform.SetParent(root.transform, false);
            clone.transform.localPosition = -avgMeshCenter;
            clone.transform.localRotation = Quaternion.identity;
            clone.transform.localScale = Vector3.one;

            clone.AddComponent<MeshFilter>().sharedMesh = mf.sharedMesh;
            clone.AddComponent<MeshRenderer>().sharedMaterials = mr.sharedMaterials;

            // Purple telekinesis outline (slightly larger)
            var outline = new GameObject("_outline");
            outline.transform.SetParent(clone.transform, false);
            outline.transform.localScale = Vector3.one * 1.15f;

            outline.AddComponent<MeshFilter>().sharedMesh = mf.sharedMesh;
            outline.AddComponent<MeshRenderer>().sharedMaterial = _purpleMat;
        }

        return root;
    }

    IEnumerator FlyTreeToTarget(GameObject tree, Vector3 from, Vector3 to, int slotIndex)
    {
        float duration = Vector3.Distance(from, to) / launchSpeed * 4f;
        duration = Mathf.Max(duration, 0.6f);
        float elapsed = 0f;

        while (elapsed < duration)
        {
            elapsed += Time.deltaTime;
            float linear = elapsed / duration;
            float t = linear * linear * (3f - 2f * linear);
            Vector3 pos = Vector3.Lerp(from, to, t);
            pos.y += Mathf.Sin(t * Mathf.PI) * 1.0f;
            tree.transform.position = pos;
            tree.transform.Rotate(0f, 360f * Time.deltaTime, 0f);
            yield return null;
        }

        tree.transform.position = to;
        tree.transform.rotation = Quaternion.identity;

        // Remove telekinesis outlines after landing
        foreach (Transform child in tree.transform)
        {
            foreach (Transform sub in child)
            {
                if (sub.name == "_outline")
                    Destroy(sub.gameObject);
            }
        }

        // Add PathTree behavior
        var pt = tree.AddComponent<PathTree>();
        pt.damage = damage;
        pt.lifetime = treeLifetime;
        pt.source = GetComponent<TowerData>();
        pt.onDestroyed = () => ReturnTree(slotIndex);
    }

    public void ReturnTree(int slotIndex)
    {
        if (slotIndex < 0 || slotIndex >= _slots.Count) return;
        var slot = _slots[slotIndex];
        slot.deployed = false;

        foreach (var p in slot.orbitParts)
        {
            if (p != null)
                p.gameObject.SetActive(true);
        }
    }
}
