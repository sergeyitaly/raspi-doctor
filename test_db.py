#!/home/pi/raspi-doctor/.venv/bin/python3
# test_db.py

from enhanced_doctor import KnowledgeBase

def test_database():
    kb = KnowledgeBase()
    
    # Test storing a metric
    success = kb.store_metric('test_cpu', 50.5, {'test': 'data'})
    print(f"Store metric success: {success}")
    
    # Debug status
    kb.debug_database_status()
    
    # Test getting trends
    trend = kb.get_metric_trend('test_cpu')
    print(f"Trend data: {trend}")

if __name__ == "__main__":
    test_database()