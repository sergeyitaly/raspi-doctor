#!/usr/bin/env python3
import subprocess, datetime, os, json, psutil, shutil

LOG_DIR = "/var/log/ai_health"
LOG_FILE = os.path.join(LOG_DIR, "health.log")

def run(cmd):
    try:
        return subprocess.getoutput(cmd)
    except Exception as e:
        return f"ERROR running {cmd}: {e}"

def exists(cmd):
    return shutil.which(cmd) is not None

def collect_snapshot():
    ts = datetime.datetime.now().isoformat()

    # Basics (psutil gives stable numbers quickly)
    cpu_percent = psutil.cpu_percent(interval=1)
    load1, load5, load15 = psutil.getloadavg()
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/")

    # Pi temp (vcgencmd)
    temp = run("vcgencmd measure_temp") if exists("vcgencmd") else "vcgencmd not found"

    # SMART for SD/drive (may not be supported on some SD cards)
    smart = run("sudo smartctl -a /dev/mmcblk0")  # SD card device on Pi
    if "open device: /dev/mmcblk0 failed" in smart.lower():
        # Try first USB drive as fallback (optional)
        smart = run("lsblk -ndo NAME,TYPE | awk '$2==\"disk\"{print \"/dev/\"$1; exit}' | xargs -r sudo smartctl -a")

    # Journal (recent errors)
    journal_err = run("journalctl -p err -n 100 --no-pager")

    # Failed services
    failed_services = run("systemctl --failed")

    # Disk usage and mounts
    df = run("df -h")

    # Thermal / throttling hints
    dmesg_therm = run("dmesg | grep -i -E 'thermal|throttle' | tail -n 50")

    # Network quick check
    ping = run("ping -c 3 8.8.8.8")

    data = {
        "timestamp": ts,
        "cpu_percent": cpu_percent,
        "load": [load1, load5, load15],
        "memory": {
            "total": mem.total, "available": mem.available,
            "percent": mem.percent, "used": mem.used, "free": mem.free,
        },
        "swap": {"total": swap.total, "used": swap.used, "free": swap.free, "percent": swap.percent},
        "disk_root": {"total": disk.total, "used": disk.used, "free": disk.free, "percent": disk.percent},
        "temp": temp,
        "smart": smart,
        "failed_services": failed_services,
        "journal_err_tail": journal_err,
        "df": df,
        "dmesg_thermal": dmesg_therm,
        "ping": ping,
    }

    # Also write a human-readable block to .log for LLM context
    blocks = [
        f"[{ts}] Raspberry Pi Health Snapshot",
        f"CPU: {cpu_percent}% | Load: {load1:.2f} {load5:.2f} {load15:.2f}",
        f"Memory: {mem.percent}% used ({mem.used//(1024**2)} MiB / {mem.total//(1024**2)} MiB)",
        f"Swap: {swap.percent}% used ({swap.used//(1024**2)} MiB / {swap.total//(1024**2)} MiB)",
        f"Disk /: {disk.percent}% used ({disk.used//(1024**3)} GiB / {disk.total//(1024**3)} GiB)",
        f"CPU Temp: {temp}",
        "=== SMART ===",
        smart,
        "=== Failed Services ===",
        failed_services,
        "=== Disk Usage (df -h) ===",
        df,
        "=== Thermal/Throttle (dmesg) ===",
        dmesg_therm,
        "=== Journal Errors (last 100) ===",
        journal_err,
        "=== Network (ping 8.8.8.8) ===",
        ping,
        "=" * 80
    ]
    text = "\n".join(blocks)

    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(text + "\n")

    # Also keep a compact JSONL (optional but handy)
    with open(os.path.join(LOG_DIR, "health.jsonl"), "a") as jf:
        jf.write(json.dumps(data) + "\n")

    return data

if __name__ == "__main__":
    collect_snapshot()
