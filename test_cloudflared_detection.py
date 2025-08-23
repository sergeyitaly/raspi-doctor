#!/home/pi/raspi-doctor/.venv/bin/python3
# test_cloudflared_detection.py

from enhanced_doctor import AutonomousDoctor

def test_cloudflared_detection():
    doctor = AutonomousDoctor()
    
    print("=== Testing Cloudflare Issue Detection ===")
    
    # Simulate the cloudflared failure scenario
    test_logs = """
error parsing YAML in config file at /home/pi/.cloudflared/config.yml: yaml: line 3: mapping values are not allowed in this context
Cloudflare Tunnel failed to start
"""
    
    # Test the specialized analyzer
    recommendations = doctor.troubleshooter.analyze_cloudflared_issue(
        "cloudflared.service", 
        "failed (Result: exit-code)", 
        test_logs
    )
    
    print(f"Cloudflare recommendations: {len(recommendations)}")
    for rec in recommendations:
        print(f"  - {rec['issue']}: {rec['reason']}")
        print(f"    Solution: {rec['solution']}")
    
    # Test the full enhanced restart
    print("\n=== Testing Enhanced Restart ===")
    result = doctor.enhanced_restart_failed_services()
    print("Enhanced restart result:")
    print(result)
    
    # Check if patterns would be stored
    print("\n=== Pattern Storage Test ===")
    pattern_data = {
        'service': 'cloudflared.service',
        'error_type': 'yaml_config_error',
        'error_message': 'mapping values are not allowed in this context',
        'solution_applied': 'fix_cloudflared_config'
    }
    
    success = doctor.knowledge_base.store_pattern(
        'service_failure', 
        pattern_data,
        severity=0.7,
        confidence=0.9,
        solution="fix_cloudflared_config"
    )
    print(f"Pattern stored: {success}")

if __name__ == "__main__":
    test_cloudflared_detection()