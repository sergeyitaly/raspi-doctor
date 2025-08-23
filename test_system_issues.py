#!/home/pi/raspi-doctor/.venv/bin/python3
# diagnose_doctor.py

from enhanced_doctor import AutonomousDoctor
import subprocess

def check_system_issues():
    doctor = AutonomousDoctor()
    
    print("=== Checking System Issues ===")
    
    # Check journal for filesystem issues
    print("\n1. Checking journal for filesystem issues...")
    journal_output = doctor.run_command("journalctl -b | grep -i 'ext4\\|filesystem\\|recovery\\|readonly' | tail -20")
    print("Filesystem issues in journal:")
    print(journal_output)
    
    # Check current health data
    print("\n2. Current health data analysis...")
    health_data = doctor.collect_health_data()
    
    # Check for failed services
    failed_services = doctor.run_command("systemctl --failed --no-legend")
    print(f"Failed services: {failed_services if failed_services else 'None'}")
    
    # Check disk health
    disk_health = doctor.run_command("sudo smartctl -a /dev/mmcblk0 || true")
    if "SMART" in disk_health and "PASSED" not in disk_health:
        print("Disk SMART status issues detected")
    
    # Analyze system state
    print("\n3. System state analysis...")
    actions = doctor.analyze_system_state()
    print(f"Recommended actions: {len(actions)}")
    for action in actions:
        print(f"  - {action['action']}: {action['reason']}")
    
    return actions

if __name__ == "__main__":
    check_system_issues()