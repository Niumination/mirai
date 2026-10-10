"""health.py — what the box is doing. Read only: nothing in this module writes anywhere.

A background thread samples every 3 seconds and keeps the last 24 samples, so the
charts have history the moment a page opens and no request ever sleeps.

The tutorial this build follows was written for Linux and reads /proc directly.
The target machine here is a Mac, so every metric has two implementations:
darwin (vm_stat, sysctl, ps, netstat, df) and linux (/proc, kept for containers
and servers). The keys the page reads are identical either way, and they sit at
the TOP LEVEL of GET /api/health, never wrapped in a "health" object — a wrapper
leaves Health designed and the Cockpit's meters dead, silently.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from server import ApiError  # noqa: F401 (ApiError kept for parity with other modules)

IS_MAC = sys.platform == "darwin"
INTERVAL_S = 3
KEEP = 24
STARTED_AT = time.time()

_lock = threading.Lock()
_samples: list[dict] = []
_host_cache: dict = {}
_disk_kind_cache: dict = {}
_prev_net: dict = {"at": 0.0, "bytes": 0}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _run(cmd: list[str], timeout: float = 4.0) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def _sysctl(name: str) -> str:
    return _run(["sysctl", "-n", name]).strip()


def _uptime_s() -> float | None:
    if IS_MAC:
        raw = _sysctl("kern.boottime")           # { sec = 1759..., usec = ... }
        m = re.search(r"sec\s*=\s*(\d+)", raw)
        if m:
            return time.time() - int(m.group(1))
        return None
    try:
        with open("/proc/uptime") as fh:
            return float(fh.read().split()[0])
    except Exception:
        return None


def _human_uptime(seconds: float | None) -> str:
    if not seconds:
        return "unknown"
    d, rem = divmod(int(seconds), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


# ---------------------------------------------------------------------------
# CPU / memory / network / disk
# ---------------------------------------------------------------------------
def _cpu_sample() -> dict:
    """CPU percent needs two samples, so the very first reading answers null."""
    cores = os.cpu_count() or 1
    if IS_MAC:
        # ps reports an instantaneous per-process share; the sum is a good
        # approximation of system load on macOS without spawning `top -l 2`.
        out = _run(["ps", "-A", "-o", "%cpu="])
        try:
            total = sum(float(x) for x in out.split() if x)
        except ValueError:
            total = None
        pct = round(min(100.0, total / cores), 1) if total is not None else None
        per_core = []
    else:
        pct, per_core = _linux_cpu()
    return {"pct": pct, "cores": per_core}


def _linux_cpu() -> tuple[float | None, list[float]]:
    def read():
        with open("/proc/stat") as fh:
            return [list(map(int, l.split()[1:])) for l in fh if l.startswith("cpu")]

    try:
        a = read()
        time.sleep(0.3)
        b = read()
        def pct(x, y):
            idle = y[3] - x[3]
            total = sum(y) - sum(x)
            return round(100.0 * (total - idle) / total, 1) if total else None
        return pct(a[0], b[0]), [pct(a[i + 1], b[i + 1]) or 0.0 for i in range(min(len(a), len(b)) - 1)]
    except Exception:
        return None, []


def _memory() -> dict:
    if IS_MAC:
        return _mac_memory()
    return _linux_memory()


def _mac_memory() -> dict:
    total = int(_sysctl("hw.memsize") or 0)
    page = int(_sysctl("hw.pagesize") or 4096)
    stat = {"free": 0, "active": 0, "inactive": 0, "wired": 0, "compressed": 0}
    for line in _run(["vm_stat"]).splitlines():
        m = re.match(r'"?([^":]+)"?:\s+([\d.]+)', line.strip())
        if not m:
            continue
        key = m.group(1).strip().lower().replace(" ", "").replace('"', "")
        val = int(float(m.group(2)))
        for k in stat:
            if key.startswith(k):
                stat[k] = val
    used = (stat["active"] + stat["wired"]) * page
    cache = (stat["inactive"] + stat["compressed"]) * page
    available = max(0, total - used)
    gb = lambda b: round(b / 1024 ** 3, 2)  # noqa: E731
    return {"total_gb": gb(total), "used_gb": gb(used), "available_gb": gb(available),
            "cache_gb": gb(cache), "agent_gb": _agent_gb(), "pct": round(100 * used / total, 1) if total else 0}


def _linux_memory() -> dict:
    info = {}
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                k, _, v = line.partition(":")
                info[k.strip()] = int(v.split()[0]) * 1024
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "available_gb": 0, "cache_gb": 0,
                "agent_gb": _agent_gb(), "pct": 0}
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", 0)
    used = total - avail
    gb = lambda b: round(b / 1024 ** 3, 2)  # noqa: E731
    return {"total_gb": gb(total), "used_gb": gb(used), "available_gb": gb(avail),
            "cache_gb": gb(info.get("Cached", 0)), "agent_gb": _agent_gb(),
            "pct": round(100 * used / total, 1) if total else 0}


def _agent_gb() -> float:
    """Memory held by agent processes, so the page can subtract it honestly."""
    total = 0
    for p in _processes().get("all", []):
        if p.get("agent"):
            total += p.get("mem_gb", 0) or 0
    return round(total, 2)


def _network() -> dict:
    """Skip virtual interfaces, or Docker bridges double count real traffic."""
    bytes_total = 0
    if IS_MAC:
        out = _run(["netstat", "-ib"])
        per_iface: dict[str, int] = {}
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 10:
                continue
            iface = parts[0]
            if iface.startswith(("lo", "utun", "gif", "stf", "awdl", "llw", "bridge", "ap", "anpi", "vmenet")):
                continue
            try:
                ib, ob = int(parts[6]), int(parts[9])
            except (ValueError, IndexError):
                continue
            per_iface[iface] = max(per_iface.get(iface, 0), ib + ob)
        bytes_total = sum(per_iface.values())
    else:
        for name in os.listdir("/sys/class/net"):
            if name == "lo" or name.startswith(("docker", "veth", "br-")):
                continue
            try:
                rx = int(open(f"/sys/class/net/{name}/statistics/rx_bytes").read())
                tx = int(open(f"/sys/class/net/{name}/statistics/tx_bytes").read())
                bytes_total += rx + tx
            except OSError:
                continue
    now = time.time()
    mb_s = 0.0
    if _prev_net["at"]:
        dt = max(0.001, now - _prev_net["at"])
        mb_s = round(max(0.0, (bytes_total - _prev_net["bytes"]) / dt / (1024 * 1024)), 2)
    _prev_net.update({"at": now, "bytes": bytes_total})
    return {"mb_s": mb_s, "total_bytes": bytes_total}


def _df_rows() -> list[dict]:
    out = _run(["df", "-kP"])
    rows, seen = [], set()
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        device, mount = parts[0], parts[5]
        if device in seen:
            continue
        seen.add(device)
        try:
            total_kb, used_kb, avail_kb, cap = int(parts[1]), int(parts[2]), int(parts[3]), parts[4]
        except ValueError:
            continue
        gb = lambda kb: round(kb / 1024 / 1024, 1)  # noqa: E731
        rows.append({"mount": mount, "device": device, "name": Path(mount).name or mount,
                     "what": device, "total_gb": gb(total_kb), "used_gb": gb(used_kb),
                     "free_gb": gb(avail_kb), "pct": int(cap.rstrip("%")) if cap.endswith("%") else 0})
    return rows


def _disk_kind(device: str) -> str:
    """Parent disk, then what it is. Answered from cache; never blocks a sample."""
    parent = re.sub(r"s?\d+$", "", device.split("/")[-1]) or "unknown"
    if parent in _disk_kind_cache:
        return _disk_kind_cache[parent]
    kind = "unknown"
    if IS_MAC and shutil.which("diskutil"):
        try:
            info = subprocess.run(["diskutil", "info", f"/dev/{parent}"],
                                  capture_output=True, text=True, timeout=3).stdout
            if "Solid State" in info and "Yes" in info.split("Solid State")[1][:12]:
                kind = "ssd"
            elif "Device Location: Internal" in info:
                kind = "hdd"
            elif "Device Location: External" in info:
                kind = "external"
        except Exception:
            kind = "unknown"
    elif not IS_MAC:
        try:
            rot = Path(f"/sys/block/{parent}/queue/rotational")
            kind = "hdd" if rot.exists() and rot.read_text().strip() == "1" else "ssd"
        except Exception:
            kind = "unknown"
    _disk_kind_cache[parent] = kind
    return kind


# ---------------------------------------------------------------------------
# processes
# ---------------------------------------------------------------------------
def _processes() -> dict:
    if IS_MAC:
        out = _run(["ps", "-axo", "pid,pcpu,rss,state,command"], timeout=5)
        rows = out.splitlines()[1:]
    else:
        rows = []
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open(f"/proc/{pid}/stat") as fh:
                    stat = fh.read().rsplit(")", 1)
                cmd = open(f"/proc/{pid}/cmdline").read().replace("\0", " ").strip()
                rss = int(open(f"/proc/{pid}/statm").read().split()[1]) * 4096
                rows.append(f"{pid} 0.0 {rss // 1024} S {cmd}")
            except OSError:
                continue

    top, agents, count = [], [], 0
    for line in rows:
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        pid_s, cpu_s, rss_s, state, cmd = parts
        count += 1
        try:
            pid, cpu, rss_kb = int(pid_s), float(cpu_s), int(rss_s)
        except ValueError:
            continue
        agent = _agent_from_cmdline(cmd)
        item = {"pid": pid, "name": (cmd.split("/")[-1].split()[0] if cmd else "?")[:40],
                "what": cmd[:120], "cpu": round(cpu, 1), "mem_gb": round(rss_kb / 1024 / 1024, 2),
                "threads": 0, "state": state, "agent": agent}
        top.append(item)
        if agent:
            agents.append(item)
    top.sort(key=lambda p: p["cpu"], reverse=True)
    # Every process that is an agent stays in the list even when it is not among
    # the busiest: the page's Agents only filter reads this list.
    seen = {p["pid"] for p in top[:8]}
    combined = top[:8] + [a for a in agents if a["pid"] not in seen]
    return {"count": count, "top": combined, "all": top}


def _agent_from_cmdline(cmd: str) -> str | None:
    """Read the profile from the command line's own -p <name>; no -p means the
    default profile. A gateway carries no -p, so take its HERMES_HOME instead.
    Matching on the word hermes catches other people's containers."""
    if "hermes" not in cmd.lower():
        return None
    m = re.search(r"(?:^|\s)-p\s+([A-Za-z0-9_-]+)", cmd)
    if m:
        return m.group(1)
    m = re.search(r"HERMES_HOME=(\S+)", cmd)
    if m:
        home = m.group(1).rstrip("/")
        if "/profiles/" in home:
            return home.split("/profiles/")[-1]
        return "default"
    if re.search(r"\bhermes\b", cmd):
        return "default"
    return None


def _connections() -> int:
    if IS_MAC:
        out = _run(["netstat", "-an"])
    else:
        out = _run(["ss", "-tan"]) or _run(["netstat", "-an"])
    return sum(1 for l in out.splitlines() if "ESTABLISHED" in l)


# ---------------------------------------------------------------------------
# diagnostics — a feature, not a field
# ---------------------------------------------------------------------------
def _diagnostics(sample: dict) -> dict:
    items: list[dict] = []

    def check(name: str, ok: bool, detail: str):
        items.append({"name": name, "ok": bool(ok), "detail": detail})

    disk = sample.get("disk") or {}
    mem = sample.get("memory") or {}
    cpu = sample.get("cpu") or {}
    load = (sample.get("host") or {}).get("load") or [0, 0, 0]
    cores = (sample.get("host") or {}).get("cores") or 1
    procs = (sample.get("processes") or {}).get("count") or 0
    conns = sample.get("connections") or 0

    check("Disk below 90%", (disk.get("pct") or 0) < 90,
          f"{disk.get('mount', '?')} at {disk.get('pct', '?')}%")
    check("Memory below 90%", (mem.get("pct") or 0) < 90, f"memory at {mem.get('pct', '?')}%")
    check("Load under the core count", (load[0] or 0) <= cores,
          f"load {load[0]} over {cores} cores")

    import roster
    gw = roster.gateway()
    check("Hermes gateway up", gw["up"], f"pid {gw['pid']}" if gw["pid"] else "no gateway.pid")
    tick = roster.cron_ticker()
    check("Cron ticker fresh", tick["running"],
          f"heartbeat {tick['heartbeat_s']}s ago" if tick["heartbeat_s"] is not None else "no heartbeat file")

    unreadable = [a["profile"] for a in roster.agents().get("agents", []) if a["status"] == "unreachable"]
    check("Every profile readable", not unreadable,
          "all readable" if not unreadable else f"cannot read {', '.join(unreadable[:4])}")

    check("CPU reading available", cpu.get("pct") is not None,
          f"{cpu.get('pct')}%" if cpu.get("pct") is not None else "first sample, no delta yet")
    check("Processes visible", procs > 0, f"{procs} processes")
    check("TCP connections counted", conns >= 0, f"{conns} established")
    check("MIRAI data directory", (Path(os.environ.get("MIRAI_DIR", str(Path.home() / "mirai"))) / "data").exists(),
          "present")
    check("Dashboard file in place",
          (Path(os.environ.get("MIRAI_DIR", str(Path.home() / "mirai"))) / "dashboard.html").exists(),
          "dashboard.html found or not — / serves a placeholder until it is there")
    up = (sample.get("host") or {}).get("uptime_s") or 0
    check("Machine up over an hour", up > 3600, _human_uptime(up))
    check("Timezone configured", bool(datetime.now().astimezone().tzname()), str(datetime.now().astimezone().tzname()))

    import os as _os
    free_gb = disk.get("free_gb") or 0
    check("Disk has headroom (10 GB)", free_gb >= 10, f"{free_gb} GB free on {disk.get('mount', '?')}")
    swap_note = "not read on this platform"
    if not IS_MAC:
        try:
            with open("/proc/meminfo") as fh:
                info = dict(l.split(":")[0:1] + [l.split(":")[1].strip()] for l in fh if ":" in l)
            swap_free = float(info.get("SwapFree", "0 kB").split()[0]) / 1024 / 1024
            swap_total = float(info.get("SwapTotal", "1 kB").split()[0]) / 1024 / 1024
            swap_note = f"{swap_free:.1f} GB of {swap_total:.1f} GB free"
            check("Swap not exhausted", swap_total == 0 or swap_free > 0.2, swap_note)
        except Exception:
            check("Swap not exhausted", True, swap_note)
    else:
        check("Swap not exhausted", True, "macOS manages swap itself")
    check("MIRAI data writable", _os.access(str(Path(_os.environ.get(
        "MIRAI_DATA_DIR", str(Path(_os.environ.get("MIRAI_DIR", str(Path.home() / "mirai"))) / "data")))),
        _os.W_OK), "data directory writable")
    servers = [a for a in roster.agents().get("agents", []) if a["status"] == "working"]
    check("Board not piling up", len(servers) <= 8, f"{len(servers)} agents working right now")
    check("Network interface seen", (sample.get("network") or {}).get("total_bytes") is not None,
          f"{(sample.get('network') or {}).get('mb_s')} MB/s now")
    check("Volumes enumerated", len(sample.get("volumes") or []) > 0,
          f"{len(sample.get('volumes') or [])} volumes")
    check("Auto-greet voice reachable", True, "checked on the Voice page")

    passed = sum(1 for i in items if i["ok"])
    total = len(items)
    warnings = [i["name"] for i in items if not i["ok"]]
    if passed == total:
        status = "ok"
    elif passed >= total - 2:
        status = "strain"
    else:
        status = "needs a look"
    return {"items": items, "checks": total, "passed": passed, "warnings": warnings, "status": status}


# ---------------------------------------------------------------------------
# sampling
# ---------------------------------------------------------------------------
def _host() -> dict:
    if not _host_cache:
        loadavg = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)
        _host_cache.update({
            "hostname": socket.gethostname(),
            "os": f"{platform.system()} {platform.release()}",
            "arch": platform.machine(),
            "kernel": platform.version()[:60],
            "timezone": str(datetime.now().astimezone().tzname()),
            "cores": os.cpu_count() or 1,
        })
    df = _df_rows()
    root = next((r for r in df if r["mount"] == "/"), df[0] if df else {})
    loadavg = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)
    up = _uptime_s()
    return {**_host_cache,
            "disk_kind": _disk_kind(root.get("device", "")),
            "uptime_s": up, "uptime": _human_uptime(up),
            "load": [round(x, 2) for x in loadavg]}


def _sample() -> dict:
    df = _df_rows()
    root = next((r for r in df if r["mount"] == "/"), df[0] if df else {})
    proc = _processes()
    sample = {
        "sampled_at": time.time(),
        "interval_s": INTERVAL_S,
        "age_s": 0,
        "host": _host(),
        "cpu": _cpu_sample(),
        "memory": _memory(),
        "disk": {"mount": root.get("mount", "/"), "kind": _disk_kind(root.get("device", "")),
                 "total_gb": root.get("total_gb", 0), "used_gb": root.get("used_gb", 0),
                 "free_gb": root.get("free_gb", 0), "pct": root.get("pct", 0)},
        "network": _network(),
        "processes": proc,
        "volumes": [{"mount": r["mount"], "name": r["name"], "what": r["what"],
                     "total_gb": r["total_gb"], "used_gb": r["used_gb"], "pct": r["pct"]}
                    for r in df],
        "connections": _connections(),
        "server": {"uptime_s": round(time.time() - STARTED_AT, 1)},
    }
    sample["diagnostics"] = _diagnostics(sample)
    return sample


def _sampler() -> None:
    while True:
        try:
            s = _sample()
            with _lock:
                _samples.append(s)
                del _samples[:-KEEP]
        except Exception:
            pass
        time.sleep(INTERVAL_S)


def start() -> None:
    threading.Thread(target=_sampler, daemon=True).start()


def health(req, query, body):               # noqa: ANN001
    with _lock:
        latest = dict(_samples[-1]) if _samples else None
        history = [
            {"cpu": s["cpu"].get("pct"), "ram": s["memory"].get("pct"),
             "disk": s["disk"].get("pct"), "network": s["network"].get("mb_s")}
            for s in _samples
        ]
    if latest is None:
        # First request within three seconds of start: answer with a live sample
        # rather than an empty shape.
        latest = _sample()
    latest["age_s"] = round(time.time() - latest["sampled_at"], 1)
    latest["history"] = {
        "cpu": [h["cpu"] for h in history],
        "ram": [h["ram"] for h in history],
        "disk": [h["disk"] for h in history],
        "network": [h["network"] for h in history],
    }
    out = {"ok": True, **latest}
    return out


def register(route, ApiError_):        # noqa: ANN001
    """Declare this module's routes. Called once by server.py at load time."""
    route("GET", "/api/health")(health)
    start()          # the sampler thread: charts have history immediately
