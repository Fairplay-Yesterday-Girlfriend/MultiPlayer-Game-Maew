# Hypotheses and fixes for [Ten] Test Player

EditorLoop has no fixed normal percentage of main-thread time. At saved frame 1532, its four occurrences total 42.179 ms of the 101.932 ms main-thread frame, about 41.4%. This is elapsed time, potentially including waits. Optimize and compare milliseconds rather than targeting a particular percentage. Removing Editor work does not imply the same elapsed-time saving in a standalone Player, because rendering, waiting, and camera workloads can differ.

The user clarified that “2 URP” means two pipeline assets. Unity uses one active pipeline asset selected by the current Quality override, falling back to the Graphics default. These assets are configurations; their presence does not double-render the map. In this repository Graphics defaults to PC_RPAsset, while Low/Medium/High reference their own assets. Saved m_CurrentQuality = 2 selects High; SettingManager can change the quality level at runtime, so verify the active asset during the test. The scene's authored Main Camera uses the default renderer and an empty overlay stack; runtime cameras and Scene View are separate considerations. [Unity active pipeline selection](https://docs.unity3d.com/6000.1/Documentation/Manual/srp-setting-render-pipeline-asset.html).

## Evidence and test order

Use the same deterministic tile sequence, camera pose, resolution, day/night state, quality, and capture modules. Warm up loading and shaders, record at least 300 settled frames, and compare median/p95 frame time, main/render-thread samples, GPU duration when available, batches, and triangles. Change one variable per test in diagnostic copies. Deep Profiling should be off for the timing comparison.

| Hypothesis | Evidence | Isolation test | Fix if the test supports it |
|---|---|---|---|
| Editor redraws a heavy environment alongside Game View | 42.18 ms EditorLoop in selected frame; saved log has SceneView URP shadow rendering | Compare Scene View visible vs closed, Game View maximized, same running game; profile Editor target to expand its children | Keep Scene View closed while benchmarking; simplify its effects/gizmos; use standalone Player captures for shipping performance |
| Foliage and map density overload rendering submission | Edit Mode screenshot: 2,386 batches, 4.5M triangles; Game camera render path is 39.25 ms in saved frame | Separately hide terrain trees/details, then separate weed/ivy/rock objects, in a temporary scene copy | Tune LODs/culling distances, thin low-value foliage, test compatible mesh/detail instancing and terrain surface instancing |
| Shadow passes repeatedly draw much of the map | High URP: 4 cascades, distance 100, high soft-shadow quality, additional shadows; Scene View log confirms additional-shadow rendering | Turn off additional-light shadows only; restore them and separately test main-light shadows off | Keep shadows on key lights, bake suitable fixed content, test 2 cascades and 40–60 unit shadow distance, review shadow-casting foliage |
| Full-screen renderer effects add a large graphics cost | Shared PC_Renderer contains SSAO, decals, volumetric fog; night profile enables fog | Disable SSAO only, then restore and test night fog separately; GPU timings needed to identify GPU execution cost | Downsample SSAO; reduce fog steps/quality; restrict expensive effects by quality and camera |
| Editor tooling/Console/import activity inflates Others | Editor callbacks exist; no detailed Editor children in current capture | Profile Editor target and find the actual costly child: Scene View, Inspector, Console, Profiler, refresh/import, or callback | Address the named activity; limit repetitive logging/repaint work or fix a refresh loop if measured |

Unity recommends reducing shadow distance/cascades, additional-light shadow use, unnecessary cameras, and expensive effects as measured URP optimization options: [URP performance configuration](https://docs.unity3d.com/6000.3/Documentation/Manual/urp/configure-for-better-performance.html).

## Important implementation details

- Low, Medium, and High share PC_Renderer. A separate URP test asset must also use a separate renderer copy if a renderer feature will be changed independently; otherwise the feature change affects every quality using that renderer.
- Low still enables additional-light shadows with a 2048 atlas. A Low quality comparison does not isolate or eliminate that cost.
- Camera far clip is broadly configured at 1000 in the earlier audit. Test a shorter distance only after checking required gameplay sightlines and the active Cinemachine lens; terrain tree distance alone is not visibility.
- SRP Batcher is already enabled; it does not replace the need to reduce visible submissions or verify compatible instancing.
- Unused files on disk are a lower-priority explanation for continuous frame cost than active rendered content. Editor scripts can remain active even when associated art is unused; only a measured callback/import cost justifies linking cleanup to this slowdown.

No measured speedup is claimed. These tests distinguish Editor overhead from genuine game rendering cost before permanent art-quality changes are made.
