using UnityEngine;
using UnityEngine.EventSystems;

public class MeshDetector : MonoBehaviour
{
    void Start()
    {
        addPhysicsRaycaster();
    }

    void addPhysicsRaycaster()
    {
        PhysicsRaycaster physicsRaycaster = FindFirstObjectByType<PhysicsRaycaster>();
        if (physicsRaycaster == null)
        {
            transform.gameObject.AddComponent<PhysicsRaycaster>();
        }
    }

    public void OnPointerClick(PointerEventData eventData)
    {
        throw new System.NotImplementedException();
    }
}