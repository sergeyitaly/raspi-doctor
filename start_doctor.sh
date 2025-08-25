#!/bin/bash
cd /Volumes/WINDOC/raspi_doctor

echo "Starting AI Doctor System..."

# Check if Ollama is already running
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "Starting Ollama..."
    
    # Try different locations
    if [ -f "/Applications/Ollama.app/Contents/MacOS/ollama" ]; then
        /Applications/Ollama.app/Contents/MacOS/ollama serve &
    elif [ -f "./Ollama.app/Contents/MacOS/ollama" ]; then
        ./Ollama.app/Contents/MacOS/ollama serve &
    elif [ -f "./ollama_temp/Ollama.app/Contents/MacOS/ollama" ]; then
        ./ollama_temp/Ollama.app/Contents/MacOS/ollama serve &
    else
        echo "Ollama not found. Please download and extract it first."
        echo "Run: curl -OL https://ollama.ai/download/Ollama-darwin.zip && unzip Ollama-darwin.zip -d ollama_temp"
        exit 1
    fi
    
    # Wait for Ollama to start
    sleep 8
fi

# Pull a small model (if not already present)
echo "Checking for AI models..."
curl -s http://localhost:11434/api/tags | grep -q phi3 || {
    echo "Downloading phi3:mini model..."
    ./ollama_temp/Ollama.app/Contents/MacOS/ollama pull phi3:mini
}

# Start web application
echo "Starting web dashboard on port 8010..."
source .venv/bin/activate
export FLASK_ENV=development
python app.py
