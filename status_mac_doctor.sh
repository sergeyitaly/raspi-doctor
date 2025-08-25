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
