#!/usr/bin/env python3
import json
import subprocess
import datetime
from pathlib import Path
from ollama_client import summarize_text

# Paths to logs
LOG_DIR = Path("/var/log/ai_health")
ACTIONS_LOG = LOG_DIR / "actions.log"

# Whitelisted safe actions
SAFE_ACTIONS = {
    "restart_service": lambda target: subprocess.run(["systemctl", "restart", target], capture_output=True, text=True).stdout,
    "clear_cache": lambda _: subprocess.run(["sh", "-c", "echo 3 > /proc/sys/vm/drop_caches"], capture_output=True, text=True).stdout,
    "reboot": lambda _: subprocess.run(["reboot"], capture_output=True, text=True).stdout,
    "update_system": lambda _: subprocess.run(["apt-get", "update", "-y"], capture_output=True, text=True).stdout,
    "upgrade_system": lambda _: subprocess.run(["apt-get", "upgrade", "-y"], capture_output=True, text=True).stdout,
    "ban_ip": lambda ip: subprocess.run(["ufw", "deny", "from", ip], capture_output=True, text=True).stdout,
}

def log_action(msg):
    ts = datetime.datetime.now().isoformat()
    with open(ACTIONS_LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")

def get_recent_logs():
    """Concatenate recent logs for Ollama context"""
    logs = []
    for log_file in ["network.log", "security.log", "hardware.log"]:
        path = LOG_DIR / log_file
        if path.exists():
            logs.append(path.read_text()[-5000:])  # last 5000 chars
    return "\n".join(logs)

def ask_ollama_for_action(context_text):
    """Send recent logs to Ollama and ask for suggested action"""
    prompt = """You are a Raspberry Pi AI Doctor.
Analyze the logs below and suggest ONE safe action in JSON format:
{"action":"restart_service","target":"ssh","reason":"service inactive"}
{"action":"clear_cache","reason":"high memory usage"}
{"action":"update_system","reason":"security patches available"}
{"action":"ban_ip","target":"185.123.45.67","reason":"failed SSH attempts"}
{"action":"none","reason":"system healthy"}
Respond only in JSON."""
    
    response = summarize_text(context_text, prompt)
    try:
        return json.loads(response)
    except Exception:
        return {"action": "none", "reason": "failed to parse Ollama response"}

def main():
    context = get_recent_logs()
    action = ask_ollama_for_action(context)
    act = action.get("action")
    target = action.get("target", "")
    reason = action.get("reason", "No reason given")

    if act in SAFE_ACTIONS:
        try:
            output = SAFE_ACTIONS[act](target)
            log_action(f"Executed {act}({target}) - Reason: {reason} - Output: {output}")
        except Exception as e:
            log_action(f"Failed {act}({target}) - Error: {e}")
    else:
        log_action(f"No action taken - Reason: {reason}")

if __name__ == "__main__":
    main()
