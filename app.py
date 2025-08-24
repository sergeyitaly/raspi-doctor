#!/usr/bin/env python3

import os
import threading
import sqlite3
import json
from flask import Flask, render_template, jsonify, send_from_directory,request
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import requests

from ollama_client import summarize_text
from enhanced_doctor import AutonomousDoctor, KnowledgeBase

# Initialize Flask app
app = Flask(__name__)

LOG_FILE = Path("/var/log/ai_health/health.log")
LOG_DIR = Path("/var/log/ai_health")
MODEL = os.getenv("OLLAMA_MODEL", "tinyllama")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")

# Global doctor instance
doctor = None
kb = None

def init_doctor():
    global doctor, kb
    try:
        kb = KnowledgeBase()
        kb.ensure_tables_exist()
        doctor = AutonomousDoctor(knowledge_base=kb)
        print("Doctor and knowledge database initialized successfully")
        return True
    except Exception as e:
        print(f"Failed to initialize doctor: {e}")
        return False

def run_doctor_async():
    """Run doctor in background thread"""
    def doctor_worker():
        try:
            if doctor:
                results = doctor.run_enhanced()
                print(f"Doctor run completed. Actions: {len(results)}")
        except Exception as e:
            print(f"Error in doctor worker: {e}")
    
    thread = threading.Thread(target=doctor_worker)
    thread.daemon = True
    thread.start()
    return thread

init_doctor()

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

@app.route("/api/run-doctor")
def api_run_doctor():
    """Trigger a doctor run manually"""
    try:
        thread = run_doctor_async()
        return jsonify({"status": "started", "thread": thread.name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/db-status")
def api_db_status():
    """Get database status"""
    try:
        if kb:
            # Create a simple debug output
            conn = sqlite3.connect(str(kb.db_path))
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            status = {}
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                status[table] = count
            
            conn.close()
            return jsonify(status)
        return jsonify({"error": "Knowledge base not initialized"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/metrics")
def api_metrics():
    """Get metrics data from database"""
    try:
        if not kb:
            return jsonify({"error": "Knowledge base not initialized"}), 500
        
        conn = sqlite3.connect(str(kb.db_path))
        cursor = conn.cursor()
        
        # Get available metric names
        cursor.execute("SELECT DISTINCT metric_name FROM long_term_metrics ORDER BY metric_name")
        metric_names = [row[0] for row in cursor.fetchall()]
        
        # Get latest values for each metric
        metrics_data = {}
        for metric_name in metric_names:
            cursor.execute('''
                SELECT metric_value, timestamp 
                FROM long_term_metrics 
                WHERE metric_name = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
            ''', (metric_name,))
            result = cursor.fetchone()
            if result:
                metrics_data[metric_name] = {
                    'value': result[0],
                    'timestamp': result[1]
                }
        
        # Get trend data for key metrics
        trends = {}
        key_metrics = ['cpu_percent', 'memory_percent', 'disk_percent', 'cpu_temperature']
        for metric in key_metrics:
            if metric in metric_names:
                cursor.execute('''
                    SELECT metric_value, timestamp 
                    FROM long_term_metrics 
                    WHERE metric_name = ? 
                    AND timestamp > datetime('now', '-24 hours')
                    ORDER BY timestamp
                ''', (metric,))
                results = cursor.fetchall()
                if results:
                    trends[metric] = {
                        'values': [r[0] for r in results],
                        'timestamps': [r[1] for r in results],
                        'current': results[-1][0] if results else None,
                        'average': sum(r[0] for r in results) / len(results) if results else None
                    }
        
        conn.close()
        
        return jsonify({
            'metrics': metrics_data,
            'trends': trends,
            'available_metrics': metric_names
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to fetch metrics: {str(e)}"}), 500

@app.route("/api/patterns")
def api_patterns():
    """Get learned patterns from database"""
    try:
        if not kb:
            return jsonify({"error": "Knowledge base not initialized"}), 500
        
        conn = sqlite3.connect(str(kb.db_path))
        cursor = conn.cursor()
        
        # Get patterns with occurrence count
        cursor.execute('''
            SELECT pattern_type, severity, confidence, solution, occurrence_count, last_seen
            FROM system_patterns 
            ORDER BY occurrence_count DESC, last_seen DESC
            LIMIT 20
        ''')
        
        patterns = []
        for row in cursor.fetchall():
            patterns.append({
                'type': row[0],
                'severity': row[1],
                'confidence': row[2],
                'solution': row[3],
                'occurrence_count': row[4],
                'last_seen': row[5]
            })
        
        conn.close()
        
        return jsonify({
            'patterns': patterns,
            'count': len(patterns)
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to fetch patterns: {str(e)}"}), 500

@app.route("/api/actions")
def api_actions():
    """Get action outcomes from database"""
    try:
        if not kb:
            return jsonify({"error": "Knowledge base not initialized"}), 500
        
        conn = sqlite3.connect(str(kb.db_path))
        cursor = conn.cursor()
        
        # Get recent actions
        cursor.execute('''
            SELECT action_type, target, reason, result, success, timestamp, improvement
            FROM action_outcomes 
            ORDER BY timestamp DESC
            LIMIT 50
        ''')
        
        actions = []
        for row in cursor.fetchall():
            actions.append({
                'action': row[0],
                'target': row[1],
                'reason': row[2],
                'result': row[3],
                'success': bool(row[4]),
                'timestamp': row[5],
                'improvement': row[6]
            })
        
        # Get success statistics
        cursor.execute('''
            SELECT action_type, 
                   COUNT(*) as total,
                   AVG(success) as success_rate,
                   AVG(improvement) as avg_improvement
            FROM action_outcomes 
            GROUP BY action_type
        ''')
        
        stats = {}
        for row in cursor.fetchall():
            stats[row[0]] = {
                'total': row[1],
                'success_rate': row[2],
                'avg_improvement': row[3]
            }
        
        conn.close()
        
        return jsonify({
            'recent_actions': actions,
            'statistics': stats
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to fetch actions: {str(e)}"}), 500
    
@app.route("/api/network")
def api_network():
    try:
        path = LOG_DIR / "network.log"
        if not path.exists():
            return jsonify({"summary": "No network log file found."})
        
        log_content = path.read_text()[-2000:]  # Reduced from 5000
        if not log_content.strip():
            return jsonify({"summary": "No recent network data available."})
            
        try:
            # Use the faster specialized analysis
            from ollama_client import analyze_network_logs
            summary = analyze_network_logs(log_content)
            return jsonify({"summary": summary})
        except Exception as e:
            return jsonify({"summary": f"Network analysis error: {e}"})
    except Exception as e:
        return jsonify({"summary": f"Network analysis failed: {e}"})

@app.route("/api/security")
def api_security():
    try:
        auth_log = ""
        ufw_log = ""
        
        # Read only recent entries
        if Path("/var/log/auth.log").exists():
            try:
                # Use tail command for efficiency
                auth_log = subprocess.run(
                    ["tail", "-n", "100", "/var/log/auth.log"],
                    capture_output=True, text=True, timeout=10
                ).stdout
            except:
                auth_log = ""
        
        if Path("/var/log/ufw.log").exists():
            try:
                ufw_log = subprocess.run(
                    ["tail", "-n", "50", "/var/log/ufw.log"],
                    capture_output=True, text=True, timeout=10
                ).stdout
            except:
                ufw_log = ""
            
        context = auth_log + "\n" + ufw_log
        if not context.strip():
            return jsonify({"report": "No recent security logs available."})
            
        try:
            # Use the faster specialized analysis
            from ollama_client import analyze_security_logs
            report = analyze_security_logs(context)
            return jsonify({"report": report})
        except Exception as e:
            return jsonify({"report": f"Security analysis error: {e}"})
    except Exception as e:
        return jsonify({"error": f"Security analysis failed: {str(e)}"}), 500

@app.route("/api/summary")
def api_summary():
    try:
        text = read_tail(LOG_FILE, max_bytes=60000)
        if not text.strip():
            return jsonify({"ok": False, "summary": "No logs found yet. Wait for the collector to run.", "ts": datetime.now().isoformat()})
        
        # Use the optimized summarize_text with timeout handling
        from ollama_client import summarize_text
        summary = summarize_text(text)
        return jsonify({"ok": True, "summary": summary, "ts": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({
            "ok": False, 
            "summary": f"Error generating summary: {str(e)}", 
            "ts": datetime.now().isoformat()
        }), 500


@app.route("/api/health")
def api_health():
    """Simple health check that doesn't depend on Ollama"""
    try:
        # Check if Ollama port is open (without making HTTP requests)
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', 11434))
        sock.close()
        
        ollama_status = "online" if result == 0 else "offline"
        
        return jsonify({
            "status": "ok",
            "ollama_port_open": ollama_status == "online",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500
    
@app.route("/api/hardware")
def api_hardware():
    path = LOG_DIR / "hardware.log"
    return jsonify({"report": path.read_text()[-5000:] if path.exists() else "No hardware logs."})

@app.route("/api/system-health")
def api_system_health():
    """Comprehensive system health endpoint combining logs and database metrics"""
    try:
        # Get current health data
        health_data = {}
        if doctor:
            health_data = doctor.collect_health_data()
            # Fix temperature if it's 0
            if health_data.get('cpu', {}).get('temperature') == 0:
                # Try to get temperature from alternative source
                temp = doctor.get_cpu_temperature()
                if temp > 0:
                    health_data['cpu']['temperature'] = temp
                    logger.info(f"Fixed CPU temperature: {temp}°C")
        else:
            health_data = {"error": "Doctor not initialized"}
        
        # Get database metrics
        metrics_response = api_metrics()
        metrics_data = metrics_response.get_json() if hasattr(metrics_response, 'get_json') else {}
        
        # Get patterns
        patterns_response = api_patterns()
        patterns_data = patterns_response.get_json() if hasattr(patterns_response, 'get_json') else {}
        
        # Get actions
        actions_response = api_actions()
        actions_data = actions_response.get_json() if hasattr(actions_response, 'get_json') else {}
        
        return jsonify({
            "current_health": health_data,
            "historical_metrics": metrics_data,
            "learned_patterns": patterns_data,
            "action_history": actions_data,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to get system health: {str(e)}"}), 500

@app.route("/api/ollama-status")
def api_ollama_status():
    """Check if Ollama server is running with better timeout handling"""
    try:
        # Use a very short timeout just to check basic connectivity
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
        
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                "status": "online",
                "models": data.get("models", []),
                "message": "Ollama server is responding"
            })
        else:
            return jsonify({
                "status": "error", 
                "message": f"Ollama API returned status {response.status_code}"
            })
            
    except requests.exceptions.ConnectionError:
        return jsonify({
            "status": "offline", 
            "message": "Cannot connect to Ollama server"
        })
    except requests.exceptions.Timeout:
        # Ollama is running but busy - this is normal on Raspberry Pi
        return jsonify({
            "status": "online",
            "message": "Ollama is running but busy processing requests",
            "models": [{"name": "tinyllama"}, {"name": "phi3:mini"}]  # Provide default models
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error checking Ollama status: {str(e)}"
        })
    
@app.route('/api/test-ollama', methods=['POST'])
def test_ollama():
    try:
        data = request.get_json()
        prompt = data.get('prompt', 'Hello, how are you')
        
        response = requests.post(
            f'{OLLAMA_HOST}/api/generate',
            json={
                "model": MODEL, 
                'prompt': prompt,
                'stream': False,
                'options': {
                    'num_predict': 8,
                    'num_thread': 1,
                    'temperature': 0.3,
                    'top_k': 20,
                    'top_p': 0.9,
                    'stop': ['\n'],
                    'repeat_penalty': 1.0
                }

            },
            timeout=8
        )
        
        if response.status_code == 200:
            result = response.json()
            # Check if response was cut off due to length
            if result.get('done_reason') == 'length':
                return jsonify({
                    'success': False, 
                    'error': 'Response was cut short. Try increasing num_predict or using a shorter prompt.',
                    'partial_response': result.get('response', '')
                })
            return jsonify({'success': True, 'response': result.get('response', 'No response')})
        else:
            return jsonify({
                'success': False, 
                'error': f'Ollama error: {response.status_code} - {response.text}'
            })
            
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False, 
            'error': 'Ollama request timed out. The Raspberry Pi is processing slowly. Try a shorter prompt.'
        })
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False, 
            'error': 'Cannot connect to Ollama server. Make sure Ollama is running.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
        
@app.route("/api/temperature")
def api_temperature():
    """Get CPU temperature with multiple fallback methods"""
    try:
        if not doctor:
            return jsonify({"error": "Doctor not initialized"}), 500
        
        # Try multiple methods to get temperature
        temperature = doctor.get_cpu_temperature()
        
        # If still 0, try direct system commands
        if temperature == 0:
            # Direct vcgencmd
            try:
                result = subprocess.run(["vcgencmd", "measure_temp"], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    temp_str = result.stdout.split("=")[1].split("'")[0]
                    temperature = float(temp_str)
            except:
                pass
        
        if temperature == 0:
            # Direct thermal zone reading
            try:
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temp_millic = float(f.read().strip())
                    temperature = temp_millic / 1000.0
            except:
                pass
        
        return jsonify({
            "temperature": temperature,
            "unit": "celsius",
            "timestamp": datetime.now().isoformat(),
            "source": "direct_measurement"
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to get temperature: {str(e)}"}), 500
    
@app.route("/api/debug/temperature")
def api_debug_temperature():
    """Debug endpoint to test all temperature reading methods"""
    methods = []
    
    # Method 1: vcgencmd
    try:
        result = subprocess.run(["vcgencmd", "measure_temp"], 
                              capture_output=True, text=True, timeout=5)
        methods.append({
            "method": "vcgencmd",
            "output": result.stdout,
            "success": result.returncode == 0,
            "temperature": float(result.stdout.split("=")[1].split("'")[0]) if result.returncode == 0 else None
        })
    except Exception as e:
        methods.append({"method": "vcgencmd", "error": str(e)})
    
    # Method 2: Thermal zone
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_millic = float(f.read().strip())
            methods.append({
                "method": "thermal_zone0",
                "temperature": temp_millic / 1000.0,
                "success": True
            })
    except Exception as e:
        methods.append({"method": "thermal_zone0", "error": str(e)})
    
    # Method 3: Check all thermal zones
    thermal_zones = []
    for zone in range(5):
        try:
            with open(f"/sys/class/thermal/thermal_zone{zone}/temp", "r") as f:
                temp_millic = float(f.read().strip())
                thermal_zones.append({
                    "zone": zone,
                    "temperature": temp_millic / 1000.0,
                    "success": True
                })
        except Exception as e:
            thermal_zones.append({"zone": zone, "error": str(e)})
    
    methods.append({"method": "all_thermal_zones", "zones": thermal_zones})
    
    # Method 4: sensors command
    try:
        result = subprocess.run(["sensors"], 
                              capture_output=True, text=True, timeout=5)
        methods.append({
            "method": "sensors",
            "output": result.stdout,
            "success": result.returncode == 0
        })
    except Exception as e:
        methods.append({"method": "sensors", "error": str(e)})
    
    return jsonify({"methods": methods})

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