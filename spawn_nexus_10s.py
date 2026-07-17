"""Stage 30: launch nexus_daemon.bat for 10 seconds and observe it read-only."""
from __future__ import annotations
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

NEXUS = Path(r"C:\Users\87999\.nexus")
BAT = NEXUS / "nexus_daemon.bat"
LOG = NEXUS / "logs" / "nexus_startup.log"
PORT = "19666"


def _listeners() -> dict:
    run = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True)
    text = run.stdout.decode("latin-1", errors="replace")
    lines = [line.strip() for line in text.splitlines()
             if f":{PORT}" in line and "LISTENING" in line.upper()]
    pids = sorted({line.split()[-1] for line in lines if line.split()})
    return {"listening": bool(lines), "pids": pids, "lines": lines,
            "has_old_pid_11848": "11848" in pids}


def _log_tail() -> list[str]:
    if not LOG.exists():
        return [f"[missing] {LOG}"]
    return LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-50:]


def spawn_and_observe(seconds: float = 10.0) -> dict:
    """Start the daemon, observe for *seconds*, kill its process tree, return evidence."""
    if not BAT.is_file():
        raise FileNotFoundError(BAT)
    before = _listeners()
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        proc = subprocess.Popen(
            [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(BAT)],
            cwd=str(NEXUS), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", creationflags=flags)
    except Exception as exc:
        raise RuntimeError(f"Popen failed: {type(exc).__name__}: {exc}") from exc
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        at_10s = _listeners()
        killed = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.poll() is None:
            proc.kill()
        stdout, stderr = proc.communicate(timeout=10)
    else:
        at_10s = _listeners()
        killed = None
    time.sleep(0.5)
    return {
        "started_at": started, "bat": str(BAT), "pid": proc.pid,
        "exit_code": proc.returncode, "timed_out_at_10s": timed_out,
        "kill_rc": None if killed is None else killed.returncode,
        "kill_stdout": "" if killed is None else killed.stdout.strip(),
        "kill_stderr": "" if killed is None else killed.stderr.strip(),
        "port_before": before, "port_at_10s": at_10s,
        "port_after_kill": _listeners(),
        "stdout_head_200": stdout.splitlines()[:200],
        "stderr_head_200": stderr.splitlines()[:200],
        "startup_log_tail_50": _log_tail(),
    }


if __name__ == "__main__":
    from pprint import pprint
    pprint(spawn_and_observe(), sort_dicts=False)
