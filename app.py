#!/usr/bin/env python3
import os
import time
import json
import threading
from flask import Flask, render_template, jsonify, send_from_directory
from datetime import datetime
from pathlib import Path
import psutil
import subprocess

# Initialize Flask app
app = Flask(__name__)

LOG_FILE = Path("/var/log/ai_health/health.log")
LOG_DIR = Path("/var/log/ai_health")
CONFIG_FILE = Path("./config.yaml")

# Ensure log directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

class SystemMonitor:
    def __init__(self):
        self.health_data = {}
        self.last_update = datetime.now()
        self.update_interval = 2  # seconds
        self.running = True
        
    def collect_system_data(self):
        """Collect real-time system health data"""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=0.5)
            load_avg = psutil.getloadavg()
            mem = psutil.virtual_memory()
            
            # Disk
            disk = psutil.disk_usage("/")
            
            # Network
            net_io = psutil.net_io_counters()
            
            # Temperature (Raspberry Pi specific)
            cpu_temp = 0.0
            try:
                temp_output = subprocess.check_output(["vcgencmd", "measure_temp"], text=True)
                cpu_temp = float(temp_output.split("=")[1].split("'")[0])
            except Exception:
                pass
            
            # Uptime
            uptime_seconds = time.time() - psutil.boot_time()
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            uptime_str = f"{days}d {hours}h {minutes}m"
            
            # Processes
            processes = len(psutil.pids())
            
            # Network stats
            latency = self.measure_latency()
            packet_loss = self.measure_packet_loss()
            
            self.health_data = {
                'timestamp': datetime.now().isoformat(),
                'cpu': {
                    'percent': cpu_percent,
                    'temperature': cpu_temp,
                    'load_1min': load_avg[0],
                    'load_5min': load_avg[1],
                    'load_15min': load_avg[2],
                    'cores': psutil.cpu_count()
                },
                'memory': {
                    'total_gb': round(mem.total / (1024**3), 2),
                    'used_gb': round(mem.used / (1024**3), 2),
                    'percent': mem.percent,
                    'available_gb': round(mem.available / (1024**3), 2)
                },
                'disk': {
                    'total_gb': round(disk.total / (1024**3), 2),
                    'used_gb': round(disk.used / (1024**3), 2),
                    'free_gb': round(disk.free / (1024**3), 2),
                    'percent': disk.percent
                },
                'network': {
                    'latency_ms': latency,
                    'packet_loss_percent': packet_loss,
                    'sent_mb': round(net_io.bytes_sent / (1024**2), 2),
                    'received_mb': round(net_io.bytes_recv / (1024**2), 2)
                },
                'system': {
                    'uptime': uptime_str,
                    'processes': processes
                },
                'status': {
                    'overall': 'good',
                    'security': 'secure',
                    'network': 'stable'
                }
            }
            
            # Update status based on thresholds
            self.update_status()
            
            return self.health_data
            
        except Exception as e:
            print(f"Error collecting system data: {e}")
            return {'error': str(e)}
    
    def measure_latency(self):
        """Measure network latency to Google DNS"""
        try:
            result = subprocess.run(
                "ping -c 3 8.8.8.8 | tail -1 | awk '{print $4}' | cut -d'/' -f2",
                shell=True, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception:
            pass
        return 0.0
    
    def measure_packet_loss(self):
        """Measure packet loss"""
        try:
            result = subprocess.run(
                "ping -c 10 8.8.8.8 | grep 'packet loss' | awk '{print $6}' | tr -d '%'",
                shell=True, capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception:
            pass
        return 0.0
    
    def update_status(self):
        """Update system status based on current metrics"""
        # CPU temp
        temp = self.health_data['cpu']['temperature']
        if temp > 85:
            self.health_data['status']['overall'] = 'critical'
        elif temp > 75:
            self.health_data['status']['overall'] = 'warning'
        
        # Memory
        mem_use = self.health_data['memory']['percent']
        if mem_use > 95:
            self.health_data['status']['overall'] = 'critical'
        elif mem_use > 85:
            self.health_data['status']['overall'] = 'warning'
        
        # Disk
        disk_use = self.health_data['disk']['percent']
        if disk_use > 95:
            self.health_data['status']['overall'] = 'critical'
        elif disk_use > 85:
            self.health_data['status']['overall'] = 'warning'
        
        # Network
        packet_loss = self.health_data['network']['packet_loss_percent']
        if packet_loss > 20:
            self.health_data['status']['network'] = 'poor'
        elif packet_loss > 5:
            self.health_data['status']['network'] = 'unstable'
        
        # Security
        try:
            failed_logins = subprocess.run(
                "grep 'Failed password' /var/log/auth.log | wc -l",
                shell=True, capture_output=True, text=True
            )
            if failed_logins.returncode == 0 and failed_logins.stdout.strip().isdigit():
                if int(failed_logins.stdout.strip()) > 10:
                    self.health_data['status']['security'] = 'warning'
        except Exception:
            pass
    
    def start_monitoring(self):
        """Start background monitoring thread"""
        def monitor_loop():
            while self.running:
                self.collect_system_data()
                time.sleep(self.update_interval)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self.running = False

# Create global monitor instance
monitor = SystemMonitor()
monitor.start_monitoring()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/health")
def api_health():
    """Return current system health data"""
    return jsonify(monitor.health_data)

@app.route("/api/health/history")
def api_health_history():
    """Return health data history"""
    history = []
    try:
        if LOG_FILE.exists():
            with open(LOG_FILE, 'r') as f:
                for line in f.readlines()[-100:]:
                    if line.strip() and "Health Data:" in line:
                        try:
                            data = json.loads(line.split("Health Data: ")[1])
                            history.append(data)
                        except Exception:
                            continue
    except Exception as e:
        print(f"Error reading health history: {e}")
    
    return jsonify(history)

@app.route("/api/actions")
def api_actions():
    """Return recent actions taken by the system"""
    actions = []
    try:
        actions_file = LOG_DIR / "actions.log"
        if actions_file.exists():
            with open(actions_file, 'r') as f:
                actions = f.readlines()[-20:]
    except Exception as e:
        print(f"Error reading actions: {e}")
    
    return jsonify({"actions": actions})

@app.route("/api/security")
def api_security():
    """Return security status"""
    security_info = {
        "firewall": "active",
        "failed_logins": 0,
        "suspicious_ips": [],
        "status": "secure"
    }
    
    try:
        # Failed logins count
        result = subprocess.run(
            "grep 'Failed password' /var/log/auth.log | wc -l",
            shell=True, capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip().isdigit():
            security_info["failed_logins"] = int(result.stdout.strip())
        
        # Top suspicious IPs
        result = subprocess.run(
            "grep 'Failed password' /var/log/auth.log | awk '{print $(NF-3)}' | sort | uniq -c | sort -nr | head -5",
            shell=True, capture_output=True, text=True
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    count, ip = parts[0], parts[1]
                    if count.isdigit():
                        security_info["suspicious_ips"].append({"ip": ip, "attempts": int(count)})
        
        # Status update
        if security_info["failed_logins"] > 100:
            security_info["status"] = "critical"
        elif security_info["failed_logins"] > 50:
            security_info["status"] = "warning"
            
    except Exception as e:
        print(f"Error checking security: {e}")
    
    return jsonify(security_info)

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory('static', filename)

if __name__ == "__main__":
    # Only run Flask app (monitor already started)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8010")), debug=True)
