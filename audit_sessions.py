#!/usr/bin/env python3
"""Audit snapshot filenames, manifest references, and canonical JSON hashes."""
from hashlib import sha256
from json import dumps, loads
from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
MANIFEST = ROOT / "manifest.jsonl"
SNAPSHOTS = ROOT / "snapshots"
HASH = re.compile(r"^[0-9a-f]{64}$")
problems = []
referenced = set()

def fail(message):
    problems.append(message)

if not MANIFEST.is_file():
    fail(f"missing manifest: {MANIFEST}")

if not SNAPSHOTS.is_dir():
    fail(f"missing snapshots directory: {SNAPSHOTS}")

if MANIFEST.is_file():
    for number, raw in enumerate(
        MANIFEST.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw.strip()
        if not line:
            continue

        fields = line.split()
        if len(fields) != 2:
            fail(f"manifest line {number}: expected 'timestamp hash'")
            continue

        timestamp, digest = fields

        if not HASH.fullmatch(digest):
            fail(f"manifest line {number}: invalid hash {digest!r}")
            continue

        if digest in referenced:
            fail(f"manifest line {number}: duplicate hash {digest}")

        referenced.add(digest)
        snapshot = SNAPSHOTS / f"{digest}.json"

        if not snapshot.is_file():
            fail(f"manifest line {number}: missing snapshot {snapshot.name}")
            continue

        try:
            data = loads(snapshot.read_text(encoding="utf-8"))
            canonical = dumps(
                data,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
            actual = sha256(canonical).hexdigest()
        except Exception as error:
            fail(f"{snapshot.name}: invalid JSON or hash input: {error}")
            continue

        if actual != digest:
            fail(
                f"{snapshot.name}: canonical hash mismatch; "
                f"computed {actual}"
            )
        else:
            print(f"OK {digest} {timestamp}")

if SNAPSHOTS.is_dir():
    for entry in sorted(SNAPSHOTS.iterdir()):
        if not entry.is_file():
            fail(f"invalid snapshot entry: {entry.name}")
            continue
        if entry.suffix != ".json" or not HASH.fullmatch(entry.stem):
            fail(f"invalid snapshot filename: {entry.name}")
            continue
        if entry.stem not in referenced:
            fail(f"orphaned snapshot: {entry.name}")

if not referenced and SNAPSHOTS.is_dir():
    if any(SNAPSHOTS.iterdir()):
        fail("snapshots exist but manifest contains no valid references")

if problems:
    print("AUDIT FAILED")
    for problem in problems:
        print(f"  - {problem}")
    raise SystemExit(1)

print("AUDIT PASSED: manifest, filenames, and canonical content agree")
