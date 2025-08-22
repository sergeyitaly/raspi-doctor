#!/usr/bin/env python3
import subprocess, datetime, os

def run(cmd):
    try:
        return subprocess.getoutput(cmd)
    except Exception as e:
        return str(e)

def collect_health():
    timestamp = datetime.datetime.now().isoformat()
    sections = {
        "Uptime": run("uptime -p"),
        "CPU Temp": run("vcgencmd measure_temp"),
        "CPU Load": run("top -bn1 | head -n 5"),
        "Memory": run("free -h"),
        "Disk Usage": run("df -h"),
        "Disk Health": run("sudo smartctl -a /dev/mmcblk0 || echo 'No SMART support'"),
        "Failed Services": run("systemctl --failed"),
        "Errors (last 50)": run("journalctl -p err -n 50 --no-pager"),
        "Network": run("ping -c 3 8.8.8.8"),
    }

    report = [f"[{timestamp}] Raspberry Pi Health Report\n"]
    for key, value in sections.items():
        report.append(f"## {key}\n{value}\n")
    return "\n".join(report)

def main():
    logdir = "/var/log/ai_health"
    os.makedirs(logdir, exist_ok=True)
    logfile = os.path.join(logdir, "health.log")
    with open(logfile, "a") as f:
        f.write(collect_health())
        f.write("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()
