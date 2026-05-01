# anno117-save-parser

Extract and analyze **Anno 117: Pax Romana** save files (`.a8s`) on Windows.

A `.a8s` save is a ~3 MB opaque binary. This pipeline expands it into ~120 MB of structured XML you can grep, parse, or hand to an AI assistant.

## Scripts

| Script | Purpose |
|--------|---------|
| `extract.py` | Decode a `.a8s` save into XML (meta, header, gamesetup, data, per-session blobs) |
| `build_guid_map.py` | Parse `assets.xml` into a 29k-entry `GUID -> name` map |
| `analyze.py` | Empire summary: cash, income, population, happiness, religion, prestige |
| `analyze_trade.py` | List trade routes; separate player-owned from NPC passive trade |
| `count_buildings_v2.py` | Count residences per tier, production buildings, marvels, and more |
| `setup.py` | Install third-party tooling |

## How it works

`.a8s` is an [RDA v2.2 container](https://github.com/lysanntranvouez/RDAExplorer/wiki/RDA-File-Format) sharing the magic string `Resource File V2.2` with Anno 1800. Inside sit four zlib-compressed [FileDB v1](https://github.com/anno-mods/FileDBReader) documents. The pipeline:

1. **`RdaConsole`** unpacks the outer RDA container into four inner `.a7s` files
2. **`zlib.decompress`** strips each zlib wrapper
3. **`FileDBReader`** converts FileDB binary to XML

Session-state blobs, the bulk of the save, hold nested `<BinaryData>` elements that are themselves complete FileDB v1 documents. Decode them the same way to expose placed buildings, trade routes, and the rest.

## Setup (Windows + .NET 8 + Python 3.10+)

```bash
# Downloads RdaConsole and FileDBReader; patches FileDBReader for .NET 8
python setup.py
```

This installs everything under `tools/`. You also need `assets.xml` from your installed game. Pull it directly from the game's RDA archive:

```bash
# Steam path (adjust for Ubisoft Connect / Epic)
./tools/RdaConsole/build/RdaConsole.exe extract \
    -f "C:/Program Files (x86)/Steam/steamapps/common/Anno 117 - Pax Romana/maindata/config.rda" \
    --filter "assets\.xml$" -o ./game_data -y -n

python build_guid_map.py --assets game_data/data/base/config/export/assets.xml --out guid_map.json
```

## Usage

```bash
# 1. Extract a save
python extract.py \
    --save "$USERPROFILE/Documents/Anno 117 - Pax Romana/accounts/<guid>/<profile>/Autosave 256.a8s" \
    --out-dir ./out

# 2. Inspect the empire
python analyze.py --xml-dir ./out
python analyze_trade.py --xml-dir ./out
python count_buildings_v2.py --xml-dir ./out --guid-map guid_map.json
```

`./out` contains:

| File | Size | Contents |
|------|------|----------|
| `meta.xml` | ~360 B | Game version, save name |
| `header.xml` | ~480 KB | Player profiles, map setup |
| `gamesetup.xml` | ~70 KB | Map and scenario settings |
| `data.xml` | ~120 MB | Full game state |
| `session_blob_0.xml` | ~57 MB | Latium session (decoded from `data.xml` `<BinaryData>`) |
| `session_blob_1.xml` | ~60 MB | Albion session |

A modern machine finishes extraction in **~2 seconds**.

## Replace hard-coded participant IDs

The analyzer scripts target one specific save. Before running them on yours, find these constants and replace them:

| File | Constant | Meaning |
|------|----------|---------|
| `analyze.py`, `analyze_trade.py` | `HUMAN_PID_HEX = '29000000'` | Your participant ID in `EconomyManager`'s `<ParticipantGUID>` (LE hex) |
| `count_buildings_v2.py` | `LATIUM_AREAS`, `ALBION_AREAS` | Your owned `AreaID`s per session |

To find your `HUMAN_PID_HEX`:
- Run `analyze.py` once. `find_human()` already auto-detects the human via heuristic (positive net income plus multiple bought settlements). Read the printed `pid` and convert to LE hex.
- Or grep `data.xml` for `<ParticipantGUID>` inside the `EconomyManager` block. Saves typically hold four participants: one human and three AI.

To find your `AreaID`s, run `analyze_trade.py` and collect every AreaID whose station prints `AreaOwner=<your-pid>`.

## Reliability notes

- **Use structured XML tag matching, not byte-pattern scans.** Counting how often a building's GUID appears as 4 bytes inflates results wildly: the same GUID surfaces in registries, quest caches, upgrade-tier lists, and buff effects, not just placements. The byte-noise floor for "this building is registered" sits at 15 to 25 even when zero exist on the map.
- **`PopulationManager.MaxReachedPopulationCount`** is the gold standard for "did I ever reach tier X". A missing tier ID means you never housed a single resident at that tier.
- Session blobs use both `<guid>...</guid>` and `<GUID>...</GUID>` depending on object type. The counter handles both.

## Out of scope

- **Ship counts.** Ships are placed entities, but the delineating tag remains unidentified; byte-pattern scans returned wildly inflated numbers for ships.
- **Per-island building maps.** `count_buildings_v2.py` reports per-area but draws no map.
- **Storage levels per island.** The data exposes `MetaStorageCount` and `Goods`, but the current scripts ignore them.

## Roadmap

This is an MVP. Next directions:

1. **JSON intermediate format.** FileDBReader emits XML: verbose, hex-encoded leaves, anonymous list entries serialized as `<None>` with no semantic name. A post-processor that emits typed JSON, decoding hex into int, float, or string and naming list entries from known schema fragments, would simplify everything downstream.
2. **Web frontend for visualization.** Once the data lives in JSON, a static site can render residence tiers, trade routes, and production health by good.
3. **Auto-detect human player and AreaIDs.** The heuristic is well-defined (positive net income plus multiple bought settlements identifies the human; AreaOwner of player-owned trade-route stations identifies the islands) and only needs wiring up.

Keep `extract.py` as a thin pipeline shim. Put schema knowledge and decoding logic into a separate Python module so a future JSON exporter can reuse it.

## License and legal

Code: pick your own license (MIT recommended). Game data files (`assets.xml`, save files, `guid_map.json` derived from `assets.xml`) belong to Ubisoft Blue Byte and ship nowhere.

## Credits and dependencies

- [`anno-mods/RdaConsole`](https://github.com/anno-mods/RdaConsole) — RDA outer container extraction
- [`anno-mods/FileDBReader`](https://github.com/anno-mods/FileDBReader) — FileDB binary to XML
- [Anno modding wiki — RDA file format](https://github.com/lysanntranvouez/RDAExplorer/wiki/RDA-File-Format)
- [`anno-mods/asset-extractor`](https://github.com/anno-mods/asset-extractor) — original inspiration for the asset extraction step
