#!/home/pi/raspi-doctor/.venv/bin/python3
# check_failed_service.py

from enhanced_doctor import AutonomousDoctor

def check_failed_service():
    doctor = AutonomousDoctor()
    
    print("=== Analyzing Failed Service ===")
    
    # Get detailed service status
    service_status = doctor.run_command("systemctl status cloudflared.service --no-pager || true")
    print("Cloudflared service status:")
    print(service_status)
    
    # Check service logs
    service_logs = doctor.run_command("journalctl -u cloudflared.service --no-pager -n 20 || true")
    print("\nRecent cloudflared logs:")
    print(service_logs)
    
    # Check if this should trigger an action
    health_data = doctor.collect_health_data()
    if health_data['services']['failed_count'] > 0:
        print("\nService failure detected! This should trigger:")
        print("- Pattern storage in system_patterns table")
        print("- Action outcome in action_outcomes table")
        print("- Automatic service restart attempt")

if __name__ == "__main__":
    check_failed_service()