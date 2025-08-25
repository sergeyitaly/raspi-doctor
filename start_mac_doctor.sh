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
