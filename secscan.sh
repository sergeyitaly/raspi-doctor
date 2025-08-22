#!/bin/bash
LOG_DIR="/var/log/ai_health"
mkdir -p $LOG_DIR
LOG_FILE="$LOG_DIR/security.log"

DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Count failed SSH attempts
FAILED=$(grep "Failed password" /var/log/auth.log | tail -n 200 | wc -l)

# Top attacking IP
TOP_IP=$(grep "Failed password" /var/log/auth.log | tail -n 200 | awk '{print $(NF-3)}' | sort | uniq -c | sort -nr | head -1)

# UFW recent blocks
UFW=$(grep "BLOCK" /var/log/ufw.log | tail -n 5)

echo "[$DATE]" >> $LOG_FILE
echo "Failed SSH logins: $FAILED" >> $LOG_FILE
echo "Top attacker: $TOP_IP" >> $LOG_FILE
echo "Recent UFW blocks:" >> $LOG_FILE
echo "$UFW" >> $LOG_FILE
echo "---" >> $LOG_FILE
