#!/home/pi/raspi-doctor/.venv/bin/python3
# repair_cloudflared.py

import subprocess
import yaml
from pathlib import Path

def repair_cloudflared_config():
    print("=== Repairing Cloudflare Tunnel Config ===")
    
    config_path = Path("/home/pi/.cloudflared/config.yml")
    backup_path = Path("/home/pi/.cloudflared/config.yml.backup")
    
    # Backup current config
    if config_path.exists():
        subprocess.run(f"cp {config_path} {backup_path}", shell=True)
        print(f"✓ Backed up config to {backup_path}")
    
    # Check if config exists and is valid
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                content = f.read()
            
            # Try to parse YAML
            yaml.safe_load(content)
            print("✓ Current config is valid YAML")
            return True
            
        except yaml.YAMLError as e:
            print(f"✗ YAML error in current config: {e}")
            print("Content that caused error:")
            print(content)
            
            # Create a simple valid config
            simple_config = """# Cloudflare Tunnel configuration
# Replace with your actual tunnel ID and credentials path
tunnel: YOUR_TUNNEL_ID_HERE
credentials-file: /home/pi/.cloudflared/YOUR_TUNNEL_ID_HERE.json

# Optional: Configure ingress rules
ingress:
  - hostname: your-domain.example.com
    service: http://localhost:3000
  - service: http-status:404
"""
            
            with open(config_path, "w") as f:
                f.write(simple_config)
            
            print("✓ Created simple valid config template")
            print("Please edit with your actual tunnel ID and credentials")
            
    else:
        # Create config directory and file
        config_path.parent.mkdir(exist_ok=True)
        
        simple_config = """# Cloudflare Tunnel configuration
tunnel: YOUR_TUNNEL_ID_HERE
credentials-file: /home/pi/.cloudflared/YOUR_TUNNEL_ID_HERE.json
"""
        
        with open(config_path, "w") as f:
            f.write(simple_config)
        
        print("✓ Created new config file with template")
        print("Please edit with your actual tunnel ID and credentials")
    
    return True

if __name__ == "__main__":
    repair_cloudflared_config()