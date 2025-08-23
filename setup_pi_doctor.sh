#!/bin/bash

# Directories
BASE_DIR="/home/pi/raspi-doctor"
LOG_DIR="/var/log/ai_health"
SYSTEMD_DIR="$BASE_DIR"

echo "Step 1: Create directories and set ownership..."
sudo mkdir -p "$LOG_DIR"
sudo chown -R $USER:$USER "$LOG_DIR"

echo "Step 2: Copy scripts to /usr/local/bin and set permissions..."
# Copy Python script
if [ -f "$BASE_DIR/collect_health.py" ]; then
    sudo cp "$BASE_DIR/collect_health.py" /usr/local/bin/
    sudo chmod +x /usr/local/bin/collect_health.py
    echo "Copied collect_health.py"
else
    echo "WARNING: collect_health.py not found in $BASE_DIR"
fi

# Copy shell scripts
for script in raspi_doctor.sh netcheck.sh secscan.sh; do
    if [ -f "$BASE_DIR/$script" ]; then
        sudo cp "$BASE_DIR/$script" /usr/local/bin/
        sudo chmod +x "/usr/local/bin/$script"
        echo "Copied $script"
    else
        echo "WARNING: $script not found in $BASE_DIR"
    fi
done

echo "Step 3: Setup Python virtual environment and install requirements..."
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
    pip install flask requests psutil pyyaml python-dotenv
fi

deactivate

echo "Step 4: Copy systemd unit files to /etc/systemd/system/..."
for unit in collect_health.service collect_health.timer \
            raspi_doctor.service raspi_doctor.timer \
            netcheck.service netcheck.timer \
            secscan.service secscan.timer; do
    if [ -f "$SYSTEMD_DIR/$unit" ]; then
        sudo cp "$SYSTEMD_DIR/$unit" /etc/systemd/system/
        echo "Copied $unit"
    else
        echo "WARNING: $unit not found in $SYSTEMD_DIR"
    fi
done

echo "Step 5: Setup web dashboard service on port 8010..."
sudo tee /etc/systemd/system/pi-doctor-web.service > /dev/null << 'WEB_EOF'
[Unit]
Description=Pi Doctor Web Dashboard
After=network.target ollama.service
Wants=network.target ollama.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/raspi-doctor
Environment=PYTHONPATH=/home/pi/raspi-doctor
Environment=OLLAMA_HOST=http://localhost:11434
Environment=PORT=8010
ExecStart=/home/pi/raspi-doctor/.venv/bin/python /home/pi/raspi-doctor/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
WEB_EOF

echo "Step 5b: Setup Ollama service..."
# autodetect path to ollama
OLLAMA_BIN=$(command -v ollama || echo "/usr/local/bin/ollama")
sudo tee /etc/systemd/system/ollama.service > /dev/null << OLLAMA_EOF
[Unit]
Description=Ollama Server
After=network.target

[Service]
Type=simple
User=pi
Group=pi
ExecStart=$OLLAMA_BIN serve
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
OLLAMA_EOF

echo "Step 6: Reload systemd..."
sudo systemctl daemon-reload

echo "Step 7: Enable and start all timers and services..."
for timer in collect_health.timer raspi_doctor.timer netcheck.timer secscan.timer; do
    if [ -f "/etc/systemd/system/$timer" ]; then
        sudo systemctl enable --now "$timer"
        echo "Enabled and started $timer"
    else
        echo "WARNING: $timer not found, skipping"
    fi
done

# Enable and start ollama
sudo systemctl enable ollama.service
sudo systemctl start ollama.service
echo "Enabled and started ollama.service"

# Enable and start web service
sudo systemctl enable pi-doctor-web.service
sudo systemctl start pi-doctor-web.service
echo "Enabled and started pi-doctor-web.service on port 8010"

echo "Step 8: Create startup script..."
cat > "$BASE_DIR/start_pi_doctor.sh" << 'START_EOF'
#!/bin/bash
# Start all Pi Doctor services on port 8010

echo "Starting Pi Doctor System on port 8010..."

# Start Ollama if not running
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "Starting Ollama..."
    sudo systemctl start ollama.service
    sleep 5
fi

# Start web dashboard on port 8010 if not running
if ! systemctl is-active --quiet pi-doctor-web.service; then
    echo "Starting Web Dashboard on port 8010..."
    sudo systemctl start pi-doctor-web.service
    sleep 3
fi

# Check if web dashboard is responding on port 8010
if curl -s http://localhost:8010/api/summary > /dev/null; then
    echo "Web dashboard is running on port 8010"
else
    echo "Warning: Web dashboard not responding on port 8010"
fi

# Run enhanced doctor once
echo "Running Enhanced Doctor..."
./enhanced_doctor.py

echo "Pi Doctor system started!"
echo "Web Dashboard: http://$(hostname -I | awk '{print $1}'):8010"
echo "Ollama API: http://localhost:11434"
START_EOF

chmod +x "$BASE_DIR/start_pi_doctor.sh"

echo "Setup complete. Checking services:"
echo "Active timers:"
systemctl list-timers --all | grep -E "collect_health|raspi_doctor|netcheck|secscan" || echo "No timers found"

echo "Web service status:"
sudo systemctl status pi-doctor-web.service --no-pager -l | head -10
