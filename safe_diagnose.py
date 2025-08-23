#!/home/pi/raspi-doctor/.venv/bin/python3
# safe_diagnose.py

from enhanced_doctor import AutonomousDoctor

def safe_check_system_issues():
    doctor = AutonomousDoctor()
    
    print("=== Safe System Diagnosis ===")
    
    try:
        # Check journal for filesystem issues
        print("\n1. Checking journal for filesystem issues...")
        journal_output = doctor.run_command("journalctl -b | grep -i 'ext4\\|filesystem\\|recovery\\|readonly' | tail -20")
        print("Filesystem issues in journal:")
        print(journal_output if journal_output else "No filesystem issues found")
        
        # Check current health data
        print("\n2. Current health data analysis...")
        health_data = doctor.collect_health_data()
        
        # Check for failed services
        failed_services = doctor.run_command("systemctl --failed --no-legend")
        print(f"Failed services: {failed_services if failed_services else 'None'}")
        
        # Check disk health
        disk_health = doctor.run_command("sudo smartctl -a /dev/mmcblk0 2>/dev/null || echo 'SMART not available'")
        if "SMART" in disk_health and "PASSED" not in disk_health and "not available" not in disk_health:
            print("Disk SMART status issues detected")
        else:
            print("Disk SMART status: OK or not available")
        
        # Safe system state analysis with error handling
        print("\n3. System state analysis...")
        try:
            actions = doctor.analyze_system_state()
            print(f"Recommended actions: {len(actions)}")
            for action in actions:
                print(f"  - {action['action']}: {action['reason']}")
        except Exception as e:
            print(f"Error in system analysis: {e}")
            print("This is likely due to missing config keys. Let's check the config...")
            
            # Check config
            print("\nCurrent thresholds:")
            print(doctor.thresholds)
            
            # Provide default actions based on observed issues
            if "cloudflared.service" in failed_services:
                print("\nSuggested action: Restart failed cloudflared service")
            
            if "recovery required" in journal_output:
                print("\nSuggested action: Check filesystem health")
        
        return True
        
    except Exception as e:
        print(f"Diagnosis failed: {e}")
        return False

if __name__ == "__main__":
    safe_check_system_issues()