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
            try:
                temp_output = subprocess.check_output(["vcgencmd", "measure_temp"], text=True)
                cpu_temp = float(temp_output.split("=")[1].split("'")[0])
            except:
                cpu_temp = 0.0
            
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
            if result.returncode == 0:
                return float(result.stdout.strip())
        except:
            pass
        return 0.0
    
    def measure_packet_loss(self):
        """Measure packet loss"""
        try:
            result = subprocess.run(
                "ping -c 10 8.8.8.8 | grep 'packet loss' | awk '{print $6}' | tr -d '%'",
                shell=True, capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
        except:
            pass
        return 0.0
    
    def update_status(self):
        """Update system status based on current metrics"""
        # Check CPU temperature
        if self.health_data['cpu']['temperature'] > 75:
            self.health_data['status']['overall'] = 'warning'
        elif self.health_data['cpu']['temperature'] > 85:
            self.health_data['status']['overall'] = 'critical'
        
        # Check memory usage
        if self.health_data['memory']['percent'] > 85:
            self.health_data['status']['overall'] = 'warning'
        elif self.health_data['memory']['percent'] > 95:
            self.health_data['status']['overall'] = 'critical'
        
        # Check disk usage
        if self.health_data['disk']['percent'] > 85:
            self.health_data['status']['overall'] = 'warning'
        elif self.health_data['disk']['percent'] > 95:
            self.health_data['status']['overall'] = 'critical'
        
        # Check network
        if self.health_data['network']['packet_loss_percent'] > 5:
            self.health_data['status']['network'] = 'unstable'
        elif self.health_data['network']['packet_loss_percent'] > 20:
            self.health_data['status']['network'] = 'poor'
        
        # Check security (simplified)
        try:
            failed_logins = subprocess.run(
                "grep 'Failed password' /var/log/auth.log | wc -l",
                shell=True, capture_output=True, text=True
            )
            if failed_logins.returncode == 0 and int(failed_logins.stdout.strip()) > 10:
                self.health_data['status']['security'] = 'warning'
        except:
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
                for line in f.readlines()[-100:]:  # Last 100 entries
                    if line.strip():
                        try:
                            data = json.loads(line.split("Health Data: ")[1])
                            history.append(data)
                        except:
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
                actions = f.readlines()[-20:]  # Last 20 actions
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
        # Check failed logins
        result = subprocess.run(
            "grep 'Failed password' /var/log/auth.log | wc -l",
            shell=True, capture_output=True, text=True
        )
        if result.returncode == 0:
            security_info["failed_logins"] = int(result.stdout.strip())
        
        # Check suspicious IPs
        result = subprocess.run(
            "grep 'Failed password' /var/log/auth.log | awk '{print $(NF-3)}' | sort | uniq -c | sort -nr | head -5",
            shell=True, capture_output=True, text=True
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.strip():
                    count, ip = line.strip().split()[:2]
                    security_info["suspicious_ips"].append({"ip": ip, "attempts": int(count)})
        
        # Update status based on findings
        if security_info["failed_logins"] > 50:
            security_info["status"] = "warning"
        elif security_info["failed_logins"] > 100:
            security_info["status"] = "critical"
            
    except Exception as e:
        print(f"Error checking security: {e}")
    
    return jsonify(security_info)

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory('static', filename)

if __name__ == "__main__":
    # Start the monitoring thread
    monitor.start_monitoring()
    
    # Run the Flask app
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8010")), debug=True)