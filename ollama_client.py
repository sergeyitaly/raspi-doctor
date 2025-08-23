# ollama_client.py
import os
import requests
import textwrap
import json
import sqlite3
from datetime import datetime, timedelta

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")
KNOWLEDGE_DB = "/var/log/ai_health/knowledge.db"

def get_system_patterns_from_db(hours=72):
    """Retrieve system patterns from the knowledge database"""
    patterns = []
    try:
        conn = sqlite3.connect(KNOWLEDGE_DB)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor.execute('''
        SELECT pattern_type, pattern_data, severity, confidence, solution, occurrence_count
        FROM system_patterns 
        WHERE last_seen > ? AND occurrence_count > 2
        ORDER BY severity DESC, occurrence_count DESC
        LIMIT 20
        ''', (cutoff,))
        
        for row in cursor.fetchall():
            pattern_type, pattern_data_blob, severity, confidence, solution, count = row
            try:
                # For now, just store the raw data since we can't unpickle here
                patterns.append({
                    'type': pattern_type,
                    'data_size': len(pattern_data_blob) if pattern_data_blob else 0,
                    'severity': severity,
                    'confidence': confidence,
                    'solution': solution,
                    'occurrence_count': count
                })
            except Exception as e:
                print(f"Error processing pattern data: {e}")
                continue
                
        conn.close()
    except Exception as e:
        print(f"Error reading patterns from DB: {e}")
    
    return patterns

def get_recent_action_outcomes(hours=24):
    """Retrieve recent action outcomes for context"""
    outcomes = []
    try:
        conn = sqlite3.connect(KNOWLEDGE_DB)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor.execute('''
        SELECT action_type, target, reason, result, success, improvement
        FROM action_outcomes 
        WHERE timestamp > ?
        ORDER BY timestamp DESC
        LIMIT 15
        ''', (cutoff,))
        
        for row in cursor.fetchall():
            action_type, target, reason, result, success, improvement = row
            outcomes.append({
                'action': action_type,
                'target': target,
                'reason': reason,
                'result': result,
                'success': bool(success),
                'improvement': improvement
            })
                
        conn.close()
    except Exception as e:
        print(f"Error reading action outcomes: {e}")
    
    return outcomes

def get_metric_trends(metric_names=None, hours=72):
    """Get trend data for key metrics"""
    trends = {}
    if metric_names is None:
        metric_names = ['cpu_percent', 'memory_percent', 'disk_percent', 'cpu_temperature']
    
    try:
        conn = sqlite3.connect(KNOWLEDGE_DB)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        for metric in metric_names:
            cursor.execute('''
            SELECT metric_value, timestamp 
            FROM long_term_metrics 
            WHERE metric_name = ? AND timestamp > ?
            ORDER BY timestamp
            ''', (metric, cutoff))
            
            results = cursor.fetchall()
            if results and len(results) > 1:
                values = [r[0] for r in results]
                trends[metric] = {
                    'current': values[-1] if values else None,
                    'average': sum(values) / len(values) if values else None,
                    'min': min(values) if values else None,
                    'max': max(values) if values else None,
                    'trend': 'increasing' if values[-1] > values[0] else 'decreasing' if values[-1] < values[0] else 'stable',
                    'data_points': len(values)
                }
            elif results:
                # Only one data point
                trends[metric] = {
                    'current': results[0][0],
                    'average': results[0][0],
                    'min': results[0][0],
                    'max': results[0][0],
                    'trend': 'stable',
                    'data_points': 1
                }
                
        conn.close()
    except Exception as e:
        print(f"Error reading metric trends: {e}")
    
    return trends

def summarize_text(text: str, prompt: str = None, max_chars=6000):
    """Enhanced summarization with historical context from knowledge base"""
    
    # Get historical context from knowledge base
    patterns = get_system_patterns_from_db()
    outcomes = get_recent_action_outcomes()
    trends = get_metric_trends()
    
    # Truncate input text
    text = text[-max_chars:] if len(text) > max_chars else text
    
    if not prompt:
        prompt = textwrap.dedent("""
        You are a Raspberry Pi health analyst with access to historical system data. 
        Analyze the current system state along with historical patterns and trends.

        Historical Context Available:
        - System patterns and recurring issues
        - Recent action outcomes and their effectiveness  
        - Long-term metric trends

        Produce a comprehensive health report with sections:
        
        1. Status Summary (current state overview)
        2. Historical Patterns (recurring issues from knowledge base)
        3. Immediate Alerts (critical issues needing attention)
        4. Performance Analysis (CPU, Memory, Disk, Temp with trends)
        5. Service Health (with learned service patterns)
        6. Storage/SD Card Health Assessment
        7. Network and Security Status
        8. Recommended Actions (prioritized, informed by historical success rates)

        Consider historical patterns when making recommendations. If a solution has 
        worked well in the past, prioritize it. If patterns show recurring issues,
        suggest deeper investigation.

        Be specific and data-driven. Reference historical patterns when applicable.
        """).strip()

    # Build enhanced context with historical data
    historical_context = f"""
    === HISTORICAL PATTERNS ===
    {json.dumps(patterns, indent=2, default=str)}
    
    === RECENT ACTION OUTCOMES ===
    {json.dumps(outcomes, indent=2, default=str)}
    
    === METRIC TRENDS ===
    {json.dumps(trends, indent=2, default=str)}
    
    === CURRENT SYSTEM STATE ===
    {text}
    """

    full_prompt = f"{prompt}\n\n--- ENHANCED CONTEXT ---\n{historical_context}\n--- CONTEXT END ---"
    
    try:
        url = f"{OLLAMA_HOST}/api/generate"
        payload = {
            "model": MODEL, 
            "prompt": full_prompt, 
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 500
            }
        }
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except Exception as e:
        return f"Error consulting AI: {str(e)}"

def analyze_network_logs(log_content: str, max_chars=2000):
    """Fast network analysis with reduced context"""
    log_content = log_content[-max_chars:] if len(log_content) > max_chars else log_content
    
    prompt = textwrap.dedent("""
    Analyze these network logs briefly. Focus on:
    - Connection stability issues
    - High latency or packet loss
    - Security concerns
    - 2-3 key recommendations
    
    Respond with 1-2 paragraphs maximum.
    """)
    
    try:
        url = f"{OLLAMA_HOST}/api/generate"
        payload = {
            "model": MODEL, 
            "prompt": f"{prompt}\n\n--- NETWORK LOGS ---\n{log_content}",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 300  # Very short response
            }
        }
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except Exception as e:
        return f"Network analysis unavailable: {str(e)}"

def analyze_security_logs(log_content: str, max_chars=2000):
    """Fast security analysis with reduced context"""
    log_content = log_content[-max_chars:] if len(log_content) > max_chars else log_content
    
    prompt = textwrap.dedent("""
    Analyze these security logs briefly. Focus on:
    - Failed login attempts
    - Suspicious IP addresses
    - Firewall/UFW events
    - Critical security recommendations
    
    Respond with 1-2 paragraphs maximum.
    """)
    
    try:
        url = f"{OLLAMA_HOST}/api/generate"
        payload = {
            "model": MODEL, 
            "prompt": f"{prompt}\n\n--- SECURITY LOGS ---\n{log_content}",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 300
            }
        }
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except Exception as e:
        return f"Security analysis unavailable: {str(e)}"
    

def consult_ai_for_service_issue(service_name: str, logs: str, service_status: str):
    """Consult AI for service troubleshooting with historical context"""
    
    # Get historical patterns for this service type
    service_patterns = []
    try:
        conn = sqlite3.connect(KNOWLEDGE_DB)
        cursor = conn.cursor()
        cursor.execute('''
        SELECT pattern_data, solution, success_rate, occurrence_count
        FROM system_patterns 
        WHERE pattern_type LIKE '%service%' 
        ORDER BY occurrence_count DESC
        LIMIT 5
        ''')
        
        for row in cursor.fetchall():
            pattern_data_blob, solution, success_rate, count = row
            # Store basic info since we can't unpickle
            service_patterns.append({
                'solution': solution,
                'success_rate': success_rate,
                'occurrence_count': count
            })
                
        conn.close()
    except Exception as e:
        print(f"Error reading service patterns: {e}")
    
    prompt = textwrap.dedent(f"""
    Analyze this service failure:

    Service: {service_name}
    Status: {service_status}
    Logs: {logs[:1500]}
    
    Based on the symptoms, recommend the best course of action.
    
    Respond with JSON: {{
        "solution": "disable|stop|restart|reinstall|investigate|custom_command",
        "reason": "detailed explanation",
        "confidence": "high|medium|low",
        "recommended_command": "specific command to execute"
    }}
    """)
    
    try:
        url = f"{OLLAMA_HOST}/api/generate"
        payload = {
            "model": MODEL, 
            "prompt": prompt, 
            "stream": False,
            "options": {"temperature": 0.1}
        }
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        response_text = data.get("response", "").strip()
        
        # Try to extract JSON from response
        try:
            # Look for JSON in the response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback if no JSON found
                return {
                    "solution": "investigate",
                    "reason": "Could not parse AI response as JSON",
                    "confidence": "low",
                    "recommended_command": f"journalctl -u {service_name} --no-pager -n 50"
                }
        except json.JSONDecodeError:
            return {
                "solution": "investigate",
                "reason": "AI response format error",
                "confidence": "low",
                "recommended_command": f"journalctl -u {service_name} --no-pager -n 50"
            }
            
    except Exception as e:
        return {
            "solution": "investigate",
            "reason": f"AI consultation failed: {str(e)}",
            "confidence": "low",
            "recommended_command": f"systemctl status {service_name} --no-pager"
        }

def analyze_system_trends():
    """Generate comprehensive trend analysis using historical data"""
    
    trends = get_metric_trends(hours=168)  # 1 week of data
    patterns = get_system_patterns_from_db(hours=168)
    outcomes = get_recent_action_outcomes(hours=168)
    
    prompt = textwrap.dedent("""
    Analyze long-term system trends and patterns to identify:
    
    1. Recurring issues and their patterns
    2. Seasonal or time-based trends
    3. Effectiveness of previous actions
    4. Emerging problems before they become critical
    5. Optimization opportunities
    
    Provide a weekly trend report with:
    - Overall system health trend
    - Most common recurring issues
    - Most effective remediation actions
    - Predictions for upcoming issues
    - Long-term optimization recommendations
    """)
    
    context = f"""
    === WEEKLY TREND DATA ===
    Metrics: {json.dumps(trends, indent=2, default=str)}
    
    === RECURRING PATTERNS ===
    {json.dumps(patterns, indent=2, default=str)}
    
    === ACTION EFFECTIVENESS ===
    {json.dumps(outcomes, indent=2, default=str)}
    """
    
    full_prompt = f"{prompt}\n\n{context}"
    
    try:
        url = f"{OLLAMA_HOST}/api/generate"
        payload = {
            "model": MODEL, 
            "prompt": full_prompt, 
            "stream": False,
            "options": {"temperature": 0.2}
        }
        response = requests.post(url, json=payload, timeout=240)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except Exception as e:
        return f"Trend analysis failed: {str(e)}"

# Test function
def test_connection():
    """Test connection to Ollama and database"""
    try:
        # Test Ollama connection
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        ollama_ok = response.status_code == 200
        
        # Test database connection
        conn = sqlite3.connect(KNOWLEDGE_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        db_ok = 'system_patterns' in tables
        
        return {
            'ollama_connected': ollama_ok,
            'database_connected': db_ok,
            'available_tables': tables
        }
        
    except Exception as e:
        return {
            'ollama_connected': False,
            'database_connected': False,
            'error': str(e)
        }