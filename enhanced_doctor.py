#!/usr/bin/env python3

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

# Configuration
CONFIG_FILE = Path("./config.yaml")
LOG_DIR = Path("/var/log/ai_health")
HEALTH_LOG = LOG_DIR / "health.log"
ACTIONS_LOG = LOG_DIR / "actions.log"
DECISIONS_LOG = LOG_DIR / "decisions.log"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")

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

class AutonomousDoctor:
    def __init__(self):
        self.config = self.load_config()
        self.thresholds = self.config.get('thresholds', {})
        self.actions_enabled = self.config.get('actions', {})
        self.health_data = {}
        
    def load_config(self) -> Dict:
        """Load configuration from YAML file"""
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
            },
            'notifications': {
                'email': '',
                'webhook': ''
            }
        }
        
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    loaded_config = yaml.safe_load(f) or {}
                return {**default_config, **loaded_config}
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                return default_config
        return default_config

    def run_command(self, cmd: str) -> str:
        """Run a shell command safely"""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout.strip() if result.returncode == 0 else f"ERROR: {result.stderr}"
        except subprocess.TimeoutExpired:
            return "ERROR: Command timed out"
        except Exception as e:
            return f"ERROR: {str(e)}"

    def collect_health_data(self) -> Dict:
        """Collect comprehensive system health data"""
        ts = datetime.datetime.now().isoformat()
        
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
            
            # Temperature
            temp = self.run_command("vcgencmd measure_temp | cut -d= -f2 | cut -d\' -f1") or "N/A"
            
            # Services
            failed_services = self.run_command("systemctl --failed --no-legend | wc -l")
            
            # Security
            failed_logins = self.count_failed_logins()
            suspicious_ips = self.detect_suspicious_ips()
            
            self.health_data = {
                'timestamp': ts,
                'cpu': {
                    'percent': cpu_percent,
                    'load_1min': load_avg[0],
                    'load_5min': load_avg[1],
                    'load_15min': load_avg[2],
                    'temperature': float(temp) if temp.replace('.', '').isdigit() else 0.0
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
                'services': {
                    'failed_count': int(failed_services) if failed_services.isdigit() else 0
                },
                'security': {
                    'failed_logins': failed_logins,
                    'suspicious_ips': suspicious_ips
                }
            }
            
            # Log health data
            self.log_health_data()
            
        except Exception as e:
            logger.error(f"Error collecting health data: {e}")
            self.health_data = {'timestamp': ts, 'error': str(e)}
            
        return self.health_data

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
                    count, ip = line.strip().split()[:2]
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
        """Analyze system state and recommend actions"""
        actions = []
        
        if not self.health_data:
            return actions
        
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
            actions.append({
                'action': 'restart_failed_services',
                'priority': 'medium',
                'reason': f'{failed_services} failed services detected'
            })
        
        # Security - Failed Logins
        failed_logins = self.health_data['security']['failed_logins']
        if failed_logins > self.thresholds['failed_logins']:
            actions.append({
                'action': 'increase_security',
                'priority': 'high',
                'reason': f'High failed login attempts: {failed_logins} (threshold: {self.thresholds["failed_logins"]})'
            })
        
        # Network Issues
        if self.health_data['network']['packet_loss_percent'] > self.thresholds['packet_loss']:
            actions.append({
                'action': 'optimize_network',
                'priority': 'medium',
                'reason': f'High packet loss: {self.health_data["network"]["packet_loss_percent"]}%'
            })
        
        # Sort by priority
        priority_order = {'high': 3, 'medium': 2, 'low': 1}
        return sorted(actions, key=lambda x: priority_order.get(x['priority'], 0), reverse=True)

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
        """Restart all failed services"""
        failed_services = self.run_command("systemctl --failed --no-legend | awk '{print $1}'")
        if not failed_services or "no units" in failed_services.lower():
            return "No failed services found"
        
        results = []
        for service in failed_services.split('\n'):
            service = service.strip()
            # Skip empty lines and invalid service names
            if service and not any(char in service for char in ['●', '○', '•', '·']):
                result = self.run_command(f"systemctl restart {service}")
                results.append(f"{service}: {result}")
        
        return "\n".join(results) if results else "No valid failed services found"

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
            with open(DECISIONS_LOG, 'a') as f:
                f.write(json.dumps({
                    'timestamp': datetime.datetime.now().isoformat(),
                    'action': action,
                    'target': target,
                    'reason': reason,
                    'result': result,
                    'success': success
                }) + "\n")
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

    def run(self):
        """Main execution method"""
        logger.info("Starting Enhanced Autonomous Doctor")
        
        # Collect health data
        health_data = self.collect_health_data()
        logger.info(f"Health data collected: {json.dumps(health_data, indent=2)}")
        
        # Analyze and get recommended actions
        recommended_actions = self.analyze_system_state()
        logger.info(f"Recommended actions: {len(recommended_actions)}")
        
        # Execute actions
        executed_actions = []
        for action in recommended_actions:
            if action['priority'] == 'high' or len(executed_actions) < 2:  # Limit actions per run
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

def main():
    """Main function"""
    # Ensure log directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)
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
            logger.info("Created default configuration file")
        except Exception as e:
            logger.error(f"Failed to create config file: {e}")
    
    # Run the autonomous doctor
    doctor = AutonomousDoctor()
    results = doctor.run()
    
    # Print summary
    print(f"\n=== Enhanced Doctor Summary ===")
    print(f"Timestamp: {datetime.datetime.now().isoformat()}")
    print(f"Actions executed: {len(results)}")
    for action, result in results:
        print(f"  - {action['action']}: {action['reason']}")
        print(f"    Result: {result[:100]}...")
    
    return 0

if __name__ == "__main__":
    exit(main())