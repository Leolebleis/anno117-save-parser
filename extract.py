#!/usr/bin/env python3
"""Anno 117 .a8s save -> XML extractor.

Pipeline:
  1. RdaConsole unpacks the outer RDA container (.a8s) -> 4 inner .a7s files
  2. Each .a7s is zlib-compressed; decompress -> .bin
  3. FileDBReader: FileDB binary -> XML
  4. data.xml contains nested <BinaryData> blobs (per-session game state) that
     are themselves complete FileDB v1 documents — decode them too.
"""
import argparse
import os
import re
import subprocess
import sys
import zlib

ROOT = os.path.dirname(os.path.abspath(__file__))
RDA_EXE = os.path.join(ROOT, 'tools', 'RdaConsole', 'build', 'RdaConsole.exe')
FDB_EXE = os.path.join(ROOT, 'tools', 'FileDBReader', 'FileDBReader', 'FileDBReader.exe')

INNER_NAMES = ('meta', 'header', 'gamesetup', 'data')


def need(path: str, hint: str) -> None:
    if not os.path.exists(path):
        sys.exit(f'ERROR: {hint} missing: {path}\nRun `python setup.py` first.')


def step(n: int, total: int, msg: str) -> None:
    print(f'[{n}/{total}] {msg}')


def main() -> int:
    ap = argparse.ArgumentParser(description='Extract an Anno 117 .a8s save to XML')
    ap.add_argument('--save', required=True, help='Path to a .a8s save file')
    ap.add_argument('--out-dir', default='./out', help='Output directory (default: ./out)')
    args = ap.parse_args()

    need(RDA_EXE, 'RdaConsole.exe')
    need(FDB_EXE, 'FileDBReader.exe')
    if not os.path.exists(args.save):
        sys.exit(f'ERROR: save not found: {args.save}')

    os.makedirs(args.out_dir, exist_ok=True)
    abs_out = os.path.abspath(args.out_dir)
    abs_save = os.path.abspath(args.save)

    # 1. RDA -> 4 inner .a7s files
    step(1, 4, f'Unpack RDA container -> {abs_out}')
    # RdaConsole's library calls Console.Clear which crashes when stdout is
    # redirected; -n suppresses its console output to avoid that path.
    subprocess.run(
        [RDA_EXE, 'extract', '-f', abs_save, '-o', abs_out, '-y', '-n'],
        cwd=os.path.dirname(RDA_EXE),
        check=True,
    )

    # 2. zlib -> .bin
    step(2, 4, 'zlib-decompress inner .a7s -> .bin')
    for name in INNER_NAMES:
        src = os.path.join(abs_out, name + '.a7s')
        if not os.path.exists(src):
            continue
        with open(src, 'rb') as f:
            raw = f.read()
        dst = os.path.join(abs_out, name + '.bin')
        with open(dst, 'wb') as f:
            f.write(zlib.decompress(raw))
        print(f'  {name}.a7s -> {name}.bin')

    # 3. FileDB -> XML (top-level)
    step(3, 4, 'FileDB binary -> XML (top-level)')
    bins = [os.path.join(abs_out, n + '.bin') for n in INNER_NAMES]
    bins = [b for b in bins if os.path.exists(b)]
    if bins:
        subprocess.run([FDB_EXE, 'decompress', '-f', *bins, '-c', '1', '-y'], check=True)

    # 4. Nested per-session FileDB blobs inside data.xml
    step(4, 4, 'Decode nested per-session BinaryData blobs in data.xml')
    data_xml = os.path.join(abs_out, 'data.xml')
    session_bins = []
    if os.path.exists(data_xml):
        with open(data_xml, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        for i, m in enumerate(re.finditer(r'<BinaryData>([0-9A-Fa-f]+)</BinaryData>', text)):
            blob = bytes.fromhex(m.group(1))
            dst = os.path.join(abs_out, f'session_blob_{i}.bin')
            with open(dst, 'wb') as f:
                f.write(blob)
            session_bins.append(dst)
            print(f'  -> session_blob_{i}.bin ({len(blob):,} bytes)')
        if session_bins:
            subprocess.run(
                [FDB_EXE, 'decompress', '-f', *session_bins, '-c', '1', '-y'],
                check=True,
                stdout=subprocess.DEVNULL,
            )
    else:
        print('  data.xml missing — nothing to do')

    print()
    print(f'Done. XML files in {abs_out}:')
    for entry in sorted(os.listdir(abs_out)):
        if entry.endswith('.xml'):
            size = os.path.getsize(os.path.join(abs_out, entry))
            print(f'  {entry:<30s} {size:>14,} bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main())
