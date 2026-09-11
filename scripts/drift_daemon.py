#!/usr/bin/env python3
"""Passive drift watcher: never writes to the repo. Alerts on transitions only."""
import fcntl, subprocess, sys, time, datetime, pathlib, os, signal

REPO = pathlib.Path("/home/droid/handover")
LOCK = REPO / ".audit_logs" / "repo.lock"
LOG = REPO / ".audit_logs" / "sync_drift.log"
INTERVAL = int(os.environ.get("SYNC_INTERVAL_SECONDS", "300"))
REMOTE = os.environ.get("GIT_REMOTE_NAME", "origin")
BRANCH = os.environ.get("GIT_BRANCH_NAME", "main")
running = True

def log(level, msg):
    ts = datetime.datetime.now(datetime.timezone.utc)
    line = f"[{ts:%Y-%m-%dT%H:%M:%SZ}] [{level}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")
    subprocess.run(["logger", "-t", "handover-sync-monitor",
                    "-p", f"daemon.{level.lower()} ", msg], capture_output=True)

def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=REPO, check=check,
                          capture_output=True, text=True)

def classify(local, remote):
    git("fetch", REMOTE, BRANCH)          # refs only; working tree untouched
    base = git("merge-base", local, remote,
               check=False).stdout.strip()
    if not base:
        return "DIVERGED-UNRELATED"
    if local == base:   return "BEHIND"
    if remote == base:  return "AHEAD"
    return "DIVERGED"

def shutdown(sig, frame):
    global running
    running = False
signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

log(f"INFO Drift daemon started ({REMOTE}/{BRANCH}, interval {INTERVAL}s)")
last_state = None
while running:
    lockfile = open(LOCK, "w")
    locked = True
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("INFO Sync in progress (lock held); skipping cycle.")
        last_state = None  # force re-alert if drift persists after sync
        time.sleep(INTERVAL)
        continue

    try:
        local = git("rev-parse", "--verify", "HEAD",
                    check=False).stdout.strip()
        out = subprocess.run(
            ["git", "ls-remote", REMOTE, f"refs/heads/{BRANCH}"],
            cwd=REPO, capture_output=True, text=True, timeout=30)
        remote = out.stdout.split()[0] if out.returncode == 0 and out.stdout.strip() else ""

        if not local:
            log("ERROR Local HEAD unresolved."); last_state = None
        elif not remote:
            log("WARNING Remote unreachable; skipping cycle.")
            if last_state != "UNREACHABLE":
                log("WARNING State transition -> UNREACHABLE")
            last_state = "UNREACHABLE"
        elif local == remote:
            if last_state not in (None, "IN_SYNC"):
                log("INFO State transition -> IN SYNC")
            last_state = "IN_SYNC"
        else:
            state = classify(local, remote)
            if state != last_state:
                log(f"CRITICAL Drift [{state}] Local:{local[:7]} Remote:{remote[:7]}"
                    f" | {git('log','-1','--format=%h (%s)',check=False).stdout.strip()}")
            last_state = state
    except Exception as e:
        log(f"ERROR Check cycle exception: {e}")
        last_state = None
    finally:
        fcntl.flock(lockfile, fcntl.LOCK_UN)
        lockfile.close()

    # sleep in short slices so SIGTERM lands promptly
    for _ in range(INTERVAL):
        if not running:
            break
        time.sleep(1)

log("INFO Drift daemon stopped cleanly")
