#!/bin/bash
LOG_DIR="/var/log/ai_health"
mkdir -p $LOG_DIR

DATE=$(date '+%Y-%m-%d %H:%M:%S')

### --- Network Check ---
PING_TARGET="8.8.8.8"
if ping -c 2 -W 2 $PING_TARGET > /dev/null; then
    LAT=$(ping -c 1 $PING_TARGET | awk -F'time=' '/time=/{print $2}')
    echo "$DATE - NET OK - latency=$LAT" >> $LOG_DIR/network.log
else
    echo "$DATE - NET FAIL - no response" >> $LOG_DIR/network.log
fi

### --- Security Check ---
FAILED=$(grep "Failed password" /var/log/auth.log | tail -n 200 | wc -l)
TOP_IP=$(grep "Failed password" /var/log/auth.log | tail -n 200 | awk '{print $(NF-3)}' | sort | uniq -c | sort -nr | head -1)
UFW=$(grep "BLOCK" /var/log/ufw.log | tail -n 5)

{
  echo "[$DATE]"
  echo "Failed SSH logins: $FAILED"
  echo "Top attacker: $TOP_IP"
  echo "Recent UFW blocks:"
  echo "$UFW"
  echo "---"
} >> $LOG_DIR/security.log

### --- Hardware Health ---
CPU_TEMP=$(vcgencmd measure_temp | cut -d= -f2)
CPU_LOAD=$(uptime | awk -F'load average:' '{print $2}' | xargs)
MEMORY_USED=$(free -m | awk '/Mem:/ {print $3}')
MEMORY_TOTAL=$(free -m | awk '/Mem:/ {print $2}')
DISK=$(df -h / | awk 'NR==2 {print $3 " used / " $2 " total (" $5 " full)"}')
SD_ERRORS=$(dmesg | grep -i mmc | tail -n 5)

{
  echo "[$DATE]"
  echo "CPU Temp: $CPU_TEMP"
  echo "CPU Load: $CPU_LOAD"
  echo "Memory: $MEMORY_USED MB used / $MEMORY_TOTAL MB total"
  echo "Disk: $DISK"
  echo "SD Card Errors:"
  echo "$SD_ERRORS"
  echo "---"
} >> $LOG_DIR/hardware.log

### --- Auto-Healing ---

# 1. Restart failed services
FAILED_SERVICES=$(systemctl --failed --no-legend | awk '{print $1}')
for svc in $FAILED_SERVICES; do
    echo "$DATE - Restarting failed service: $svc" >> $LOG_DIR/actions.log
    systemctl restart $svc
done

# 2. Free memory if usage > 80%
MEM_USAGE_PERCENT=$(( MEMORY_USED * 100 / MEMORY_TOTAL ))
if [ $MEM_USAGE_PERCENT -ge 80 ]; then
    echo "$DATE - High memory usage ($MEM_USAGE_PERCENT%), clearing page cache" >> $LOG_DIR/actions.log
    sync; echo 3 > /proc/sys/vm/drop_caches
fi

# 3. Optional: Auto-update security packages if available
echo "$DATE - Running apt update & upgrade" >> $LOG_DIR/actions.log
apt-get update -y && apt-get upgrade -y
