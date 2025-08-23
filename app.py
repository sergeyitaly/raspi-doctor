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

@app.route("/api/network")
def api_network():
    try:
        path = LOG_DIR / "network.log"
        if not path.exists():
            return jsonify({"summary": "No network log."})
        
        log_content = path.read_text()[-5000:]
        if not log_content.strip():
            return jsonify({"summary": "No network data available."})
            
        try:
            summary = summarize_text(log_content, "Summarize Raspberry Pi network stability in last 24h.")
            return jsonify({"summary": summary})
        except Exception as e:
            return jsonify({"summary": f"Ollama unavailable: {e}"})
    except Exception as e:
        return jsonify({"summary": f"Network analysis failed: {e}"})


@app.route("/api/security")
def api_security():
    try:
        auth_log = ""
        ufw_log = ""
        
        if Path("/var/log/auth.log").exists():
            auth_log = Path("/var/log/auth.log").read_text()[-5000:]
        
        if Path("/var/log/ufw.log").exists():
            ufw_log = Path("/var/log/ufw.log").read_text()[-5000:]
            
        context = auth_log + "\n" + ufw_log
        if not context.strip():
            return jsonify({"report": "No security logs available."})
            
        report = summarize_text(context, "Summarize suspicious security events: failed logins, attacks, blocked IPs.")
        return jsonify({"report": report})
    except Exception as e:
        return jsonify({"error": f"Security analysis failed: {str(e)}"}), 500

@app.route("/api/summary")
def api_summary():
    try:
        text = read_tail(LOG_FILE, max_bytes=120000)
        if not text.strip():
            return jsonify({"ok": False, "summary": "No logs found yet. Wait for the collector to run.", "ts": datetime.now().isoformat()})
        
        summary = summarize_text(text)
        return jsonify({"ok": True, "summary": summary, "ts": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"ok": False, "summary": f"Error querying Ollama: {e}", "ts": datetime.now().isoformat()}), 500

@app.route("/api/hardware")
def api_hardware():
    path = LOG_DIR / "hardware.log"
    return jsonify({"report": path.read_text()[-5000:] if path.exists() else "No hardware logs."})

# Static files route
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# Main route - should be LAST to avoid catching API routes
@app.route("/")
def index():
    latest = read_tail(LOG_FILE, max_bytes=60000)
    return render_template("index.html", latest=latest)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8010")))