#!/usr/bin/env python3
"""Handover sync writer: pull -> commit real changes -> checksums -> push."""
import fcntl, subprocess, sys, datetime, pathlib

REPO = pathlib.Path("/home/droid/handover")
LOCK = REPO / ".audit_logs" / "repo.lock"
ARTIFACTS = ["HANDOVER.json", "manifest.json", "scripts/", "docs/"]

def run(*args, check=True):
    return subprocess.run(args, cwd=REPO, check=check,
                          capture_output=True, text=True)

def log(msg):
    ts = datetime.datetime.now(datetime.timezone.utc)
    line = f"[{ts:%Y-%m-%dT%H:%M:%SZ}] [SYNC] {msg}"
    print(line)
    with open(REPO / ".audit_logs" / "sync.log", "a") as f:
        f.write(line + "\n")

def main():
    with open(LOCK, "w") as lockfile:
        try:
            fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("Lock held (drift or prior sync); skipping cycle.")
            return 0

        # 1. Pull with rebase; abort quietly if remote moved awkwardly
        pull = run(["git", "pull", "--rebase", "origin", "main"], check=False)
        if pull.returncode != 0:
            log(f"PULL-REBASE FAILED: {pull.stderr.strip()[:200]}")
            return 1

        # 2. Commit ONLY real changes to handover artifacts
        status = run(["git", "status", "--porcelain"]).stdout.splitlines()
        relevant = [l for l in status
                    if any(a.rstrip("/") in l for a in ARTIFACTS)]
        if relevant:
            for line in relevant:
                run(["git", "add", "--", line.split()[-1]])
            run(["git", "commit", "-m",
                 f"chore: sync artifacts {ts:%Y-%m-%dT%H:%M:%SZ}"])
            log(f"Committed {len(relevant)} artifact change(s).")
        else:
            log("No artifact changes; no commit minted.")

        # 3. Regenerate checksums AFTER any commit, then push
        sums = run(["sha256sum", "HANDOVER.json", "manifest.json",
                    "scripts/repo-ctl", "sync_and_monitor.sh"], check=False)
        if sums.returncode == 0:
            (REPO / "HANDOVER.sha256").write_text(sums.stdout)
            run(["git", "add", "HANDOVER.sha256"])
            if run(["git", "diff", "--cached", "--quiet"],
                   check=False).returncode != 0:
                run(["git", "commit", "-m", "chore: refresh checksums"])
                log("Checksums regenerated and committed.")

        push = run(["git", "push", "origin", "main"], check=False)
        if push.returncode != 0:
            log(f"PUSH FAILED: {push.stderr.strip()[:200]}")
            return 1
        log("Push complete; local == remote.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
