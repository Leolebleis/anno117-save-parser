# anno117-save-parser

Extract and analyze Anno 117: Pax Romana `.a8s` saves on Windows.

## Pipeline shape (don't reinvent)

`.a8s` → RdaConsole → 4 zlib blobs → `zlib.decompress` → FileDB v1 → FileDBReader → XML. `extract.py` runs the chain.

`data.xml` contains nested `<BinaryData>` elements that are themselves complete FileDB v1 documents (`08000000fdffffff` magic tail). `extract.py` step 4 decodes them into `session_blob_*.xml`.

## Counting placed objects (the #1 trap)

**DO** match `<guid>HEX</guid>` / `<GUID>HEX</GUID>` with `re.compile(r'<(\w+)>HEX</\1>')` (proper backrefs). Both cases occur; case depends on object type.

**DO NOT** byte-pattern scan binary blobs for a GUID's 4 LE bytes. The same GUID surfaces in registries, quest caches, upgrade-tier lists, and buff effects, inflating counts 10–50×. Noise floor for an unbuilt building is 15–25.

`PopulationManager.MaxReachedPopulationCount` is the ground truth for "did the player ever reach tier X" — a missing tier-ID entry means zero residents ever lived at that tier.

## XML quirks

- FileDBReader leaves values as hex strings. Decode by context: int32/uint32/int64 LE, float32 LE, or UTF-16LE. No type info in the XML.
- Anonymous FileDB list entries serialize as `<None>...</None>`.
- Tag names containing spaces (e.g. `AI Time`) get dropped during conversion; use FileDBReader `-z` to rename if needed.
- `<ID>16-hex-chars</ID>` encodes AreaID at chars 8–11 (bytes 4–5 of the 8-byte ObjectID).

## Per-save hardcoded constants (replace before running on a new save)

- `analyze.py`, `analyze_trade.py`: `HUMAN_PID_HEX` — LE hex of human's `<ParticipantGUID>` in `EconomyManager`. `analyze.py`'s `find_human()` auto-detects via heuristic (positive net income + multiple bought settlements).
- `count_buildings_v2.py`: `LATIUM_AREAS`, `ALBION_AREAS` — 4-hex AreaIDs from trade-route stations marked `AreaOwner=<your-pid>`.

## Tooling gotchas

- FileDBReader ships targeting .NET 6. `setup.py` patches its `runtimeconfig.json` with `"rollForward": "Major"` so it runs on .NET 8.
- RdaConsole's library calls `Console.Clear()`, which crashes when stdout is redirected. Always pass `-n`.
- FileDBReader `-c 1` expects already-decompressed FileDB bytes (NOT zlib-wrapped). Anno 117 wraps FileDB in zlib externally, so strip with `zlib.decompress` first, then call FileDBReader. `-c 2` does NOT match the Anno 117 wrapper version — don't use it as a shortcut.
- `setup.py` pins RdaConsole v1.2 and FileDBReader v3.0.3.

## Running Python scripts

- Windows console defaults to cp1252; UTF-16-decoded names (player profile, save name, etc.) crash with `UnicodeEncodeError`. Either prefix with `PYTHONIOENCODING=utf-8` or call `sys.stdout.reconfigure(encoding='utf-8')` at the top of any script that prints decoded strings.

## Repo conventions

- LF line endings (enforced by `.gitattributes`).
- Gitignored: `tools/`, `game_data/`, `guid_map.json`, `*.a8s`, `*.a7s`, `*.bin`, `/out/`. The Ubisoft asset data and the user's saves never ship.
- Bash on Windows uses Unix paths (`/c/Users/...`); PowerShell tool available when needed.

## Roadmap direction (don't lock decisions away from)

Future: post-process XML → typed JSON (decoding hex into int/float/string), then a static-site frontend for visualization. Keep `extract.py` thin; put schema knowledge in a separate module so a JSON exporter can reuse it.
