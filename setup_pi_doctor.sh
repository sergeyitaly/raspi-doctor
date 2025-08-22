#!/bin/bash

# Directories - CORRECTED for your setup
BASE_DIR="/home/pi/raspi-doctor"
LOG_DIR="/var/log/ai_health"
SYSTEMD_DIR="$BASE_DIR"

echo "Step 1: Create directories and set ownership..."
sudo mkdir -p "$BASE_DIR" "$LOG_DIR"
sudo chown -R $USER:$USER "$BASE_DIR" "$LOG_DIR"

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
systemctl list-timers --all | grep -E "collect_health|raspi_doctor|netcheck|secscan" || echo "No timers found - check systemd unit files"