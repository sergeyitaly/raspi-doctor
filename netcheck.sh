#!/bin/bash
LOG_DIR="/var/log/ai_health"
mkdir -p $LOG_DIR
LOG_FILE="$LOG_DIR/network.log"

PING_TARGET="8.8.8.8"   # Google DNS
DATE=$(date '+%Y-%m-%d %H:%M:%S')

if ping -c 2 -W 2 $PING_TARGET > /dev/null; then
    LAT=$(ping -c 1 $PING_TARGET | awk -F'time=' '/time=/{print $2}')
    echo "$DATE - OK - latency=$LAT" >> $LOG_FILE
else
    echo "$DATE - FAIL - no response" >> $LOG_FILE
fi
