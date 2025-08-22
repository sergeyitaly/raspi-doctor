#!/bin/bash

# Directories
BASE_DIR="/opt/pi-health-ai"
LOG_DIR="/var/log/ai_health"
SYSTEMD_DIR="$BASE_DIR/systemd"

echo "Step 1: Create directories and set ownership..."
sudo mkdir -p "$BASE_DIR" "$LOG_DIR"
sudo chown -R $USER:$USER "$BASE_DIR" "$LOG_DIR"

echo "Step 2: Copy scripts to /usr/local/bin and set permissions..."
cp "$BASE_DIR/collect_health.py" /usr/local/bin/collect_health.py
sudo chmod +x /usr/local/bin/collect_health.py

sudo chmod +x /usr/local/bin/raspi_doctor.sh
sudo chmod +x /usr/local/bin/netcheck.sh
sudo chmod +x /usr/local/bin/secscan.sh

# Also make collector.py executable if present
if [ -f "$BASE_DIR/collector.py" ]; then
    chmod +x "$BASE_DIR/collector.py"
    echo "Made collector.py executable"
fi

echo "Step 3: Setup Python virtual environment and install requirements..."
cd "$BASE_DIR" || exit 1
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
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

echo "Step 5: Reload systemd..."
sudo systemctl daemon-reload

echo "Step 6: Enable and start all timers..."
for timer in collect_health.timer raspi_doctor.timer netcheck.timer secscan.timer; do
    sudo systemctl enable --now "$timer"
    echo "Enabled and started $timer"
done

echo "Setup complete. Active timers:"
systemctl list-timers --all | grep -E "collect_health|raspi_doctor|netcheck|secscan"
