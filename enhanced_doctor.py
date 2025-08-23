#!/home/pi/raspi-doctor/.venv/bin/python3
import subprocess
import datetime
import os
import json
import psutil
import shutil
import yaml
import requests
from pathlib import Path
import logging
from typing import Dict, List, Any, Optional
import sqlite3
import pickle
import hashlib
import numpy as np
from collections import deque
import statistics

# Configuration
CONFIG_FILE = Path("./config.yaml")
LOG_DIR = Path("/var/log/ai_health")
HEALTH_LOG = LOG_DIR / "health.log"
ACTIONS_LOG = LOG_DIR / "actions.log"
DECISIONS_LOG = LOG_DIR / "decisions.log"
KNOWLEDGE_DB = LOG_DIR / "knowledge.db"
PATTERNS_FILE = LOG_DIR / "patterns.pkl"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.getenv("OLLAMA_MODEL", "tinyllama")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "enhanced_doctor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("enhanced_doctor")

class KnowledgeBase:
    def __init__(self, db_path=KNOWLEDGE_DB):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initializing database at: {db_path}")
        logger.info(f"Database directory exists: {db_path.parent.exists()}")
        logger.info(f"Database file exists: {db_path.exists()}")
        
        # Ensure proper permissions
        try:
            if not db_path.exists():
                db_path.touch(mode=0o666)
                logger.info("Created new database file")
        except Exception as e:
            logger.error(f"Could not create database file: {e}")
            
        self.init_db()
        self.ensure_tables_exist()
        
    def init_db(self):
        """Initialize the knowledge database with error handling"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_hash TEXT UNIQUE,
                pattern_type TEXT,
                pattern_data BLOB,
                first_seen TIMESTAMP,
                last_seen TIMESTAMP,
                occurrence_count INTEGER,
                severity REAL,
                confidence REAL,
                solution TEXT,
                success_rate REAL
            )
            ''')
            # Action outcomes table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS action_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT,
                target TEXT,
                reason TEXT,
                result TEXT,
                success INTEGER,
                timestamp TIMESTAMP,
                system_state_hash TEXT,
                improvement REAL
            )
            ''')
            
            # Long-term metrics table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS long_term_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT,
                metric_value REAL,
                timestamp TIMESTAMP,
                context TEXT
            )
            ''')
            
            conn.commit()
            conn.close()
            logger.info(f"Database initialized successfully at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            try:
                conn = sqlite3.connect(self.db_path)
                conn.close()
                logger.info("Created basic database file, tables will be created on next access")
            except:
                logger.error("Could not create database file at all")
    
    def ensure_tables_exist(self):
        """Check if tables exist and create them if they don't"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [table[0] for table in cursor.fetchall()]
            conn.close()
            
            required_tables = ['system_patterns', 'action_outcomes', 'long_term_metrics']
            missing_tables = [table for table in required_tables if table not in tables]
            
            if missing_tables:
                logger.warning(f"Missing tables: {missing_tables}, reinitializing...")
                self.init_db()
                return False
            return True
            
        except Exception as e:
            logger.error(f"Error checking tables: {e}")
            return False

    def debug_database_status(self):
        """Debug method to check database status"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Check tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"Database tables: {tables}")
            
            # Check row counts
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                logger.info(f"Table {table} has {count} rows")
            
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Database debug failed: {e}")
            return False

    def store_pattern(self, pattern_type, pattern_data, severity=0.5, confidence=0.5, solution=""):
        """Store a pattern in the knowledge base"""
        if not self.ensure_tables_exist():
            return False
            
        try:
            pattern_hash = hashlib.md5(json.dumps(pattern_data, sort_keys=True).encode()).hexdigest()
            serialized_data = pickle.dumps(pattern_data)
            timestamp = datetime.datetime.now().isoformat()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if pattern already exists
            cursor.execute('SELECT occurrence_count FROM system_patterns WHERE pattern_hash = ?', (pattern_hash,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing pattern
                cursor.execute('''
                UPDATE system_patterns 
                SET last_seen = ?, occurrence_count = occurrence_count + 1 
                WHERE pattern_hash = ?
                ''', (timestamp, pattern_hash))
            else:
                # Insert new pattern
                cursor.execute('''
                INSERT INTO system_patterns 
                (pattern_hash, pattern_type, pattern_data, first_seen, last_seen, 
                occurrence_count, severity, confidence, solution, success_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (pattern_hash, pattern_type, serialized_data, timestamp, timestamp, 
                    1, severity, confidence, solution, 0.0))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error storing pattern: {e}")
            return False

    def store_metric(self, metric_name, metric_value, context=None):
        """Store a metric value for trend analysis"""
        if not self.ensure_tables_exist():
            logger.error("Cannot store metric - tables not available")
            return False
            
        try:
            conn = sqlite3.connect(str(self.db_path))  # Use string path
            cursor = conn.cursor()
            
            # Debug: Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='long_term_metrics'")
            table_exists = cursor.fetchone()
            if not table_exists:
                logger.error("long_term_metrics table doesn't exist!")
                conn.close()
                return False
                
            # Convert context to JSON string if it's a dict
            context_str = None
            if context is not None:
                if isinstance(context, dict):
                    context_str = json.dumps(context)
                else:
                    context_str = str(context)
            
            timestamp = datetime.datetime.now().isoformat()
            logger.debug(f"Storing metric: {metric_name}={metric_value} at {timestamp}")
            
            cursor.execute('''
            INSERT INTO long_term_metrics (metric_name, metric_value, timestamp, context)
            VALUES (?, ?, ?, ?)
            ''', (metric_name, float(metric_value), timestamp, context_str))
            
            conn.commit()
            conn.close()
            logger.info(f"Successfully stored metric: {metric_name}={metric_value}")
            return True
            
        except sqlite3.OperationalError as e:
            logger.error(f"SQLite operational error storing metric {metric_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error storing metric {metric_name}: {e}")
            return False
            
    def store_action_outcome(self, action_type, target, reason, result, success, system_state_hash, improvement=0.0):
        """Store the outcome of an action"""
        if not self.ensure_tables_exist():
            return False
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO action_outcomes 
            (action_type, target, reason, result, success, timestamp, system_state_hash, improvement)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (action_type, target, reason, result, 1 if success else 0, 
                datetime.datetime.now().isoformat(), system_state_hash, improvement))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error storing action outcome: {e}")
            return False

    def calculate_similarity(self, pattern1, pattern2):
        """Calculate similarity between two patterns (simple implementation)"""
        # This is a simple implementation - you might want to improve this
        if not isinstance(pattern1, dict) or not isinstance(pattern2, dict):
            return 0.0
        
        common_keys = set(pattern1.keys()) & set(pattern2.keys())
        if not common_keys:
            return 0.0
        
        similarity = 0.0
        for key in common_keys:
            if pattern1[key] == pattern2[key]:
                similarity += 1.0
            elif isinstance(pattern1[key], (int, float)) and isinstance(pattern2[key], (int, float)):
                # For numeric values, calculate relative similarity
                max_val = max(abs(pattern1[key]), abs(pattern2[key]))
                if max_val > 0:
                    similarity += 1.0 - (abs(pattern1[key] - pattern2[key]) / max_val)
        
        return similarity / len(common_keys)

    def get_similar_patterns(self, pattern_data, pattern_type=None, threshold=0.8):
        """Find similar patterns in the knowledge base"""
        if not self.ensure_tables_exist():
            logger.warning("Cannot get similar patterns - tables not available")
            return []
            
        try:
            pattern_hash = hashlib.md5(json.dumps(pattern_data, sort_keys=True).encode()).hexdigest()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if pattern_type:
                cursor.execute('''
                SELECT pattern_hash, pattern_data, severity, confidence, solution, success_rate
                FROM system_patterns 
                WHERE pattern_type = ? AND occurrence_count > 2
                ORDER BY last_seen DESC
                LIMIT 10
                ''', (pattern_type,))
            else:
                cursor.execute('''
                SELECT pattern_hash, pattern_data, severity, confidence, solution, success_rate
                FROM system_patterns 
                WHERE occurrence_count > 2
                ORDER BY last_seen DESC
                LIMIT 10
                ''')
            
            patterns = []
            for row in cursor.fetchall():
                try:
                    stored_data = pickle.loads(row[1])
                    similarity = self.calculate_similarity(pattern_data, stored_data)
                    if similarity >= threshold:
                        patterns.append({
                            'hash': row[0],
                            'data': stored_data,
                            'severity': row[2],
                            'confidence': row[3],
                            'solution': row[4],
                            'success_rate': row[5],
                            'similarity': similarity
                        })
                except:
                    continue
            
            conn.close()
            return sorted(patterns, key=lambda x: x['similarity'], reverse=True)
            
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                logger.warning("Tables missing, attempting to reinitialize...")
                self.init_db()
                return []
            else:
                logger.error(f"Database error: {e}")
                return []
        except Exception as e:
            logger.error(f"Error getting similar patterns: {e}")
            return []
    
    def get_action_success_rate(self, action_type, target=None):
        """Calculate the success rate of a specific action"""
        if not self.ensure_tables_exist():
            return {'count': 0, 'success_rate': 0.5, 'avg_improvement': 0.0}
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if target:
                cursor.execute('''
                SELECT COUNT(*), AVG(success), AVG(improvement) 
                FROM action_outcomes 
                WHERE action_type = ? AND target = ?
                ''', (action_type, target))
            else:
                cursor.execute('''
                SELECT COUNT(*), AVG(success), AVG(improvement) 
                FROM action_outcomes 
                WHERE action_type = ?
                ''', (action_type,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0] > 0:
                return {
                    'count': result[0],
                    'success_rate': result[1],
                    'avg_improvement': result[2]
                }
            return {'count': 0, 'success_rate': 0.5, 'avg_improvement': 0.0}
            
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                logger.warning("Tables missing")
                return {'count': 0, 'success_rate': 0.5, 'avg_improvement': 0.0}
            else:
                logger.error(f"Database error: {e}")
                return {'count': 0, 'success_rate': 0.5, 'avg_improvement': 0.0}
        except Exception as e:
            logger.error(f"Error getting action success rate: {e}")
            return {'count': 0, 'success_rate': 0.5, 'avg_improvement': 0.0}
    
    def get_metric_trend(self, metric_name, hours=24):
        """Get trend data for a specific metric"""
        if not self.ensure_tables_exist():
            return None
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff = datetime.datetime.now() - datetime.timedelta(hours=hours)
            cursor.execute('''
            SELECT metric_value, timestamp 
            FROM long_term_metrics 
            WHERE metric_name = ? AND timestamp > ?
            ORDER BY timestamp
            ''', (metric_name, cutoff))
            
            results = cursor.fetchall()
            conn.close()
            
            if len(results) < 2:
                return None
            
            values = [r[0] for r in results]
            timestamps = [r[1] for r in results]
            
            # Calculate simple linear trend
            x = np.arange(len(values))
            try:
                slope, intercept = np.polyfit(x, values, 1)
                trend = "increasing" if slope > 0.1 else "decreasing" if slope < -0.1 else "stable"
                
                return {
                    'values': values,
                    'timestamps': timestamps,
                    'trend': trend,
                    'slope': slope,
                    'current': values[-1],
                    'average': statistics.mean(values),
                    'min': min(values),
                    'max': max(values)
                }
            except:
                return None
                
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                logger.warning("Tables missing")
                return None
            else:
                logger.error(f"Database error: {e}")
                return None
        except Exception as e:
            logger.error(f"Error getting metric trend: {e}")
            return None

class ServiceTroubleshooter:
    def __init__(self, knowledge_base):
        self.kb = knowledge_base
        self.problematic_patterns = {
            'rng-tools': {
                'pattern': 'rng-tools',
                'reason': 'Hardware RNG not available on Raspberry Pi',
                'solution': 'disable_service',
                'alternative': 'install haveged for software entropy'
            },
            'avahi-daemon': {
                'pattern': 'avahi-daemon',
                'reason': 'Often conflicts on Raspberry Pi',
                'solution': 'stop_service',
                'alternative': 'keep disabled if not needed for networking'
            },
            'bluetooth': {
                'pattern': 'bluetooth',
                'reason': 'High resource usage, often unnecessary',
                'solution': 'stop_service',
                'alternative': 'enable only when needed'
            },
            'failed-to-start': {
                'pattern': 'Failed to start',
                'reason': 'Service startup failure',
                'solution': 'investigate_logs',
                'alternative': 'check dependencies and configuration'
            },
            'filesystem_recovery': {
                'pattern': 'recovery required on readonly filesystem',
                'reason': 'Filesystem was mounted read-only and required recovery',
                'solution': 'check_disk_health',
                'alternative': 'run filesystem check and monitor disk health'
            },
            'orphan_inodes': {
                'pattern': 'orphan cleanup on readonly fs',
                'reason': 'Filesystem had orphaned inodes indicating improper shutdown',
                'solution': 'check_power_issues',
                'alternative': 'ensure proper shutdown and check power supply'
            },
            'ext4_recovery': {
                'pattern': 'EXT4-fs.*recovery',
                'reason': 'EXT4 filesystem recovery performed during boot',
                'solution': 'investigate_disk',
                'alternative': 'check disk for errors and consider fsck'
            },
            'cloudflared_yaml_error': {
                'pattern': 'error parsing YAML in config file',
                'reason': 'Cloudflare Tunnel has invalid YAML configuration',
                'solution': 'fix_cloudflared_config',
                'alternative': 'Check and repair /home/pi/.cloudflared/config.yml'
            },
            'cloudflared_config_error': {
                'pattern': 'mapping values are not allowed in this context',
                'reason': 'YAML syntax error in Cloudflare config',
                'solution': 'validate_cloudflared_config',
                'alternative': 'Validate YAML syntax and indentation'
            }
        }
    

    def analyze_cloudflared_issue(self, service_name, service_status_output, service_logs):
        """Specialized analysis for Cloudflare Tunnel issues"""
        recommendations = []
        
        # Check for YAML configuration errors
        if 'error parsing YAML' in service_logs or 'mapping values are not allowed' in service_logs:
            recommendation = {
                'service': service_name,
                'issue': 'cloudflared_yaml_error',
                'reason': 'Invalid YAML configuration in Cloudflare Tunnel',
                'solution': 'fix_cloudflared_config',
                'alternative': 'Repair the config file syntax',
                'confidence': 'high',
                'source': 'cloudflared_specific'
            }
            recommendations.append(recommendation)
        
        return recommendations
    
    def execute_cloudflared_solution(self, recommendation, run_command_func):
        """Execute Cloudflare-specific solutions"""
        service = recommendation['service']
        solution = recommendation['solution']
        
        try:
            if solution == 'fix_cloudflared_config':
                result = "Attempting to fix Cloudflare config YAML issue"
                
                # First, backup the current config
                run_command_func("cp /home/pi/.cloudflared/config.yml /home/pi/.cloudflared/config.yml.backup")
                
                # Try to validate and fix the YAML
                validation = run_command_func("python3 -c \"import yaml; yaml.safe_load(open('/home/pi/.cloudflared/config.yml'))\" 2>&1")
                
                if "Error" in validation or "error" in validation:
                    # Create a simple default config
                    default_config = """tunnel: your-tunnel-id
credentials-file: /home/pi/.cloudflared/your-tunnel-id.json
"""
                    run_command_func(f"echo '{default_config}' > /home/pi/.cloudflared/config.yml.fixed")
                    result += " - Created fixed config template"
                
                return f"SUCCESS: {result}"
                
            elif solution == 'validate_cloudflared_config':
                result = "Validating Cloudflare config syntax"
                validation = run_command_func("python3 -c \"import yaml; yaml.safe_load(open('/home/pi/.cloudflared/config.yml'))\" 2>&1")
                
                if "Error" in validation or "error" in validation:
                    result += f" - Syntax errors found: {validation}"
                else:
                    result += " - Config syntax is valid"
                
                return f"SUCCESS: {result}"
                
            else:
                return f"ERROR: Unknown Cloudflare solution: {solution}"
                
        except Exception as e:
            return f"ERROR: Failed to execute Cloudflare solution: {e}"
        
    def analyze_journal_issues(self, journal_output):
        """Analyze journal output for system-wide issues (not just services)"""
        recommendations = []
        
        # Check against known patterns
        for issue_name, issue_data in self.problematic_patterns.items():
            if issue_data['pattern'].lower() in journal_output.lower():
                recommendation = {
                    'issue': issue_name,
                    'reason': issue_data['reason'],
                    'solution': issue_data['solution'],
                    'alternative': issue_data['alternative'],
                    'confidence': 'high',
                    'source': 'journal_analysis'
                }
                recommendations.append(recommendation)
        
        return recommendations
    
    def analyze_service_issue(self, service_name, service_status_output):
        """Analyze service issues and recommend solutions"""
        recommendations = []
        
        # Check against known patterns
        for issue_name, issue_data in self.problematic_patterns.items():
            if issue_data['pattern'].lower() in service_name.lower() or \
               issue_data['pattern'].lower() in service_status_output.lower():
                
                recommendation = {
                    'service': service_name,
                    'issue': issue_name,
                    'reason': issue_data['reason'],
                    'solution': issue_data['solution'],
                    'alternative': issue_data['alternative'],
                    'confidence': 'high' if issue_data['pattern'].lower() in service_name.lower() else 'medium',
                    'source': 'builtin_knowledge'
                }
                recommendations.append(recommendation)
        
        # Check knowledge base for similar patterns
        pattern_data = {
            'service': service_name,
            'status_output': service_status_output
        }
        similar_patterns = self.kb.get_similar_patterns(pattern_data, 'service_issue')
        
        for pattern in similar_patterns:
            if pattern['similarity'] > 0.7:  # Good match
                recommendation = {
                    'service': service_name,
                    'issue': 'learned_pattern',
                    'reason': f"Similar to previous issue (confidence: {pattern['confidence']:.2f})",
                    'solution': pattern['solution'],
                    'alternative': 'Apply learned solution',
                    'confidence': 'high' if pattern['confidence'] > 0.7 else 'medium',
                    'source': 'learned_knowledge',
                    'pattern_similarity': pattern['similarity']
                }
                recommendations.append(recommendation)
        
        return recommendations
    
    def execute_solution(self, recommendation, run_command_func):
        """Execute the recommended solution"""
        service = recommendation['service']
        solution = recommendation['solution']
        
        try:
            if solution == 'disable_service':
                result = f"Disabling problematic service {service}"
                run_command_func(f"sudo systemctl disable {service} --now")
                run_command_func(f"sudo systemctl mask {service}")
                
            elif solution == 'stop_service':
                result = f"Stopping non-essential service {service}"
                run_command_func(f"sudo systemctl stop {service}")
                
            elif solution == 'investigate_logs':
                result = f"Investigating {service} logs"
                logs = run_command_func(f"sudo journalctl -u {service} --no-pager -n 20")
                # Store pattern for future learning
                pattern_data = {
                    'service': service,
                    'action': 'investigate_logs',
                    'logs_sample': logs[:500]  # Store first 500 chars
                }
                self.kb.store_pattern('service_logs', pattern_data, severity=0.3)
                
            elif solution == 'reinstall_service':
                result = f"Reinstalling {service}"
                pkg_name = service.replace('.service', '')
                run_command_func(f"sudo apt install --reinstall {pkg_name}")
                
            else:
                result = f"No action taken for {service}"
                
            return f"SUCCESS: {result}"
            
        except Exception as e:
            return f"ERROR: Failed to execute solution for {service}: {e}"

class AutonomousDoctor:
    def __init__(self, knowledge_base=None):
        self.config = self.load_config()
        self.thresholds = self.config.get('thresholds', {})
        self.actions_enabled = self.config.get('actions', {})
        self.health_data = {}
        self.knowledge_base = KnowledgeBase()

        if knowledge_base:
            self.knowledge_base = knowledge_base
        else:
            self.knowledge_base = KnowledgeBase()
            
        self.troubleshooter = ServiceTroubleshooter(self.knowledge_base)
        self.raspberry_specific_issues = {
            'rng-tools': {
                'detection': ['rng-tools', 'hardware RNG', 'no entropy source'],
                'solution': 'disable_service',
                'message': 'Raspberry Pi lacks hardware RNG, install haveged instead',
                'command': 'sudo apt install haveged && sudo systemctl disable rng-tools-debian --now'
            },
            'memory_issues': {
                'detection': ['oom', 'out of memory', 'killed process'],
                'solution': 'adjust_swappiness',
                'message': 'High memory pressure, adjusting swappiness',
                'command': 'echo "vm.swappiness=10" | sudo tee -a /etc/sysctl.conf && sudo sysctl -p'
            },
            'temperature': {
                'detection': ['thermal', 'throttling', 'temperature'],
                'solution': 'reduce_load',
                'message': 'CPU throttling due to temperature, reducing load',
                'command': 'echo powersave | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor'
            }
        }
        
        # Load long-term patterns
        self.load_patterns()
        
    def load_config(self) -> Dict:
        """Load configuration from YAML file with proper defaults"""
        default_config = {
            'thresholds': {
                'cpu_temp': 75.0,
                'memory_usage': 85.0,
                'disk_usage': 90.0,
                'load_15min': 3.0,
                'failed_logins': 10,  # Make sure this exists!
                'packet_loss': 5.0,
                'latency': 100.0
            },
            'actions': {
                'auto_block_ips': True,
                'auto_restart_services': True,
                'auto_optimize_network': True,
                'auto_clear_cache': True,
                'auto_manage_services': True,
                'auto_learn_patterns': True
            },
            'notifications': {
                'email': '',
                'webhook': ''
            },
            'learning': {
                'pattern_memory_size': 1000,
                'min_occurrences_for_learning': 3,
                'trend_analysis_hours': 72
            }
        }
        
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    loaded_config = yaml.safe_load(f) or {}
                
                # Ensure all required threshold keys exist
                if 'thresholds' in loaded_config:
                    loaded_config['thresholds'] = {**default_config['thresholds'], **loaded_config['thresholds']}
                
                return {**default_config, **loaded_config}
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                return default_config
        return default_config
        
    def load_patterns(self):
        """Load learned patterns from file"""
        self.learned_patterns = {}
        if PATTERNS_FILE.exists():
            try:
                with open(PATTERNS_FILE, 'rb') as f:
                    self.learned_patterns = pickle.load(f)
                logger.info(f"Loaded {len(self.learned_patterns)} learned patterns")
            except Exception as e:
                logger.error(f"Error loading patterns: {e}")
                self.learned_patterns = {}

    def save_patterns(self):
        """Save learned patterns to file"""
        try:
            with open(PATTERNS_FILE, 'wb') as f:
                pickle.dump(self.learned_patterns, f)
            logger.info(f"Saved {len(self.learned_patterns)} patterns to {PATTERNS_FILE}")
        except Exception as e:
            logger.error(f"Error saving patterns: {e}")

    def run_command(self, cmd: str) -> str:
        """Run a shell command safely"""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout.strip() if result.returncode == 0 else f"ERROR: {result.stderr}"
        except subprocess.TimeoutExpired:
            return "ERROR: Command timed out"
        except Exception as e:
            return f"ERROR: {str(e)}"

    def detect_raspberry_specific_issues(self):
        """Detect and handle Raspberry Pi specific issues"""
        issues_found = []
        
        # Check journal for known issues
        journal_logs = self.run_command("journalctl --since '1 hour ago' --no-pager | tail -100")
        
        for issue_name, issue_data in self.raspberry_specific_issues.items():
            for pattern in issue_data['detection']:
                if pattern.lower() in journal_logs.lower():
                    issues_found.append({
                        'issue': issue_name,
                        'solution': issue_data['solution'],
                        'message': issue_data['message'],
                        'command': issue_data['command']
                    })
                    break
        
        return issues_found

    def execute_autonomous_fixes(self, detected_issues):
        """Execute fixes for detected issues"""
        results = []
        
        for issue in detected_issues:
            try:
                # Store pattern before fixing
                pattern_data = {
                    'issue_type': issue['issue'],
                    'action_taken': issue['command']
                }
                self.knowledge_base.store_pattern('raspberry_issue', pattern_data, severity=0.5)
                
                # Execute the fix
                result = self.run_command(issue['command'])
                results.append(f"{issue['issue']}: {result}")
            except Exception as e:
                results.append(f"{issue['issue']}: ERROR - {e}")
        
        return results

    def detect_journal_issues(self):
        """Detect system issues from journal logs"""
        issues_found = []
        
        # Get recent journal entries
        journal_logs = self.run_command("journalctl --since '1 hour ago' --no-pager | tail -200")
        
        # Analyze for filesystem and other system issues
        journal_recommendations = self.troubleshooter.analyze_journal_issues(journal_logs)
        
        for recommendation in journal_recommendations:
            issues_found.append({
                'issue': recommendation['issue'],
                'solution': recommendation['solution'],
                'message': recommendation['reason'],
                'command': self.get_fix_command(recommendation['solution'])
            })
        
        return issues_found

    def get_fix_command(self, solution_type):
        """Get appropriate fix command for journal issues"""
        fix_commands = {
            'check_disk_health': 'sudo smartctl -a /dev/mmcblk0 && sudo fsck -n /dev/mmcblk0p2',
            'check_power_issues': 'echo "Check power supply and consider using UPS"',
            'investigate_disk': 'sudo dmesg | grep -i "sd\\|mmc" | tail -20 && sudo fsck -n /dev/mmcblk0p2',
            'run_fsck': 'echo "Schedule filesystem check: sudo touch /forcefsck && sudo reboot"'
        }
        return fix_commands.get(solution_type, 'echo "No specific fix command"')

    def collect_health_data(self) -> Dict:
        """Collect comprehensive system health data with better temperature reading"""
        ts = datetime.datetime.now().isoformat()
        previous_health = self.health_data.copy() if self.health_data else {}
        
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=1)
            load_avg = psutil.getloadavg()
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk
            disk = psutil.disk_usage("/")
            disk_io = psutil.disk_io_counters()
            
            # Network
            net_io = psutil.net_io_counters()
            latency = self.measure_latency()
            packet_loss = self.measure_packet_loss()
            
            # Temperature - Improved reading
            temp = self.get_cpu_temperature()
            
            # Services
            failed_services = self.run_command("systemctl --failed --no-legend | wc -l")
            
            # Security
            failed_logins = self.count_failed_logins()
            suspicious_ips = self.detect_suspicious_ips()
            
            # Hardware-specific metrics (Raspberry Pi)
            voltage = self.run_command("vcgencmd measure_volts | cut -d= -f2") or "N/A"
            clock_speed = self.run_command("vcgencmd measure_clock arm | awk -F= '{print $2}'") or "N/A"
            throttling = self.run_command("vcgencmd get_throttled") or "N/A"
            
            self.health_data = {
                'timestamp': ts,
                'cpu': {
                    'percent': cpu_percent,
                    'load_1min': load_avg[0],
                    'load_5min': load_avg[1],
                    'load_15min': load_avg[2],
                    'temperature': temp,
                    'clock_speed': clock_speed,
                    'throttling': throttling
                },
                'memory': {
                    'total_gb': round(mem.total / (1024**3), 2),
                    'used_gb': round(mem.used / (1024**3), 2),
                    'percent': mem.percent,
                    'available_gb': round(mem.available / (1024**3), 2)
                },
                'swap': {
                    'total_gb': round(swap.total / (1024**3), 2),
                    'used_gb': round(swap.used / (1024**3), 2),
                    'percent': swap.percent
                },
                'disk': {
                    'total_gb': round(disk.total / (1024**3), 2),
                    'used_gb': round(disk.used / (1024**3), 2),
                    'percent': disk.percent,
                    'read_mb': round(disk_io.read_bytes / (1024**2), 2) if disk_io else 0,
                    'write_mb': round(disk_io.write_bytes / (1024**2), 2) if disk_io else 0
                },
                'network': {
                    'latency_ms': latency,
                    'packet_loss_percent': packet_loss,
                    'sent_mb': round(net_io.bytes_sent / (1024**2), 2),
                    'received_mb': round(net_io.bytes_recv / (1024**2), 2)
                },
                'hardware': {
                    'voltage': voltage,
                    'throttling_status': throttling
                },
                'services': {
                    'failed_count': int(failed_services) if failed_services.isdigit() else 0
                },
                'security': {
                    'failed_logins': failed_logins,
                    'suspicious_ips': suspicious_ips
                }
            }
            
            # Store long-term metrics
            self.store_long_term_metrics(previous_health)
            
            # Log health data
            self.log_health_data()
            
        except Exception as e:
            logger.error(f"Error collecting health data: {e}")
            self.health_data = {'timestamp': ts, 'error': str(e)}
            
        return self.health_data

    def get_cpu_temperature(self):
        """Get CPU temperature with multiple fallback methods"""
        try:
            # Method 1: vcgencmd (Raspberry Pi)
            temp_output = self.run_command("vcgencmd measure_temp")
            if temp_output and "temp" in temp_output:
                temp_str = temp_output.split("=")[1].split("'")[0]
                return float(temp_str)
            
            # Method 2: Thermal zone (Linux)
            try:
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temp_millic = float(f.read().strip())
                    return temp_millic / 1000.0  # Convert to Celsius
            except:
                pass
                
            # Method 3: sensors command
            sensors_output = self.run_command("sensors | grep -i temp | head -1")
            if sensors_output:
                import re
                match = re.search(r'([0-9]+\.[0-9]+)°C', sensors_output)
                if match:
                    return float(match.group(1))
            
            # Method 4: Check multiple thermal zones
            for zone in range(5):
                try:
                    with open(f"/sys/class/thermal/thermal_zone{zone}/temp", "r") as f:
                        temp_millic = float(f.read().strip())
                        temp_c = temp_millic / 1000.0
                        if temp_c > 10:  # Reasonable temperature check
                            return temp_c
                except:
                    continue
                    
            logger.warning("Could not read CPU temperature using any method")
            return 0.0
            
        except Exception as e:
            logger.error(f"Error reading CPU temperature: {e}")
            return 0.0
        
    def store_long_term_metrics(self, previous_health):
        """Store metrics for long-term trend analysis"""
        if not self.health_data:
            logger.warning("No health data available for metric storage")
            return
        
        logger.info(f"Storing long-term metrics for timestamp: {self.health_data['timestamp']}")
        
        # Store key metrics
        metrics_to_store = [
            ('cpu_percent', self.health_data['cpu']['percent']),
            ('cpu_temperature', self.health_data['cpu']['temperature']),
            ('memory_percent', self.health_data['memory']['percent']),
            ('disk_percent', self.health_data['disk']['percent']),
            ('load_15min', self.health_data['cpu']['load_15min']),
            ('network_latency', self.health_data['network']['latency_ms']),
            ('packet_loss', self.health_data['network']['packet_loss_percent']),
            ('failed_services', self.health_data['services']['failed_count']),
            ('failed_logins', self.health_data['security']['failed_logins'])
        ]
        
        stored_count = 0
        for metric_name, metric_value in metrics_to_store:
            try:
                success = self.knowledge_base.store_metric(metric_name, metric_value, {
                    'timestamp': self.health_data['timestamp']
                })
                if success:
                    stored_count += 1
                    logger.debug(f"Stored metric: {metric_name} = {metric_value}")
                else:
                    logger.warning(f"Failed to store metric: {metric_name}")
            except Exception as e:
                logger.error(f"Error storing metric {metric_name}: {e}")
        
        logger.info(f"Successfully stored {stored_count}/{len(metrics_to_store)} metrics")
        
    def calculate_improvement(self, previous, current):
        """Calculate overall system improvement percentage"""
        if not previous or not current:
            return 0.0
        
        # Weighted factors for improvement calculation
        factors = {
            'cpu_percent': 0.25,
            'memory_percent': 0.25,
            'load_15min': 0.20,
            'disk_percent': 0.15,
            'failed_services': 0.15
        }
        
        improvement = 0.0
        for factor, weight in factors.items():
            if factor == 'failed_services':
                # For failed services, improvement is reduction in count
                prev_val = previous['services']['failed_count'] if 'services' in previous else 0
                curr_val = current['services']['failed_count']
                if prev_val > 0:
                    improvement += weight * (prev_val - curr_val) / prev_val * 100
            else:
                # For percentages, improvement is reduction in usage
                if factor == 'cpu_percent':
                    prev_val = previous['cpu']['percent']
                    curr_val = current['cpu']['percent']
                elif factor == 'memory_percent':
                    prev_val = previous['memory']['percent']
                    curr_val = current['memory']['percent']
                elif factor == 'disk_percent':
                    prev_val = previous['disk']['percent']
                    curr_val = current['disk']['percent']
                elif factor == 'load_15min':
                    prev_val = previous['cpu']['load_15min']
                    curr_val = current['cpu']['load_15min']
                
                if prev_val > 0:
                    improvement += weight * (prev_val - curr_val) / prev_val * 100
        
        return improvement

    def measure_latency(self) -> float:
        """Measure network latency to Google DNS"""
        try:
            result = self.run_command("ping -c 3 8.8.8.8 | tail -1 | awk '{print $4}' | cut -d'/' -f2")
            return float(result) if result.replace('.', '').isdigit() else 0.0
        except:
            return 0.0

    def measure_packet_loss(self) -> float:
        """Measure packet loss"""
        try:
            result = self.run_command("ping -c 10 8.8.8.8 | grep 'packet loss' | awk '{print $6}' | tr -d '%'")
            return float(result) if result.replace('.', '').isdigit() else 0.0
        except:
            return 0.0

    def count_failed_logins(self) -> int:
        """Count failed login attempts in last hour"""
        try:
            result = self.run_command("grep 'Failed password' /var/log/auth.log | grep '$(date -d \"1 hour ago\" \"+%b %d %H\")' | wc -l")
            return int(result) if result.isdigit() else 0
        except:
            return 0

    def detect_suspicious_ips(self) -> Dict[str, int]:
        """Detect suspicious IP addresses with multiple failed attempts"""
        suspicious = {}
        try:
            result = self.run_command("grep 'Failed password' /var/log/auth.log | awk '{print $(NF-3)}' | sort | uniq -c | sort -nr | head -5")
            for line in result.split('\n'):
                if line.strip():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        count, ip = parts[0], parts[1]
                        suspicious[ip] = int(count)
        except:
            pass
        return suspicious

    def log_health_data(self):
        """Log health data to file"""
        try:
            with open(HEALTH_LOG, 'a') as f:
                f.write(f"[{self.health_data['timestamp']}] Health Data: {json.dumps(self.health_data)}\n")
        except Exception as e:
            logger.error(f"Error logging health data: {e}")

    def analyze_system_state(self) -> List[Dict]:
        """Analyze system state and recommend actions with learned knowledge"""
        actions = []
        
        if not self.health_data:
            return actions
        
        # Check for patterns in current state
        system_pattern = self.health_data.copy()
        # Remove timestamp for pattern matching
        if 'timestamp' in system_pattern:
            del system_pattern['timestamp']
        
        similar_patterns = self.knowledge_base.get_similar_patterns(system_pattern, 'system_state')
        
        # Add actions based on learned patterns
        for pattern in similar_patterns:
            if pattern['similarity'] > 0.75 and pattern['solution']:
                actions.append({
                    'action': pattern['solution'],
                    'priority': 'high' if pattern['severity'] > 0.7 else 'medium',
                    'reason': f"Matched learned pattern (confidence: {pattern['confidence']:.2f})",
                    'learned_pattern': True,
                    'pattern_similarity': pattern['similarity']
                })
        
        # CPU Temperature
        cpu_temp = self.health_data['cpu']['temperature']
        if cpu_temp > self.thresholds['cpu_temp']:
            actions.append({
                'action': 'throttle_cpu',
                'priority': 'high',
                'reason': f'CPU temperature critical: {cpu_temp}°C (threshold: {self.thresholds["cpu_temp"]}°C)'
            })
        
        # Memory Usage
        mem_percent = self.health_data['memory']['percent']
        if mem_percent > self.thresholds['memory_usage']:
            actions.append({
                'action': 'clear_cache',
                'priority': 'medium',
                'reason': f'High memory usage: {mem_percent}% (threshold: {self.thresholds["memory_usage"]}%)'
            })
        
        # Disk Usage
        disk_percent = self.health_data['disk']['percent']
        if disk_percent > self.thresholds['disk_usage']:
            actions.append({
                'action': 'clean_logs',
                'priority': 'high',
                'reason': f'Disk usage critical: {disk_percent}% (threshold: {self.thresholds["disk_usage"]}%)'
            })
        
        # Load Average
        load_15min = self.health_data['cpu']['load_15min']
        if load_15min > self.thresholds['load_15min']:
            actions.append({
                'action': 'manage_services',
                'target': 'stop_non_essential',
                'priority': 'medium',
                'reason': f'High system load: {load_15min} (threshold: {self.thresholds["load_15min"]})'
            })
        
        # Failed Services
        failed_services = self.health_data['services']['failed_count']
        if failed_services > 0:
            # Get the actual failed services for smart analysis
            failed_list = self.run_command("systemctl --failed --no-legend | awk '{print $1}' | tr '\n' ','")
            actions.append({
                'action': 'restart_failed_services',
                'priority': 'medium',
                'reason': f'{failed_services} failed services detected: {failed_list}',
                'smart_troubleshooting': True
            })
        
        # Security - Failed Logins (with error handling)
        failed_logins = self.health_data['security']['failed_logins']
        failed_logins_threshold = self.thresholds.get('failed_logins', 10)  # Default to 10 if missing
        if failed_logins > failed_logins_threshold:
            actions.append({
                'action': 'increase_security',
                'priority': 'high',
                'reason': f'High failed login attempts: {failed_logins} (threshold: {failed_logins_threshold})'
            })

        # Network Issues
        if self.health_data['network']['packet_loss_percent'] > self.thresholds['packet_loss']:
            actions.append({
                'action': 'optimize_network',
                'priority': 'medium',
                'reason': f'High packet loss: {self.health_data["network"]["packet_loss_percent"]}%'
            })
        
        # Check for long-term trends that might indicate emerging issues
        trend_actions = self.check_long_term_trends()
        actions.extend(trend_actions)
        
        # Sort by priority
        priority_order = {'high': 3, 'medium': 2, 'low': 1}
        return sorted(actions, key=lambda x: priority_order.get(x['priority'], 0), reverse=True)

    def check_long_term_trends(self):
        """Check long-term trends for emerging issues"""
        actions = []
        trends_to_check = [
            ('cpu_temperature', 'high', 'CPU temperature trending upward'),
            ('memory_percent', 'high', 'Memory usage trending upward'),
            ('disk_percent', 'high', 'Disk usage trending upward'),
            ('load_15min', 'high', 'System load trending upward')
        ]
        
        for metric, direction, reason in trends_to_check:
            trend = self.knowledge_base.get_metric_trend(metric, 
                                                         self.config['learning']['trend_analysis_hours'])
            if trend and trend['trend'] == direction:
                # Check if the trend is significant
                if abs(trend['slope']) > 0.5:  # Significant trend
                    actions.append({
                        'action': 'investigate_trend',
                        'target': metric,
                        'priority': 'medium',
                        'reason': f'{reason}: slope {trend["slope"]:.2f}',
                        'trend_data': trend
                    })
        
        return actions
    
    def execute_action(self, action: Dict) -> str:
        """Execute a recommended action"""
        action_type = action['action']
        target = action.get('target', '')
        reason = action.get('reason', '')
        
        action_handlers = {
            'clear_cache': lambda: self.run_command("sync; echo 3 > /proc/sys/vm/drop_caches"),
            'throttle_cpu': lambda: self.run_command("echo powersave > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"),
            'clean_logs': lambda: self.run_command("find /var/log -name \"*.log\" -mtime +7 -delete"),
            'restart_failed_services': self.restart_failed_services,
            'optimize_network': self.optimize_network_settings,
            'manage_services': lambda: self.manage_services(target),
            'increase_security': self.increase_security,
            'ban_ip': lambda: self.ban_ip(target) if target else "No IP specified"
        }
        
        if action_type in action_handlers and self.actions_enabled.get(f'auto_{action_type}', True):
            try:
                if action.get('smart_troubleshooting', False):
                    result = self.enhanced_restart_failed_services()
                else:
                    result = action_handlers[action_type]()
                self.log_action(action_type, target, reason, result)
                return result
            except Exception as e:
                error_msg = f"Failed to execute {action_type}: {e}"
                self.log_action(action_type, target, reason, error_msg, success=False)
                return error_msg
        else:
            return f"Action {action_type} not enabled or not found"

    def restart_failed_services(self) -> str:
        """Smart service restart with autonomous troubleshooting"""
        return self.enhanced_restart_failed_services()

    def optimize_network_settings(self) -> str:
        """Optimize network settings based on current conditions"""
        results = []
        
        if self.health_data['network']['packet_loss_percent'] > 5:
            results.append(self.run_command("sysctl -w net.ipv4.tcp_sack=0"))
            results.append("Disabled TCP SACK due to high packet loss")
        
        if self.health_data['network']['latency_ms'] > 100:
            results.append(self.run_command("sysctl -w net.ipv4.tcp_window_scaling=1"))
            results.append("Enabled TCP window scaling for high latency")
        
        return "\n".join(results) if results else "No network optimization needed"

    def manage_services(self, operation: str) -> str:
        """Manage non-essential services"""
        non_essential = ['bluetooth', 'avahi-daemon', 'triggerhappy', 'wolfram-engine']
        
        if operation == 'stop_non_essential':
            results = []
            for service in non_essential:
                if self.is_service_running(service):
                    result = self.run_command(f"systemctl stop {service}")
                    results.append(f"Stopped {service}: {result}")
            return "\n".join(results) if results else "No non-essential services running"
        
        return f"Unknown operation: {operation}"

    def increase_security(self) -> str:
        """Increase security measures"""
        results = []
        
        # Block suspicious IPs
        for ip, count in self.health_data['security']['suspicious_ips'].items():
            if count > 20:  # More than 20 failed attempts
                result = self.run_command(f"ufw deny from {ip}")
                results.append(f"Blocked {ip}: {result}")
        
        # Harden SSH if many failed attempts
        if self.health_data['security']['failed_logins'] > 50:
            result = self.run_command("sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config")
            results.append("Disabled root SSH login")
            results.append(self.run_command("systemctl restart ssh"))
        
        return "\n".join(results) if results else "No security enhancements needed"

    def ban_ip(self, ip: str) -> str:
        """Ban a specific IP address"""
        return self.run_command(f"ufw deny from {ip}")

    def is_service_running(self, service: str) -> bool:
        """Check if a service is running"""
        result = self.run_command(f"systemctl is-active {service}")
        return result == "active"

    def log_action(self, action: str, target: str, reason: str, result: str, success: bool = True):
        """Log actions taken by the doctor"""
        status = "SUCCESS" if success else "FAILED"
        log_entry = f"[{datetime.datetime.now().isoformat()}] {status} - {action}({target}): {reason} - Result: {result}"
        
        try:
            with open(ACTIONS_LOG, 'a') as f:
                f.write(log_entry + "\n")
            
            # Also store in database
            system_state_hash = hashlib.md5(json.dumps(self.health_data, sort_keys=True).encode()).hexdigest()
            self.knowledge_base.store_action_outcome(
                action, target, reason, result, success, system_state_hash
            )
            
        except Exception as e:
            logger.error(f"Error logging action: {e}")
            
    def consult_ai(self, context: str) -> Optional[Dict]:
        """Consult AI for complex decisions"""
        try:
            prompt = f"""Analyze this system health data and suggest the most appropriate action:
            {context}
            
            Respond with JSON only: {{"action": "action_name", "target": "optional_target", "reason": "explanation"}}
            Available actions: clear_cache, throttle_cpu, clean_logs, restart_failed_services, optimize_network, manage_services, increase_security, ban_ip, none"""
            
            url = f"{OLLAMA_HOST}/api/generate"
            payload = {
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1}
            }
            
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            ai_response = response.json().get('response', '').strip()
            
            # Extract JSON from response
            try:
                return json.loads(ai_response)
            except json.JSONDecodeError:
                # Try to find JSON in the response
                import re
                json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return None
                
        except Exception as e:
            logger.error(f"AI consultation failed: {e}")
            return None

    def enhanced_restart_failed_services(self):
        """Smart service restart with troubleshooting"""
        failed_services = self.run_command("systemctl --failed --no-legend | awk '{print $1}'")
        if not failed_services or "no units" in failed_services.lower():
            return "No failed services found"
        
        results = []
        
        for service in failed_services.split('\n'):
            service = service.strip()
            if not service or service in ['', '●']:
                continue
                
            # Get detailed service status and logs
            service_status = self.run_command(f"systemctl status {service} --no-pager || true")
            service_logs = self.run_command(f"journalctl -u {service} --no-pager -n 20 || true")
            
            # Special handling for Cloudflare Tunnel
            if 'cloudflared' in service.lower():
                print(f"Detected Cloudflare service issue: {service}")
                recommendations = self.troubleshooter.analyze_cloudflared_issue(service, service_status, service_logs)
                
                if recommendations:
                    recommendation = recommendations[0]
                    result = self.troubleshooter.execute_cloudflared_solution(recommendation, self.run_command)
                    results.append(f"{service}: {result} (Cloudflare-specific fix)")
                    continue
            
            # Standard analysis for other services
            recommendations = self.troubleshooter.analyze_service_issue(service, service_status)
            
            if recommendations:
                # Use the first recommendation (highest confidence)
                recommendation = recommendations[0]
                result = self.troubleshooter.execute_solution(recommendation, self.run_command)
                results.append(f"{service}: {result} (AI troubleshooting)")
            else:
                # Standard restart for unknown issues
                check_cmd = f"systemctl cat {service} >/dev/null 2>&1"
                if subprocess.run(check_cmd, shell=True).returncode == 0:
                    result = self.run_command(f"systemctl restart {service}")
                    results.append(f"{service}: {result}")
                else:
                    results.append(f"{service}: SKIPPED (not a valid service)")
        
        return "\n".join(results)

    def consult_ai_for_troubleshooting(self, service_name, service_logs):
        """Use Ollama to analyze service issues"""
        try:
            prompt = f"""Analyze this service failure and suggest a solution:

Service: {service_name}
Logs: {service_logs[:2000]}

Common Raspberry Pi service issues:
- rng-tools: Hardware RNG not available, disable and use haveged
- avahi-daemon: Network discovery conflicts, disable if not needed
- bluetooth: Resource intensive, disable if not used
- Failed dependencies: Check required services

Respond with JSON: {{"solution": "disable|stop|reinstall|investigate", "reason": "explanation", "confidence": "high|medium|low"}}
"""
            
            # You'll need to implement the summarize_text function or use Ollama directly
            # response = summarize_text(prompt, max_chars=1000)
            # return json.loads(response)
            return {"solution": "investigate", "reason": "AI analysis not implemented", "confidence": "low"}
            
        except Exception as e:
            return {"solution": "investigate", "reason": f"AI analysis failed: {e}", "confidence": "low"}

    def run_enhanced(self):
        """Enhanced execution with autonomous troubleshooting"""
        logger.info("Starting Enhanced Autonomous Doctor with Troubleshooting")
        
        # Collect health data
        health_data = self.collect_health_data()
        
        # Detect Raspberry-specific issues
        raspberry_issues = self.detect_raspberry_specific_issues()
        
        # Detect journal issues (NEW)
        journal_issues = self.detect_journal_issues()
        
        all_issues = raspberry_issues + journal_issues
        
        if all_issues:
            logger.info(f"Detected issues: {len(all_issues)}")
            fix_results = self.execute_autonomous_fixes(all_issues)
            for result in fix_results:
                logger.info(f"Autonomous fix: {result}")
        
        # Continue with normal analysis and actions
        recommended_actions = self.analyze_system_state()
        
        # Execute actions with smart troubleshooting
        executed_actions = []
        for action in recommended_actions:
            logger.info(f"Executing action: {action}")
            result = self.execute_action(action)
            executed_actions.append((action, result))
        
        # For complex situations, consult AI
        if not executed_actions and len(recommended_actions) > 0:
            context = json.dumps(self.health_data, indent=2)
            ai_decision = self.consult_ai(context)
            if ai_decision and ai_decision.get('action') != 'none':
                logger.info(f"AI recommended action: {ai_decision}")
                result = self.execute_action(ai_decision)
                executed_actions.append((ai_decision, result))
        
        logger.info(f"Enhanced Doctor completed. Actions executed: {len(executed_actions)}")
        return executed_actions
        
    def learn_from_issues(self):
        """Learn from recurring issues and adapt"""
        # Read past actions and results
        try:
            with open(ACTIONS_LOG, 'r') as f:
                past_actions = f.readlines()[-100:]  # Last 100 actions
            
            # Analyze patterns of failures
            recurring_issues = {}
            for action in past_actions:
                if 'ERROR' in action or 'FAILED' in action:
                    # Extract service/issue name and count occurrences
                    pass  # Implement pattern matching here
            
            # Update knowledge base based on learnings
            if recurring_issues:
                logger.info(f"Learned from {len(recurring_issues)} recurring issues")
                
        except Exception as e:
            logger.error(f"Learning system error: {e}")
def main():
    """Main function"""
    # Ensure config directory exists
    if CONFIG_FILE.parent != Path("."):
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Create default config if it doesn't exist
    if not CONFIG_FILE.exists():
        default_config = {
            'thresholds': {
                'cpu_temp': 75.0,
                'memory_usage': 85.0,
                'disk_usage': 90.0,
                'load_15min': 3.0,
                'failed_logins': 10,
                'packet_loss': 5.0,
                'latency': 100.0
            },
            'actions': {
                'auto_block_ips': True,
                'auto_restart_services': True,
                'auto_optimize_network': True,
                'auto_clear_cache': True,
                'auto_manage_services': True
            }
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False)
            logger.info("Created default configuration file at %s", CONFIG_FILE)
        except Exception as e:
            logger.error(f"Failed to create config file: {e}")

    # Initialize knowledge base
    kb = KnowledgeBase()
    logger.info("Knowledge database initialized at %s", KNOWLEDGE_DB)

    kb.debug_database_status()

    # Run the autonomous doctor
    doctor = AutonomousDoctor(knowledge_base=kb)
    results = doctor.run_enhanced()

    kb.debug_database_status()

    # Print summary
    print("\n=== Enhanced Doctor Summary ===")
    print(f"Timestamp: {datetime.datetime.now().isoformat()}")
    print(f"Actions executed: {len(results)}")
    for action, result in results:
        print(f"  - {action['action']}: {action['reason']}")
        print(f"    Result: {str(result)[:100]}...")

    return 0


if __name__ == "__main__":
    main()