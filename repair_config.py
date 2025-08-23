#!/home/pi/raspi-doctor/.venv/bin/python3
# repair_config.py

import yaml
from pathlib import Path

CONFIG_FILE = Path("./config.yaml")

def repair_config():
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
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                current_config = yaml.safe_load(f) or {}
            
            # Repair missing keys
            repaired = False
            
            if 'thresholds' not in current_config:
                current_config['thresholds'] = default_config['thresholds']
                repaired = True
            else:
                # Ensure all threshold keys exist
                for key in default_config['thresholds']:
                    if key not in current_config['thresholds']:
                        current_config['thresholds'][key] = default_config['thresholds'][key]
                        repaired = True
            
            if 'actions' not in current_config:
                current_config['actions'] = default_config['actions']
                repaired = True
            
            if repaired:
                with open(CONFIG_FILE, 'w') as f:
                    yaml.dump(current_config, f, default_flow_style=False)
                print("Config file repaired successfully!")
            else:
                print("Config file is already valid.")
                
            print("Current config:")
            print(yaml.dump(current_config, default_flow_style=False))
            
        except Exception as e:
            print(f"Error repairing config: {e}")
            # Create fresh config
            with open(CONFIG_FILE, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False)
            print("Created new config file with defaults.")
    else:
        # Create config file
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)
        print("Created config file with defaults.")

if __name__ == "__main__":
    repair_config()