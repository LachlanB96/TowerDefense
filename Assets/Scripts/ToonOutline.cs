using UnityEngine;

public class ToonOutline : MonoBehaviour
{
    [SerializeField] private float _outlineWidth = 0.04f;
    [SerializeField] private Color _outlineColor = Color.black;

    void Awake()
    {
        var shader = Shader.Find("Custom/ToonOutline");
        if (shader == null) return;

        var outlineMat = new Material(shader);
        outlineMat.SetFloat("_OutlineWidth", _outlineWidth);
        outlineMat.SetColor("_OutlineColor", _outlineColor);

        // Skinned meshes (units) — duplicate the renderer sharing bones
        foreach (var smr in GetComponentsInChildren<SkinnedMeshRenderer>())
        {
            var outlineObj = new GameObject("_Outline");
            outlineObj.transform.SetParent(smr.transform, false);

            var outlineSmr = outlineObj.AddComponent<SkinnedMeshRenderer>();
            outlineSmr.sharedMesh = smr.sharedMesh;
            outlineSmr.bones = smr.bones;
            outlineSmr.rootBone = smr.rootBone;
            outlineSmr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            outlineSmr.receiveShadows = false;

            var mats = new Material[smr.sharedMesh.subMeshCount];
            for (int i = 0; i < mats.Length; i++)
                mats[i] = outlineMat;
            outlineSmr.sharedMaterials = mats;
        }

        // Static meshes (towers) — combine body meshes into one, skip orbiting tack parts
        var allFilters = GetComponentsInChildren<MeshFilter>();
        var bodyFilters = new System.Collections.Generic.List<MeshFilter>();
        foreach (var mf in allFilters)
        {
            string n = mf.gameObject.name;
            if (n.StartsWith("TackHead") || n.StartsWith("TackShaft") || n.StartsWith("TackTip"))
                continue;
            bodyFilters.Add(mf);
        }

        if (bodyFilters.Count > 0)
        {
            var combines = new CombineInstance[bodyFilters.Count];
            for (int i = 0; i < bodyFilters.Count; i++)
            {
                combines[i].mesh = bodyFilters[i].sharedMesh;
                combines[i].transform = transform.worldToLocalMatrix * bodyFilters[i].transform.localToWorldMatrix;
            }

            var combinedMesh = new Mesh();
            combinedMesh.name = "OutlineCombined";
            combinedMesh.CombineMeshes(combines, true, true);
            combinedMesh.RecalculateNormals();

            var outlineObj = new GameObject("_Outline");
            outlineObj.transform.SetParent(transform, false);

            var outlineMf = outlineObj.AddComponent<MeshFilter>();
            outlineMf.sharedMesh = combinedMesh;

            var outlineMr = outlineObj.AddComponent<MeshRenderer>();
            outlineMr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            outlineMr.receiveShadows = false;
            outlineMr.sharedMaterial = outlineMat;
        }
    }
}
