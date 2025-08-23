#!/home/pi/raspi-doctor/.venv/bin/python3
# doctor_service.py - Background service that collects health data

import time
import logging
from pathlib import Path
from enhanced_doctor import AutonomousDoctor, KnowledgeBase

# Setup logging
LOG_DIR = Path("/var/log/ai_health")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "doctor_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("doctor_service")

def main():
    logger.info("Starting Autonomous Doctor Service")
    
    # Initialize knowledge base
    kb = KnowledgeBase()
    kb.debug_database_status()
    
    # Initialize doctor
    doctor = AutonomousDoctor(knowledge_base=kb)
    
    # Run continuously
    while True:
        try:
            logger.info("Running health check cycle...")
            results = doctor.run_enhanced()
            
            # Debug database status
            kb.debug_database_status()
            
            logger.info(f"Cycle completed. Actions executed: {len(results)}")
            
            # Wait before next cycle (e.g., 5 minutes)
            time.sleep(300)
            
        except Exception as e:
            logger.error(f"Error in doctor service: {e}")
            time.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    main()