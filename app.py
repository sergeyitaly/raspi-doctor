#!/usr/bin/env python3

import os
from flask import Flask, render_template, jsonify, send_from_directory
from datetime import datetime
from pathlib import Path

from ollama_client import summarize_text

# Initialize Flask app
app = Flask(__name__)

LOG_FILE = Path("/var/log/ai_health/health.log")
LOG_DIR = Path("/var/log/ai_health")

# Add static file route
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

def read_tail(path: Path, max_bytes=120000):
    if not path.exists():
        return ""
    size = path.stat().st_size
    with open(path, "rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
        data = f.read()
    try:
        return data.decode("utf-8", errors="replace")
    except:
        return data.decode("latin1", errors="replace")

def parse_network_log():
    path = LOG_DIR / "network.log"
    if not path.exists():
        return []
    data = []
    for line in path.read_text().splitlines():
        if not line.strip() or " - " not in line:
            continue
        try:
            dt_str, status, *_ = line.split(" - ", 2)
            dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            data.append({"time": dt.isoformat(), "status": status})
        except Exception:
            continue
    return data

def parse_hardware_log():
    path = LOG_DIR / "hardware.log"
    if not path.exists():
        return []
    data = []
    lines = path.read_text().splitlines()
    temp, mem = None, None
    for line in lines:
        try:
            if "CPU Temp:" in line:
                temp = float(line.split(":")[1].strip().replace("°C", ""))
            if "Memory:" in line:
                parts = line.split(":")[1].strip().split("MB used / ")
                if len(parts) == 2:
                    mem_used, mem_total = parts
                    mem = float(mem_used.strip())
            if temp is not None and mem is not None:
                data.append({"time": datetime.now().isoformat(), "cpu": temp, "mem": mem})
                temp, mem = None, None
        except Exception:
            continue
    return data

def parse_actions_log():
    path = LOG_DIR / "actions.log"
    if not path.exists():
        return []
    data = []
    for line in path.read_text().splitlines():
        if not line.strip() or "] " not in line:
            continue
        try:
            ts_str, action = line.split("] ", 1)
            ts = ts_str.strip("[]")
            data.append({"time": ts, "action": action})
        except Exception:
            continue
    return data

@app.route("/api/v2/network")
def api_v2_network():
    return jsonify(parse_network_log())

@app.route("/api/v2/hardware")
def api_v2_hardware():
    return jsonify(parse_hardware_log())

@app.route("/api/v2/actions")
def api_v2_actions():
    return jsonify(parse_actions_log())

@app.route("/api/summary")
def api_summary():
    text = read_tail(LOG_FILE, max_bytes=120000)
    if not text.strip():
        return jsonify({"ok": False, "summary": "No logs found yet. Wait for the collector to run.", "ts": datetime.now().isoformat()})
    try:
        summary = summarize_text(text)
        return jsonify({"ok": True, "summary": summary, "ts": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"ok": False, "summary": f"Error querying Ollama: {e}", "ts": datetime.now().isoformat()}), 500

@app.route("/api/actions")
def api_actions():
    path = LOG_DIR / "actions.log"
    if not path.exists():
        return jsonify({"log": "No actions yet."})
    return jsonify({"log": path.read_text()[-5000:]})

@app.route("/api/network")
def api_network():
    path = LOG_DIR / "network.log"
    if not path.exists():
        return jsonify({"summary": "No network log."})
    summary = summarize_text(path.read_text()[-5000:], "Summarize Raspberry Pi network stability in last 24h.")
    return jsonify({"summary": summary})

@app.route("/api/security")
def api_security():
    auth_log = Path("/var/log/auth.log").read_text()[-5000:] if Path("/var/log/auth.log").exists() else ""
    ufw_log = Path("/var/log/ufw.log").read_text()[-5000:] if Path("/var/log/ufw.log").exists() else ""
    context = auth_log + "\n" + ufw_log
    report = summarize_text(context, "Summarize suspicious security events: failed logins, attacks, blocked IPs.")
    return jsonify({"report": report})

@app.route("/api/hardware")
def api_hardware():
    path = LOG_DIR / "hardware.log"
    return jsonify({"report": path.read_text()[-5000:] if path.exists() else "No hardware logs."})

@app.route('/debug/template')
def debug_template():
    template_path = Path('templates/index.html')
    if not template_path.exists():
        return "Template does not exist!", 404
    
    content = template_path.read_text()
    # Check if the template has correct static references
    has_correct_css = 'url_for(\'static\', filename=\'style.css\')' in content
    has_correct_js = 'url_for(\'static\', filename=\'main.js\')' in content
    
    return jsonify({
        'template_exists': True,
        'has_correct_css_reference': has_correct_css,
        'has_correct_js_reference': has_correct_js
    })

@app.route("/")
def index():
    latest = read_tail(LOG_FILE, max_bytes=60000)
    return render_template("index.html", latest=latest)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8010")))