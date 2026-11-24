# Model imports, draw calls, triangles, and colliders

The supplied import settings have some sensible defaults but do not establish that the models are optimized for this scene. Optimize Mesh = Everything reorders data; it does not simplify the mesh, merge material slots, or reduce visible object count. Reducing submitted geometry and rendering submissions requires separate work.

## Import settings assessment

| Screenshot setting | Assessment / action |
|---|---|
| Optimize Mesh = Everything | Keep enabled. Improves vertex/index ordering; not polygon reduction. |
| Generate Mesh LODs = off | Check each asset's existing LODs first. Trial generation on dense repeated props lacking LODs; inspect silhouettes, thin foliage, UVs, and shading. |
| Read/Write = on | Retains CPU mesh data. Disable selectively where runtime mesh access/batching/collider requirements do not need it. This is principally a memory change, not a draw-count change. |
| Mesh Compression = off | Not evidence of poor runtime geometry optimization. Compression reduces stored mesh size/precision, not triangle count. Trial low/medium compression only if its size saving and visual result are acceptable. |
| Generate Colliders = off | Reasonable default. Prefabs can still contain manually assigned Mesh Colliders. |
| Import BlendShapes = on | Unnecessary for ordinary environment meshes without blend shapes; disable per asset where unused. |
| Generate Lightmap UVs = on | Useful for meshes intended for baked lighting. Do not enable indiscriminately; do not remove from assets that use lightmaps. |
| Weld Vertices = on; 16-bit indices | Sensible where appropriate, but not a solution to millions of submitted triangles. |
| Normals imported; legacy tangents | Keep authored shading until verified. A tangent-mode change is primarily about shading correctness, not a draw-call fix. |

[Unity model import reference](https://docs.unity3d.com/6000.3/Documentation/Manual/FBXImporter-Model.html), [readable-mesh requirements](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/Mesh-isReadable.html), [Mesh LOD generation](https://docs.unity3d.com/6000.3/Documentation/Manual/lod/mesh-lod-generator.html).

## Project facts checked

- The metadata for 5_Weed_7 .fbx, Ivy_1.fbx, and 5_Weed 1.fbx under Assets/FileGame/Map/DL/Fristy stylize Modular Assets 2/Foliage/Plants currently serializes isReadable = 1, meshCompression = 0, addColliders = 0, and importBlendShapes = 1. Their stored import defaults differ from parts of the supplied screenshot, so the screenshot is not verification of every project model's settings.
- tree_1.prefab has one LODGroup with three LOD entries and one Capsule Collider. It has no explicit Mesh Collider. Its LOD screen-relative thresholds are approximately 0.5533, 0.1515, and 0.01.
- TileForestCamp.prefab contains 53 explicit Mesh Collider components: 50 non-convex, 3 convex, all serialized enabled, with cooking options 30. Named owners include crates, barrels, and tables. This is an authored component count, including potentially inactive/empty components; it is not a measured count of active physics shapes and does not include all nested/imported prefab contents.
- SRP Batcher is already enabled. The audited URP assets disable GPU Resident Drawer, while PC_Renderer uses Forward+. Repeated meshes are a reasonable candidate for a compatible GPU Resident Drawer test.
- The earlier dependency audit identifies hundreds of repeated weed/ivy references, separate from TerrainData trees. Reducing terrain trees alone will not remove those submissions.

## Rendering changes in priority order

1. Establish a settled Player capture with the same map/camera/resolution/lighting. Use Frame Debugger to identify whether the expensive submissions belong to foliage, terrain, props, shadows, or other passes. Raw source polygon count is not the same as submitted triangles across passes/cameras.
2. Reduce visible foliage density and distances. Temporarily hide terrain trees/details and separate weeds/ivy independently to measure their impact. Remove decorative duplicates that add little to the view; preserve gameplay-relevant silhouettes and cover.
3. Use lower-detail meshes at distance. Verify the existing tree LODs actually switch from the gameplay camera; add tested LODs to dense buildings/props without them, and cull tiny foliage earlier. For terrain surface geometry, separately test a larger heightmap pixel error and inspect terrain silhouette/road seams. Imported model LOD generation does not optimize TerrainData surfaces.
4. Reduce repeated submissions. Reuse the same mesh and shared material for repeated props, reduce unnecessary material/submesh splits, and verify the actual batching/instancing method in Frame Debugger. SRP Batcher reduces preparation overhead and does not guarantee fewer draw calls. An Enable GPU Instancing checkbox alone is not proof that draws are instanced.
5. Trial GPU Resident Drawer on a diagnostic active URP asset. Follow Unity's setup: Forward+, SRP Batcher enabled, GPU Resident Drawer = Instanced Drawing, and appropriate BatchRendererGroup shader variants. Confirm compatible objects appear as Hybrid Batch Group in Frame Debugger. Terrain surfaces are not ordinary MeshRenderer objects and require separate terrain optimization. [GPU Resident Drawer instructions](https://docs.unity3d.com/6000.3/Documentation/Manual/urp/gpu-resident-drawer.html).
6. Reduce shadow-casting clutter and shadow distance/cascades where the isolated shadow test improves timing. Avoid combining an entire moving map into one giant mesh: it can compromise culling and increase static-batching memory. Group truly fixed content into spatial chunks only after comparing visibility and submission cost.

Instancing can lower draw calls while leaving a similar triangle count. LOD/simplification can lower triangles without lowering draw calls. Record both counters and actual CPU/GPU timings instead of expecting one setting to fix both.

## Mesh Collider changes

Mesh Colliders are physics geometry; they do not directly add rendered triangles or visual draw calls. Replace crate collisions with Box Colliders, barrels/trunks with suitable primitive shapes, and complex moving objects such as a train with compound primitive colliders or simplified convex collision meshes. Preserve collision openings needed for gameplay. Keep non-convex Mesh Colliders for stationary, irregular surfaces where the accuracy is necessary; use a dedicated simpler collision mesh instead of the full visual mesh where practical. Small decorative foliage usually needs no collision.

The tile-transform audit already found CurvedHorizonTile updates parent positions. Review whether non-convex colliders under those parents actually move, and avoid unnecessary unchanged transform writes. Measure Physics.SyncTransforms, simulation, and cooking/loading markers before attributing frame cost to colliders. In the existing selected frame, rendering dominates over physics; collider optimization is a separate improvement.

[Unity Mesh Collider guidance](https://docs.unity3d.com/6000.3/Documentation/Manual/mesh-colliders-introduction.html).

No model settings, geometry, materials, collision behavior, or scene configuration were changed by this assessment; no speedup is claimed without a comparison capture.
