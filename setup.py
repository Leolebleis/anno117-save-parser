#!/usr/bin/env python3
"""Downloads and configures the third-party tooling used by extract.py.

Tools fetched:
  - RdaConsole (anno-mods/RdaConsole)   — RDA container unpacker
  - FileDBReader (anno-mods/FileDBReader) — FileDB binary -> XML

FileDBReader ships targeting .NET 6; this script patches its
runtimeconfig.json to roll forward to whatever modern .NET is installed.
"""
import argparse
import io
import json
import os
import shutil
import sys
import urllib.request
import zipfile

RDA_VERSION_DEFAULT = 'v1.2'
FDB_VERSION_DEFAULT = 'v3.0.3'

ROOT = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(ROOT, 'tools')


def fetch_zip(label: str, url: str, dest_dir: str) -> None:
    print(f'[setup] Downloading {label} from {url}')
    with urllib.request.urlopen(url) as resp:
        data = resp.read()
    if os.path.isdir(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(dest_dir)


def find_file(root: str, name: str) -> str | None:
    for dirpath, _dirnames, filenames in os.walk(root):
        if name in filenames:
            return os.path.join(dirpath, name)
    return None


def patch_filedbreader_runtimeconfig(fdb_root: str) -> None:
    rcfg = find_file(fdb_root, 'FileDBReader.runtimeconfig.json')
    if not rcfg:
        print('[setup] WARNING: FileDBReader.runtimeconfig.json not found; skipping patch')
        return
    print(f'[setup] Patching {rcfg} to roll forward to a major .NET version')
    with open(rcfg, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    cfg.setdefault('runtimeOptions', {})['rollForward'] = 'Major'
    with open(rcfg, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser(description='Download tooling for anno117-save-parser')
    ap.add_argument('--rdaconsole-version', default=RDA_VERSION_DEFAULT)
    ap.add_argument('--filedbreader-version', default=FDB_VERSION_DEFAULT)
    args = ap.parse_args()

    os.makedirs(TOOLS_DIR, exist_ok=True)

    fetch_zip(
        'RdaConsole',
        f'https://github.com/anno-mods/RdaConsole/releases/download/{args.rdaconsole_version}/RdaConsole.zip',
        os.path.join(TOOLS_DIR, 'RdaConsole'),
    )
    fdb_dir = os.path.join(TOOLS_DIR, 'FileDBReader')
    fetch_zip(
        'FileDBReader',
        f'https://github.com/anno-mods/FileDBReader/releases/download/{args.filedbreader_version}/FileDBReader.zip',
        fdb_dir,
    )
    patch_filedbreader_runtimeconfig(fdb_dir)

    rda_exe = find_file(os.path.join(TOOLS_DIR, 'RdaConsole'), 'RdaConsole.exe')
    fdb_exe = find_file(fdb_dir, 'FileDBReader.exe')

    print()
    print('[setup] Done.')
    print(f'  RdaConsole:    {rda_exe}')
    print(f'  FileDBReader:  {fdb_exe}')
    print()
    print('Next: extract assets.xml from your game install and build the GUID map.')
    print('  See README.md "Setup" section for the exact commands.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
