# Edit Mode map rendering and EditorLoop

The new Statistics screenshot supports the map as a major rendering suspect. It does not establish that all of the Profiler's Others category is map work.

## New screenshot evidence

![Statistics with Play Mode off](C:/Users/Apricha/Documents/GitHub/MultiPlayer-Game-Maew/Doc/AIDocs/Reports/Performance-2026-10-14/edit-mode-statistics.png)

| Metric | Screenshot value |
|---|---:|
| CPU main | 23.9 ms |
| CPU render thread | 13.2 ms |
| Batches | 2,386 |
| Triangles | 4.5 million |
| Vertices | 6.2 million |
| SetPass calls | 107 |
| Saved by batching | 0 |
| Shadow casters | 0 |
| Resolution | 1920 × 1080 |

These counters show substantial rendering without gameplay simulation. Main and render thread times overlap and must not be added. The snapshot is an Edit Mode view, so it is not a standalone gameplay FPS measurement. CPU main includes Editor activity; the render-thread statistic is not GPU execution time. Unity defines these fields in its [Statistics reference](https://docs.unity3d.com/6000.3/Documentation/Manual/RenderingStatistics.html). Saved by batching = 0 does not by itself prove SRP Batcher is disabled. Shadow casters = 0 applies to this snapshot; earlier runtime log evidence contains Scene View additional-shadow work.

![Map overview provided by the user](C:/Users/Apricha/Documents/GitHub/MultiPlayer-Game-Maew/Doc/AIDocs/Reports/Performance-2026-10-14/edit-mode-map.png)

## Why map work can appear in Others

Scene View renders the terrain, trees, buildings, props, and enabled effects while the Editor repaints. During Play Mode it can render alongside Game View, creating extra camera work. Unity groups EditorLoop under Others when profiling Play Mode and suppresses its detailed child samples. Targeting the Editor process exposes those child samples: [Play Mode and Editor samples](https://docs.unity3d.com/6000.3/Documentation/Manual/profiler-play-edit-samples.html).

The previous saved log explicitly contains SceneView.DoOnGUI and Handles.Internal_DrawCameraWithGrid in URP additional-shadow stacks. This proves that the map was also being rendered by Scene View in that session, but the log does not assign milliseconds to it. At saved frame 1532, four unexpanded EditorLoop occurrences total 42.18 ms of elapsed main-thread time. The map's share of that time remains unmeasured, and waits can contribute to the elapsed duration.

## Current project settings checked

TileForestCamp.prefab has three Terrain components. All three currently serialize tree distance 5000, billboard distance 50, maximum full-LOD trees 50, detail distance 80, detail density 1, heightmap pixel error 5, and Draw Instanced = 0 (first occurrence at lines 776–788). The earlier dependency audit also found many separate ivy, weed, and rock model instances. Optimizing only TerrainData trees would leave that separate foliage workload in place. Tree distance 5000 does not override camera clipping; the active camera still determines which objects can be seen. Terrain component count alone does not determine cost; geometry, trees/details, materials, distance, passes, and visible instances matter.

## Unnecessary project files

Unused art files sitting in Assets are not rendered simply because they exist. They can add disk/import/cache/indexing/preview costs, especially when files change or the Asset Database refreshes; deleting them is not yet an evidenced fix for a sustained 100 ms frame. Unity documents refresh triggers and importing in [Asset Database refresh](https://docs.unity3d.com/6000.3/Documentation/Manual/AssetDatabaseRefreshing.html).

Installed Editor code is a separate case: it can register callbacks even if its related art assets are unused. The project includes PurrNet editor callbacks, an inspector that can repaint every 0.5 seconds, and a SoundDef custom inspector with preview update/constant-repaint behavior. Their presence does not establish a significant cost. The custom GeneratePlayerStatsAssets initializer schedules a delayed call after initialization; it is not a per-frame update registration.

## Isolation tests

1. Keep the same camera, quality, resolution, and map. Profile the Editor target, expand its CPU hierarchy, and find SceneView/Repaint/rendering, Inspector, Console, Profiler, or import/update work.
2. Compare the same Play Mode view with Scene View closed and Game View maximized. Inspect how much EditorLoop and frame time decrease.
3. In a temporary scene copy, compare trees/details disabled, separate foliage disabled, and terrain surfaces disabled one group at a time. Record batch count and main/render-thread timings. This assigns cost to the asset group rather than to the whole map.
4. Compare a standalone Development Player to measure the game's budget without Scene View and editor panels.

The leading explanation is expensive visible map rendering amplified by Editor camera/repaint work. The screenshots and capture do not prove that unused files or every millisecond of Others are the cause.
