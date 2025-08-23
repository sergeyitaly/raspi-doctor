#!/usr/bin/env python3

import os
import threading
import sqlite3
import json
from flask import Flask, render_template, jsonify, send_from_directory
from datetime import datetime, timedelta
from pathlib import Path

from ollama_client import summarize_text
from enhanced_doctor import AutonomousDoctor, KnowledgeBase

# Initialize Flask app
app = Flask(__name__)

LOG_FILE = Path("/var/log/ai_health/health.log")
LOG_DIR = Path("/var/log/ai_health")

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

@app.route("/api/system-health")
def api_system_health():
    """Comprehensive system health endpoint combining logs and database metrics"""
    try:
        # Get current health data
        if doctor:
            health_data = doctor.collect_health_data()
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