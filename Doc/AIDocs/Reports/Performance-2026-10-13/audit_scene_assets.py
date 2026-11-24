"""Read-only authored-asset audit; does not launch Unity or change game assets.

Usage: python audit_scene_assets.py --deps PATH_TO_LIBS
Requires PyYAML and UnityPy. Counts are authored dependency occurrences,
not visible draw calls; prefab overrides and LOD selection are not applied.
"""
import argparse
import collections
import functools
import json
import pathlib
import re
import sys

args = argparse.ArgumentParser()
args.add_argument('--deps')
args.add_argument('--terrain-only', action='store_true', help='Refresh binary terrain metrics using the existing authored inventory.')
options = args.parse_args()
if options.deps:
    sys.path.insert(0, options.deps)
import yaml
import UnityPy

ROOT = pathlib.Path(__file__).resolve().parents[4]
OUT = pathlib.Path(__file__).resolve().parent
guid_paths = {}
for meta in (ROOT / 'Assets').rglob('*.meta'):
    match = re.search(r'^guid: ([0-9a-f]{32})$', meta.read_text(encoding='utf-8-sig', errors='replace'), re.M)
    if match:
        guid_paths[match[1]] = meta.with_suffix('')

def rel(path):
    return str(path.relative_to(ROOT)).replace('\\', '/')

@functools.lru_cache(None)
def documents(path):
    text = path.read_text(encoding='utf-8-sig', errors='replace')
    result = []
    for match in re.finditer(r'^--- !u!(\d+) &(-?\d+)(?: stripped)?\n(.*?)(?=^--- !u!|\Z)', text, re.M | re.S):
        data = yaml.load(match[3], Loader=getattr(yaml, 'CSafeLoader', yaml.SafeLoader))
        if data:
            result.append((int(match[1]), int(match[2]), next(iter(data.values()))))
    return result

@functools.lru_cache(None)
def expand(path):
    counts = collections.Counter()
    terrains = []
    dependencies = collections.Counter()
    for class_id, file_id, data in documents(path):
        if data.get('m_CorrespondingSourceObject', {}).get('fileID', 0) != 0 and class_id != 1001:
            continue  # stripped references are not new components
        if class_id in (1, 23, 137, 218, 108, 205, 20):
            counts[{1:'game_objects', 23:'mesh_renderers', 137:'skinned_renderers', 218:'terrains', 108:'lights', 205:'lod_groups', 20:'cameras'}[class_id]] += 1
        if class_id == 23:
            counts['renderer_material_slots'] += len(data.get('m_Materials', []))
            counts['shadow_casting_mesh_renderers'] += int(data.get('m_CastShadows', 0) != 0)
        if class_id == 218:
            terrains.append({'owner_asset': rel(path), 'component_file_id': file_id, **{k:v for k,v in data.items() if k in ('m_TerrainData','m_DrawInstanced','m_DetailObjectDensity','m_DetailObjectDistance','m_TreeDistance','m_ShadowCastingMode')}})
        if class_id == 1001:
            source = data.get('m_SourcePrefab', {}).get('guid')
            child = guid_paths.get(source)
            if child:
                dependencies[rel(child)] += 1
                if child.suffix == '.prefab':
                    subcounts, subterrain, subdeps = expand(child)
                    counts.update(subcounts)
                    terrains.extend(subterrain)
                    dependencies.update(subdeps)
                else:
                    counts['unexpanded_model_instances'] += 1
            else:
                counts['unresolved_prefab_instances'] += 1
    return counts, terrains, dependencies

def compact(value):
    if isinstance(value, dict):
        return {k:compact(v) for k,v in value.items() if not isinstance(v, (bytes, bytearray))}
    if isinstance(value, list):
        return {'length':len(value), 'first':compact(value[0]) if value else None}
    return value

terrain_cache = {}
def terrain_summary(guid):
    if guid in terrain_cache:
        return terrain_cache[guid]
    path = guid_paths.get(guid)
    result = {'path':rel(path) if path else None}
    if path:
        try:
            env = UnityPy.load(str(path))
            for obj in env.objects:
                if obj.type.name == 'TerrainData':
                    tree = obj.read_typetree()
                    result['keys'] = list(tree)
                    result['summary'] = compact(tree)
                    detail = tree['m_DetailDatabase']
                    def reference_path(ptr):
                        file_id = ptr.get('m_FileID', 0)
                        if not file_id:
                            return None
                        external = obj.assets_file.externals[file_id - 1]
                        # Unity's serialized GUID hex reverses the nibbles in each byte.
                        binary_guid = external.guid.hex()
                        text_guid = ''.join(binary_guid[i:i+2][::-1] for i in range(0, 32, 2))
                        target = guid_paths.get(text_guid)
                        return rel(target) if target else (external.path or 'unresolved:' + text_guid)
                    instances = detail.get('m_TreeInstances', [])
                    tree_counts = collections.Counter(t['index'] for t in instances)
                    result['metrics'] = {
                        'terrain_layers':len(tree['m_SplatDatabase']['m_TerrainLayers']),
                        'heightmap_resolution':tree['m_Heightmap']['m_Resolution'],
                        'tree_instances':len(instances),
                        'populated_detail_patches':sum(bool(p['layerIndices']) for p in detail['m_Patches']),
                        'tree_prototypes':[{'asset':reference_path(p['prefab']), 'instances':tree_counts[i]} for i,p in enumerate(detail['m_TreePrototypes'])],
                        'detail_prototypes':[{'asset':reference_path(p['prototype']) or reference_path(p['prototypeTexture']), 'mesh':p['usePrototypeMesh'], 'instanced':p['useInstancing']} for p in detail['m_DetailPrototypes']],
                    }
        except Exception as error:
            result['error'] = str(error)
    terrain_cache[guid] = result
    return result

scene = ROOT / 'Assets/FileGame/Core/Scenes/[Ten] Test Player.unity'
scene_docs = documents(scene)
map_data = next(d for _,_,d in scene_docs if (d.get('m_EditorClassIdentifier') or '').endswith('::EndlessMapManager'))
tile_guids = [t['guid'] for t in map_data['startTiles']]
tile_guids += [t['guid'] for b in map_data['biomes'] for t in b['tilePrefabs']]
tile_guids += [map_data['transitionTilePrefab']['guid']]
assets = [scene] + [guid_paths[g] for g in dict.fromkeys(tile_guids)]
report = {'method':'Authored YAML components recursively expanded by prefab dependency occurrence. Includes inactive assets and all LODs; does not apply instance overrides. Imported model instances are listed but not expanded. Not measured frame statistics.', 'map_settings':map_data, 'assets':[]}
if options.terrain_only:
    report = json.loads((OUT / 'authored_asset_audit.json').read_text(encoding='utf-8'))
    for guid in report['terrain_data']:
        terrain_summary(guid)
else:
    for path in assets:
        counts, terrains, dependencies = expand(path)
        report['assets'].append({'asset':rel(path), 'counts':dict(counts), 'terrains':terrains, 'dependencies':dict(dependencies)})
        for terrain in terrains:
            terrain_summary(terrain['m_TerrainData']['guid'])
report['terrain_data'] = terrain_cache
(OUT / 'authored_asset_audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
for row in report['assets']:
    print(row['asset'], json.dumps(row['counts']))
    print('  top dependencies:', collections.Counter(row['dependencies']).most_common(6))
for data in terrain_cache.values():
    print('TERRAIN', data['path'], list(data.get('summary', {})), data.get('error',''))
