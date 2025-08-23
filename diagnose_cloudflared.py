#!/home/pi/raspi-doctor/.venv/bin/python3
# diagnose_cloudflared.py

import subprocess  # ADD THIS IMPORT
import yaml
from enhanced_doctor import ServiceTroubleshooter
from enhanced_doctor import KnowledgeBase

def diagnose_cloudflared():
    kb = KnowledgeBase()
    troubleshooter = ServiceTroubleshooter(kb)
    
    print("=== Cloudflare Tunnel Diagnosis ===")
    
    # Get service details
    service_name = "cloudflared.service"
    service_status = subprocess.run(f"systemctl status {service_name} --no-pager", 
                                  shell=True, capture_output=True, text=True).stdout
    service_logs = subprocess.run(f"journalctl -u {service_name} --no-pager -n 20", 
                                 shell=True, capture_output=True, text=True).stdout
    
    print("Service status:")
    print(service_status)
    
    print("\nRecent logs:")
    print(service_logs)
    
    # Analyze the issue
    print("\n=== Analysis ===")
    recommendations = troubleshooter.analyze_cloudflared_issue(service_name, service_status, service_logs)
    
    print(f"Recommendations: {len(recommendations)}")
    for rec in recommendations:
        print(f"  - {rec['issue']}: {rec['reason']}")
        print(f"    Solution: {rec['solution']}")
    
    # Test the solution
    if recommendations:
        print("\n=== Testing Solution ===")
        result = troubleshooter.execute_cloudflared_solution(recommendations[0], 
                                                           lambda cmd: subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout)
        print(f"Solution result: {result}")
    
    # Check current config
    print("\n=== Current Config Analysis ===")
    try:
        config_content = subprocess.run(f"sudo cat {config_path}", shell=True, capture_output=True, text=True).stdout
        print("Current config content:")
        print(config_content)
        
        # Try to validate YAML
        try:
            yaml.safe_load(config_content)
            print("✓ Config YAML is valid")
        except yaml.YAMLError as e:
            print(f"✗ YAML Error: {e}")
            
    except Exception as e:
        print(f"Error reading config: {e}")

if __name__ == "__main__":
    diagnose_cloudflared()