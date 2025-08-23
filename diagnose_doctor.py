#!/home/pi/raspi-doctor/.venv/bin/python3
# test_filesystem_detection.py

from enhanced_doctor import AutonomousDoctor

def test_filesystem_detection():
    doctor = AutonomousDoctor()
    
    print("=== Testing Filesystem Issue Detection ===")
    
    # Test journal analysis
    test_journal = """
    [    1.063919] EXT4-fs (mmcblk0p2): INFO: recovery required on readonly filesystem
    [    1.063929] EXT4-fs (mmcblk0p2): write access will be enabled during recovery
    [    1.199697] EXT4-fs (mmcblk0p2): recovery complete
    [    2.318991] EXT4-fs (mmcblk0p2): orphan cleanup on readonly fs
    [    2.320736] EXT4-fs (mmcblk0p2): 1 orphan inode deleted
    """
    
    print("Test journal content:")
    print(test_journal)
    
    # Test the journal analysis
    issues = doctor.troubleshooter.analyze_journal_issues(test_journal)
    print(f"\nDetected issues: {len(issues)}")
    for issue in issues:
        print(f"  - {issue['issue']}: {issue['reason']}")
    
    # Test the full detection
    print("\n=== Full Detection Test ===")
    journal_issues = doctor.detect_journal_issues()
    print(f"Journal issues found: {len(journal_issues)}")
    for issue in journal_issues:
        print(f"  - {issue['issue']}: {issue['message']}")
        print(f"    Fix: {issue['command']}")

if __name__ == "__main__":
    test_filesystem_detection()