#!/bin/bash

# Directories
BASE_DIR="/Volumes/WINDOC/raspi_doctor"
LOG_DIR="/var/log/ai_health"

echo "Step 1: Create directories and set permissions..."
sudo mkdir -p "$LOG_DIR"
sudo chown -R $(whoami):staff "$LOG_DIR"

echo "Step 2: Setup Python virtual environment and install requirements..."
cd "$BASE_DIR" || exit 1

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip

# Install requirements if the file exists
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    # Install default requirements
    pip install flask requests psutil pyyaml python-dotenv gpustat
fi

deactivate

echo "Step 3: Install Launch Agents..."
# Create Launch Agents directory if it doesn't exist
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCH_AGENTS_DIR"

# Copy Launch Agents
cat > "$LAUNCH_AGENTS_DIR/com.user.aidoctor.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.aidoctor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/$(whoami)/raspi_doctor/.venv/bin/python</string>
        <string>/Users/$(whoami)/raspi_doctor/app.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/$(whoami)/raspi_doctor</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>/Users/$(whoami)/raspi_doctor</string>
        <key>OLLAMA_HOST</key>
        <string>http://localhost:11434</string>
        <key>PORT</key>
        <string>8010</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/aidoctor.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/aidoctor.error.log</string>
</dict>
</plist>
EOF

cat > "$LAUNCH_AGENTS_DIR/com.user.ollama.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.ollama</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/ollama</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/ollama.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/ollama.error.log</string>
</dict>
</plist>
EOF

echo "Step 4: Load Launch Agents..."
# Unload if already loaded
launchctl unload "$LAUNCH_AGENTS_DIR/com.user.aidoctor.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/com.user.ollama.plist" 2>/dev/null || true

# Load the agents
launchctl load "$LAUNCH_AGENTS_DIR/com.user.aidoctor.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.user.ollama.plist"

echo "Step 5: Start services..."
launchctl start com.user.ollama
sleep 3
launchctl start com.user.aidoctor

echo "Step 6: Create startup script..."
cat > "$BASE_DIR/start_mac_doctor.sh" << 'START_EOF'
#!/bin/bash
# Start AI Doctor services on macOS

echo "Starting AI Doctor System on port 8010..."

# Start Ollama if not running
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "Starting Ollama..."
    launchctl start com.user.ollama
    sleep 5
fi

# Start web dashboard if not running
if ! launchctl list | grep -q com.user.aidoctor; then
    echo "Starting Web Dashboard..."
    launchctl start com.user.aidoctor
    sleep 3
fi

# Check if web dashboard is responding
if curl -s http://localhost:8010/api/summary > /dev/null; then
    echo "Web dashboard is running on port 8010"
else
    echo "Starting web dashboard manually..."
    source /Users/$(whoami)/raspi_doctor/.venv/bin/activate
    python /Users/$(whoami)/raspi_doctor/app.py &
    deactivate
fi

echo "AI Doctor system started!"
echo "Web Dashboard: http://localhost:8010"
echo "Ollama API: http://localhost:11434"
START_EOF

chmod +x "$BASE_DIR/start_mac_doctor.sh"

echo "Step 7: Create quick status check script..."
cat > "$BASE_DIR/status_mac_doctor.sh" << 'STATUS_EOF'
#!/bin/bash
# Check status of AI Doctor services

echo "=== AI Doctor Status ==="

# Check Ollama
echo "Ollama:"
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "  ✅ Running on port 11434"
else
    echo "  ❌ Not running"
fi

# Check Web Dashboard
echo "Web Dashboard:"
if curl -s http://localhost:8010/api/summary > /dev/null; then
    echo "  ✅ Running on port 8010"
else
    echo "  ❌ Not running"
fi

# Check Launch Agents
echo "Launch Agents:"
if launchctl list | grep -q com.user.ollama; then
    echo "  ✅ Ollama agent loaded"
else
    echo "  ❌ Ollama agent not loaded"
fi

if launchctl list | grep -q com.user.aidoctor; then
    echo "  ✅ AI Doctor agent loaded"
else
    echo "  ❌ AI Doctor agent not loaded"
fi
STATUS_EOF

chmod +x "$BASE_DIR/status_mac_doctor.sh"

echo "Setup complete!"
echo "To start manually: ./start_mac_doctor.sh"
echo "To check status: ./status_mac_doctor.sh"
echo "Web Dashboard: http://localhost:8010"