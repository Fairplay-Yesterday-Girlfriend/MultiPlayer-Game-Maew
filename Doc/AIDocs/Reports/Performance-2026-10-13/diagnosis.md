# Technical art performance audit — [Ten] Test Player

Date: 13 October 2026 (Asia/Bangkok). Unity 6000.3.4f1, URP 17.4.0, Direct3D 11.

## Finding

**The attached capture's dominant CPU cost is the “Others” category, approximately 205.79 ms. Editor overhead is the strongest explanation to investigate first. A separate, substantial environment rendering load is confirmed: approximately 11,550 batches and 5.99 million triangles in the selected frame.**

This is a source/asset investigation combined with the user's existing Profiler image and the current Editor log. It is not a fresh runtime timing capture or a measured before/after optimization. There is no saved capture in the project's `ProfilerCaptures` directory, and no callable Unity MCP connection was available. The exact sample responsible for the 205.79 ms cannot be named from an overview graph.

## 1. What the screenshot proves

The screenshot selects frame 9008 and profiles **Play Mode**. The CPU tooltip values read approximately:

Original image, copied without changes: [Profiler capture](<C:/Users/Apricha/Documents/GitHub/MultiPlayer-Game-Maew/Doc/AIDocs/Reports/Performance-2026-10-13/user-profiler-capture.png>).

| Category / counter | Visible value | Interpretation |
|---|---:|---|
| Others | 205.79 ms | Dominates the selected frame; requires a sample breakdown |
| Rendering | 19.12 ms | Already exceeds a complete 60 FPS budget of 16.67 ms |
| Scripts | 5.84 ms | Material cost, but much smaller than Others |
| Physics | 3.72 ms | Secondary cost in this frame |
| Animation | 0.04 ms | Small in this frame |
| Garbage Collector | 0.00 ms | No collection time visible in this frame; this does not establish zero allocations |
| VSync | 0.07 ms | The VSync category does not explain this selected spike |
| Batches | 11.55k | Very large amount of submitted rendering work |
| SetPass calls | 239 | Shader-pass changes; not the same metric as batches |
| Triangles | 5.99M | Submitted triangles, potentially including repeated passes |
| Vertices | 12.32M | Submitted vertices |

The selected CPU categories total roughly 235 ms, so this selected spike is worse than a 100 ms / 10 FPS frame. It does not establish the average or median gameplay frame time. The graph remains high after the rendering counters jump, suggesting a sustained workload change rather than only the first scene-loading frame.

Unity explicitly documents that, when targeting Play Mode, EditorLoop timings are grouped into Others. This makes Editor work the leading hypothesis for the large olive-colored block, but it is not proof of a particular child sample. [Unity 6.3: Play mode and Editor samples](https://docs.unity3d.com/6000.3/Documentation/Manual/profiler-play-edit-samples.html).

The CPU graph includes time spent waiting as well as doing work. GPU time must be read separately and correlated with the main/render thread timeline. An overview screenshot cannot establish whether graphics submission, GPU execution, or Editor work is the limiting factor. [Unity 6.3: Profiler markers](https://docs.unity3d.com/6000.3/Documentation/Manual/profiler-markers.html).

## 2. Evidence from this project

### A. Heavy scene rendering is also performed by the Editor

The recent Editor log contains additional-light shadow atlas warnings after loading `[Ten] Test Player` and spawning the four initial map tiles. The stack includes `AdditionalLightsShadowCasterPass.Setup`, `UniversalRenderPipeline.RenderSingleCamera`, `UnityEditor.Handles.Internal_DrawCameraWithGrid`, and `UnityEditor.SceneView.DoOnGUI`.

The warnings report **5**, and later **17**, additional punctual-light shadow maps competing for a **2048 × 2048 atlas**. This is direct runtime evidence of multiple shadow renders, not a count inferred only from serialized settings.

This establishes that Scene View was rendering the environment and its shadows during that recorded session. It does not give its duration or establish an exact frame match with the screenshot. Together with Others dominating a Play Mode capture, it is strong reason to investigate `EditorLoop` → Scene View/repaint/rendering first. See the preserved, selective [Editor log evidence](editor_evidence.txt).

Unity initializes D3D11 on **AMD Radeon(TM) Graphics**. Windows reports an **AMD Ryzen 5 4600G with Radeon Graphics**. That is the integrated graphics configuration on this machine; hardware capability is relevant to the GPU workload, but hardware identity alone does not prove the bottleneck.

### B. Four large generated tiles plus the authored starting environment

The scene's MapManager specifies **4 tiles**, **119 units per tile**, **119 units recycle distance**, and **3 safe flat tiles**. The generated route nominally spans 476 units. `WaitAndSpawnInitialMap` instantiates all four synchronously, and recycling destroys and instantiates whole tiles. Those operations can cause startup/recycle spikes; their event-driven frequency does not by itself explain every slow frame.

The authored scene also contains two occurrences of the `StartMap` prefab and a `TileSample` prefab, with instance overrides. The generator's four-tile limit therefore does not describe all environment content present in the scene. Whether each authored occurrence is active/visible must be checked at runtime.

Sources: [scene map configuration](<C:/Users/Apricha/Documents/GitHub/MultiPlayer-Game-Maew/Assets/FileGame/Core/Scenes/[Ten] Test Player.unity:2377>), [map instantiation](<C:/Users/Apricha/Documents/GitHub/MultiPlayer-Game-Maew/Assets/FileGame/Core/Scripts/Core/MapManager/EndlessMapManager.cs:225>).

### C. Repeated foliage and rocks are the strongest art-side submission suspects

The read-only dependency audit gives the following **authored inventory**, not runtime visible counts. It recursively expands prefab dependencies, includes inactive objects and all LODs, does not apply instance overrides/removals, and leaves imported FBX instances unexpanded. Terrain trees are read separately from their binary TerrainData assets and are not included in the MeshRenderer column.

| Tile | YAML MeshRenderers | Imported model instances | Terrain components | Authored terrain trees |
|---|---:|---:|---:|---:|
| TileForestCamp | 333 | 896 | 3 | 256 |
| junkyard | 236 | 990 | 3 | 159 |
| TileWaitmap1 | 103 | 0 | 3 | 279 |
| TileWaitmap2 | 103 | 0 | 3 | 199 |
| Tile transition | 103 | 0 | 0 | 0 |

ForestCamp's imported references include **336 copies of `5_Weed_7 .fbx`**, **294 of `Ivy_1.fbx`**, and **84 of `5_Weed 1.fbx`**. Junkyard includes **320**, **281**, and **80** respectively, plus **174** references to `2_Rock.fbx`. This repeated content is a credible source of many draw submissions and foliage overdraw across multiple loaded tiles. Frame Debugger is needed to assign the 11,550 batches to particular objects and passes.

The terrain trees resolve to `tree_1.prefab`, which already contains three LOD meshes. The evidence does not support claiming that all trees have no LODs.

Raw results and exact paths are in [authored_asset_audit.json](authored_asset_audit.json). The audit script is retained for reproduction; it never launches Unity or edits game assets.

### D. Distance and terrain settings keep a broad environment eligible for rendering

The main camera uses **far clip 1000**, includes all layers, and has shadows and post-processing enabled. The player's FreeLook camera prefab also specifies far clip 1000. The scene has no assigned baked occlusion data. Ordinary frustum culling still works; the absence of baked data does not mean all culling is disabled.

Each inspected tile terrain component has **Draw Instanced = 0**, **detail distance 80**, **detail density 1**, and **tree distance 5000**. The actual camera far clip still limits visibility. Some mesh detail prototypes already have instancing enabled; terrain surface instancing and detail-prototype instancing are separate settings.

Binary TerrainData inspection found **17 assigned layers in StartMap**, **16 in ForestCamp1**, and **16 in junkyard1**. These are assigned layer counts, not counts of layers actually contributing at each visible pixel. Investigate the actual TerrainLit/additional passes in Frame Debugger before estimating their cost.

Sources: [main camera](<C:/Users/Apricha/Documents/GitHub/MultiPlayer-Game-Maew/Assets/FileGame/Core/Scenes/[Ten] Test Player.unity:20110>), [ForestCamp terrain settings](<C:/Users/Apricha/Documents/GitHub/MultiPlayer-Game-Maew/Assets/FileGame/Core/Prefab/MapTile/Biome Forest/TileForestCamp.prefab:775>).

### E. Shadow and full-screen effects amplify the environment workload

All Low/Medium/High URP assets reference the same `PC_Renderer`. It is **Forward+** (`m_RenderingMode: 2`, verified against the installed URP enum), with active SSAO, decal, and volumetric fog renderer features. SSAO has **Downsample = 0**. Medium and High use **four shadow cascades**, high soft-shadow quality, and additional-light shadows. The log confirms additional shadow maps were rendered in the recorded gameplay session.

The scene's day volumetric-fog profile has **enabled = 0**, while the night profile has **enabled = 1**, **128 maximum raymarch steps**, and **2 blur iterations**. The custom fog implementation renders at half width and height, then blurs and composites. This is a specific nighttime GPU suspect, not evidence that fog caused the initial daytime slowdown.

Sources: [renderer](<C:/Users/Apricha/Documents/GitHub/MultiPlayer-Game-Maew/Assets/Simple-Multiplayer/Core/Settings/PC_Renderer.asset:104>), [night fog](<C:/Users/Apricha/Documents/GitHub/MultiPlayer-Game-Maew/Assets/FileGame/Core/Scenes/[Ten] Test Player/Night Global Volume Profile.asset:687>), [raymarch loop](<C:/Users/Apricha/Documents/GitHub/MultiPlayer-Game-Maew/Packages/com.cqf.urpvolumetricfog/Shaders/VolumetricFog.hlsl:213>).

SRP Batcher is **already enabled** on every URP quality asset. GPU Resident Drawer is disabled. The renderer already meets its Forward+ requirement; evaluate mesh/shader compatibility and batching behavior before changing it. [Unity 6.3: GPU Resident Drawer](https://docs.unity3d.com/6000.3/Documentation/Manual/urp/gpu-resident-drawer.html).

### F. Moving entire tile hierarchies is a secondary CPU/physics suspect

`CurvedHorizonTile.Update` calls `SetYPosition` every frame, and that method always writes `transform.position`, including when a tile is already flat or clamped to its final curve depth. Moving a parent containing many renderers/colliders can create transform/bounds/physics work; many authored child objects are marked static. Add a position-change guard and review movable tile batching assumptions only after measuring the relevant transform and physics markers. This code pattern is observed; its millisecond impact is unmeasured.

Source: [tile transform update](<C:/Users/Apricha/Documents/GitHub/MultiPlayer-Game-Maew/Assets/FileGame/Core/Scripts/Core/MapManager/CurvedHorizonTile.cs:61>).

## 3. Verification order and optimization priorities

Keep the same spawned tile sequence, camera, resolution, quality level, and day/night state across comparisons. Warm up scene loading and shader compilation, then record about 300 steady frames and compare median/p95 frame time, main/render thread work, GPU time, batches, triangles, and GC allocations.

| Order | Isolation test | Evidence to record |
|---|---|---|
| 1 | Select a slow frame; inspect CPU Hierarchy and Timeline. Target the Editor process to expand EditorLoop. | Exact child marker accounting for Others; screenshot of both PlayerLoop and EditorLoop |
| 2 | Repeat with Game View maximized, Scene View closed, no heavy object selected, and only necessary Profiler modules. Then compare a Development Player. | Whether Others collapses; Editor vs standalone timing difference |
| 3 | Disable foliage/rocks on one heavy tile in a temporary diagnostic copy; separately disable terrain trees/details. | Batches and geometry reduction, CPU submission time and GPU improvement |
| 4 | Test a shorter camera far clip, e.g. 200–250 units, after checking required sightlines. Update the active Cinemachine lens as well. | Distant content culled; visible popping/art impact; timing improvement |
| 5 | Disable additional-light shadows; test one/two main-light cascades. | Shadow pass count, batches, GPU and CPU rendering change |
| 6 | Disable SSAO; at night separately disable volumetric fog or reduce steps to 32–64. | GPU pass duration and frame-time delta per effect |
| 7 | Test terrain surface instancing, fewer used terrain layers, and compatible mesh instancing/GPU Resident Drawer. | Frame Debugger grouping and terrain pass reduction |
| 8 | Add a tile position-change guard in a diagnostic branch; test pooled/asynchronous tile initialization if spawn spikes remain. | Transform/physics markers; startup/recycle p95 spikes |

If the dominant marker is `EditorLoop`, optimize or remove the expensive Editor activity and use standalone results for the shipping budget. If the main thread waits on graphics, inspect the render thread: active command submission points to CPU rendering pressure; long presentation waits correlated with GPU duration point to GPU pressure. Do not equate a wait marker with active CPU work.

## 4. Scope and remaining uncertainty

Confirmed: a dominant Others spike in the supplied screenshot, exceptionally high rendering counters, heavy repeated environment content, broad camera distance, non-instanced terrain surfaces, shared renderer features, nighttime raymarch fog, and Scene View shadow rendering in the log.

Likely: Editor rendering/profiling overhead makes up much of Others, while foliage/terrain/shadows create a genuine rendering bottleneck on this hardware.

Unresolved: the precise 205.79 ms sample, standalone player FPS, GPU pass timings, runtime visible renderer counts, and the contribution of each asset group. No measured FPS gain is claimed. Only this report and its supporting evidence were added; gameplay code, scenes, prefabs, and rendering settings were not changed.
