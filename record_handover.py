#!/usr/bin/env python3
"""
record_handover.py – Content-Addressed Handover System
------------------------------------------------------
Normalizes, hashes, and snapshots handover manifests.
Exits non-zero on dirty tree or tag mismatch (fail-closed).
"""

import os
import sys
import json
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

# --- Constants -----------------------------------------------------------
TOOLKIT_DIR = Path.home() / "toolkit"
SNAPSHOT_DIR = TOOLKIT_DIR / "handover_snapshots"
REPO_DIR = Path.home() / "reverse-dns-repo"
HANDOVER_SRC = REPO_DIR / "HANDOVER.json"
SNAPSHOT_SCHEMA = {
    "id": str,
    "timestamp": str,
    "normalized_json": str,
    "sha256": str,
    "git_status": str,
    "tag_state": str,
    "diff_report": Optional[Dict[str, Any]]
}

# --- Helpers -------------------------------------------------------------
def normalize_json(raw: Dict[str, Any]) -> str:
    """Return canonical JSON string with sorted keys and trimmed whitespace."""
    return json.dumps(raw, sort_keys=True, indent=2, ensure_ascii=False).strip()

def sha256_hex(content: str) -> str:
    """Return SHA-256 hex digest of normalized content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def git_status() -> str:
    """Return short git status output."""
    try:
        return subprocess.check_output(
            ["git", "status", "--short"], cwd=REPO_DIR, text=True
        ).strip()
    except subprocess.CalledProcessError:
        return "UNVERIFIED"

def tag_state() -> str:
    """Return current tag or 'UNVERIFIED'."""
    try:
        tag = subprocess.check_output(
            ["git", "describe", "--tags", "--exact-match"], cwd=REPO_DIR, text=True
        ).strip()
        return tag if tag else "UNVERIFIED"
    except subprocess.CalledProcessError:
        return "UNVERIFIED"

def semantic_removals(prev: Dict[str, Any], curr: Dict[str, Any]) -> Dict[str, Any]:
    """Return paths removed from the tree between two handover manifests."""
    prev_files = {f["path"] for f in prev.get("repository_structure", {}).get("files", [])}
    curr_files = {f["path"] for f in curr.get("repository_structure", {}).get("files", [])}
    return {"removed_paths": sorted(list(prev_files - curr_files))}

def diff_report(prev_path: Optional[Path], curr_path: Path) -> Optional[Dict[str, Any]]:
    """Generate diff report between previous and current snapshot."""
    if not prev_path or not prev_path.exists():
        return None
    try:
        prev = json.loads(prev_path.read_text())
        curr = json.loads(curr_path.read_text())
        return {
            "semantic_removals": semantic_removals(prev, curr),
            "formatting_changes": "N/A"  # Handled by normalization
        }
    except Exception as e:
        return {"error": str(e)}

# --- Main -----------------------------------------------------------------
def main() -> int:
    # 1️⃣ Ensure directories exist
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # 2️⃣ Load and normalize the handover manifest
    if not HANDOVER_SRC.exists():
        print("❌ HANDOVER.json not found in reverse-dns-repo", file=sys.stderr)
        return 1
    raw = json.loads(HANDOVER_SRC.read_text())
    normalized = normalize_json(raw)
    sha = sha256_hex(normalized)

    # 3️⃣ Fail-closed checks
    status = git_status()
    tag = tag_state()
    if status != "":
        print(f"❌ Dirty tree detected:\n{status}", file=sys.stderr)
        return 1
    if tag == "UNVERIFIED":
        print("❌ Tag state unverified", file=sys.stderr)
        return 1

    # 4️⃣ Build snapshot payload
    snapshot = {
        "id": sha,
        "timestamp": subprocess.check_output(
            ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], text=True
        ).strip(),
        "normalized_json": normalized,
        "sha256": sha,
        "git_status": status,
        "tag_state": tag,
        "diff_report": diff_report(
            next(SNAPSHOT_DIR.glob("*.json"), None),
            HANDOVER_SRC
        )
    }

    # 5️⃣ Write snapshot atomically
    dest = SNAPSHOT_DIR / f"{sha}.json"
    dest.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))

    # 6️⃣ Print summary
    print(f"✅ Snapshot recorded: {dest.name}")
    print(f"   SHA-256: {sha}")
    print(f"   Tag: {tag}")
    if snapshot["diff_report"]:
        print("   Diff report:")
        print(f"     Semantic removals: {snapshot['diff_report']['semantic_removals']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
