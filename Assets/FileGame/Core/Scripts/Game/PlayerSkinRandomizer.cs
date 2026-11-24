using System;
using Unity.Netcode;
using UnityEngine;

public class PlayerSkinRandomizer : NetworkBehaviour
{
    [Serializable]
    private struct Skin
    {
        [Tooltip("Model using the same rig and bind pose as the player.")]
        public GameObject model;
        public Material material;
    }

    [SerializeField] private SkinnedMeshRenderer targetRenderer;
    [SerializeField] private int materialIndex;
    [SerializeField] private Skin[] skins;

    private readonly NetworkVariable<int> currentSkinIndex = new NetworkVariable<int>(
        -1, NetworkVariableReadPermission.Everyone, NetworkVariableWritePermission.Server);

    public override void OnNetworkSpawn()
    {
        base.OnNetworkSpawn();

        if (IsServer && skins != null && skins.Length > 0)
            currentSkinIndex.Value = UnityEngine.Random.Range(0, skins.Length);

        currentSkinIndex.OnValueChanged += OnSkinIndexChanged;
        ApplySkin(currentSkinIndex.Value);
    }

    public override void OnNetworkDespawn()
    {
        currentSkinIndex.OnValueChanged -= OnSkinIndexChanged;
        base.OnNetworkDespawn();
    }

    private void OnSkinIndexChanged(int previousValue, int newValue)
    {
        ApplySkin(newValue);
    }

    private void ApplySkin(int index)
    {
        if (targetRenderer == null || skins == null || index < 0 || index >= skins.Length)
            return;

        Skin skin = skins[index];
        if (skin.model == null || skin.material == null)
            return;

        var sourceRenderer = skin.model.GetComponentInChildren<SkinnedMeshRenderer>(true);
        if (sourceRenderer == null || sourceRenderer.sharedMesh == null)
            return;

        Material[] materials = targetRenderer.sharedMaterials;
        if (materialIndex < 0 || materialIndex >= materials.Length)
            return;

        // The skin models share this player's animated skeleton and bind poses.
        targetRenderer.sharedMesh = sourceRenderer.sharedMesh;
        materials[materialIndex] = skin.material;
        targetRenderer.sharedMaterials = materials;
    }
}
