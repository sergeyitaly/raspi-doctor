#!/bin/bash
# Directory where your systemd unit files currently reside
UNIT_SRC_DIR="/opt/pi-health-ai/systemd"

# Target systemd directory
UNIT_DST_DIR="/etc/systemd/system"

echo "Copying systemd unit files to $UNIT_DST_DIR..."

for unit in collect_health.service collect_health.timer \
            raspi_doctor.service raspi_doctor.timer \
            netcheck.service netcheck.timer \
            secscan.service secscan.timer; do
    if [ -f "$UNIT_SRC_DIR/$unit" ]; then
        sudo cp "$UNIT_SRC_DIR/$unit" "$UNIT_DST_DIR/"
        echo "Copied $unit"
    else
        echo "WARNING: $unit not found in $UNIT_SRC_DIR"
    fi
done

# Reload systemd daemon
echo "Reloading systemd..."
sudo systemctl daemon-reload

# Enable and start timers/services
for timer in collect_health.timer raspi_doctor.timer netcheck.timer secscan.timer; do
    echo "Enabling and starting $timer..."
    sudo systemctl enable --now "$timer"
done

# Optional: list active timers
echo "Active timers:"
systemctl list-timers --all | grep -E "collect_health|raspi_doctor|netcheck|secscan"
