# anno117-save-parser

Tools for extracting and analyzing **Anno 117: Pax Romana** save files (`.a8s`) on Windows.

The pipeline converts an opaque ~3 MB binary save into ~120 MB of structured XML you can grep, parse, or hand to an AI assistant — no screenshots required.

## What you get

- **`extract.py`** — turns a `.a8s` save into XML files (meta, header, gamesetup, data + per-session blobs)
- **`build_guid_map.py`** — parses the game's `assets.xml` into a 29k-entry `GUID → name` map
- **`analyze.py`** — empire summary (cash, income, population, happiness, religion, prestige)
- **`analyze_trade.py`** — enumerates trade routes, distinguishes player-owned vs NPC passive trade
- **`count_buildings_v2.py`** — authoritative building counter (residences per tier, production buildings, marvels, etc.)
- **`setup.py`** — one-shot installer for the third-party tooling

## How it works

`.a8s` is an [RDA v2.2 container](https://github.com/lysanntranvouez/RDAExplorer/wiki/RDA-File-Format) — same magic string as Anno 1800 (`Resource File V2.2`). Inside are 4 zlib-compressed [FileDB v1](https://github.com/anno-mods/FileDBReader) documents. The tools chain:

1. **`RdaConsole`** unpacks the outer RDA container → 4 inner `.a7s` files
2. **`zlib.decompress`** strips the zlib wrapper from each
3. **`FileDBReader`** converts FileDB binary → XML

The session-state portion (the bulk of the save) contains nested `<BinaryData>` blobs that are themselves complete FileDB v1 documents — they're decoded the same way for full visibility into placed buildings, trade routes, etc.

## Setup (Windows + .NET 8 + Python 3.10+)

```bash
# downloads RdaConsole, FileDBReader, patches FileDBReader for .NET 8
python setup.py
```

That places everything under `tools/`. You also need `assets.xml` from your installed game — extract it directly from the game's RDA archive:

```bash
# Steam path (adjust for Ubisoft Connect / Epic)
./tools/RdaConsole/build/RdaConsole.exe extract \
    -f "C:/Program Files (x86)/Steam/steamapps/common/Anno 117 - Pax Romana/maindata/config.rda" \
    --filter "assets\.xml$" -o ./game_data -y -n

python build_guid_map.py --assets game_data/data/base/config/export/assets.xml --out guid_map.json
```

## Usage

```bash
# 1. extract a save
python extract.py \
    --save "$USERPROFILE/Documents/Anno 117 - Pax Romana/accounts/<guid>/<profile>/Autosave 256.a8s" \
    --out-dir ./out

# 2. inspect the empire
python analyze.py --xml-dir ./out
python analyze_trade.py --xml-dir ./out
python count_buildings_v2.py --xml-dir ./out --guid-map guid_map.json
```

`./out` will contain:

| File | Size | Contents |
|------|------|----------|
| `meta.xml` | ~360 B | Game version, save name |
| `header.xml` | ~480 KB | Player profiles, map setup |
| `gamesetup.xml` | ~70 KB | Map/scenario settings |
| `data.xml` | ~120 MB | Full game state |
| `session_blob_0.xml` | ~57 MB | Latium session (decoded from data.xml's BinaryData) |
| `session_blob_1.xml` | ~60 MB | Albion session |

Total extraction time: **~2 seconds** on a modern machine.

## Heads-up: scripts contain hard-coded participant IDs

The analyzer scripts were calibrated against one specific save. Before running them on yours, find these constants and replace them:

| File | Constant | What it is |
|------|----------|------------|
| `analyze.py`, `analyze_trade.py` | `HUMAN_PID_HEX = '29000000'` | Your participant ID in `EconomyManager`'s `<ParticipantGUID>` (LE hex) |
| `count_buildings_v2.py` | `LATIUM_AREAS`, `ALBION_AREAS` | Your owned `AreaID`s per session |

To find your `HUMAN_PID_HEX`:
- Run `analyze.py` once. It already auto-detects the human via `find_human()` (heuristic: positive net income + multiple bought settlements). Look at the printed `pid` and convert to LE hex.
- Or grep `data.xml` for `<ParticipantGUID>` in the `EconomyManager` block — there are typically 4 participants (1 human + 3 AI).

To find your `AreaID`s: the `analyze_trade.py` output prints stations with `AreaOwner=<your-pid>`. Collect those AreaIDs.

(Patches welcome to make this fully auto-detected.)

## Reliability notes

- **Use structured XML tag matching, not byte-pattern scans.** A naive byte-pattern scan of the binary blobs (e.g., counting how often a building's GUID appears as 4 bytes) produces wildly inflated counts because the same GUID gets referenced by registries, quest caches, upgrade-tier lists, and buff effects — not just placements. The byte-noise floor for "this building is registered in the game" can be 15–25 even when zero are placed.
- **`PopulationManager.MaxReachedPopulationCount`** is the gold standard for "did I ever reach tier X" — if a tier ID is missing entirely, you've never had a single resident at that tier.
- **`<guid>...</guid>` (lowercase) and `<GUID>...</GUID>` (uppercase)** both occur in session blobs depending on object type. The counter handles both.

## What's NOT extracted

- **Ship counts** — ships are placed entities but I haven't reverse-engineered which tag delineates them; the byte-pattern method gave unreliable numbers for ships specifically.
- **Per-island building maps** — `count_buildings_v2.py` reports per-area but doesn't render a map.
- **Storage levels per island** — visible in the data (`MetaStorageCount`, `Goods`) but not exposed by the current scripts.

## Roadmap

This is an MVP. Direction it should grow in:

1. **JSON intermediate format.** XML is what FileDBReader produces; it's verbose, leaf values are hex strings, and anonymous list entries serialize as `<None>` with no semantic name. A post-processing step that emits typed JSON (decoding hex → int/float/string, naming list entries via known schema fragments) would make downstream analysis dramatically simpler.
2. **Web frontend for data viz.** Once the data is JSON, a static site (residence tier breakdown, trade route map, production health by good) is straightforward.
3. **Auto-detect human player + AreaIDs.** The current scripts hardcode IDs from one specific save; the heuristic is well-defined (positive net income + multiple bought settlements for the player, AreaOwner of player-owned trade-route stations for the islands) and just needs wiring up.

When extending, prefer to keep `extract.py` as a thin pipeline shim and put schema knowledge / decoding logic into a separate Python module so it's reusable from a future JSON exporter.

## License & legal

Code: pick your own license (suggest MIT). Game data files (`assets.xml`, save files, `guid_map.json` derived from `assets.xml`) belong to Ubisoft Blue Byte and are not redistributed.

## Credits / dependencies

- [`anno-mods/RdaConsole`](https://github.com/anno-mods/RdaConsole) — RDA outer container extraction
- [`anno-mods/FileDBReader`](https://github.com/anno-mods/FileDBReader) — FileDB binary → XML
- [Anno modding wiki — RDA file format](https://github.com/lysanntranvouez/RDAExplorer/wiki/RDA-File-Format)
- [`anno-mods/asset-extractor`](https://github.com/anno-mods/asset-extractor) — original inspiration for the asset extraction step
