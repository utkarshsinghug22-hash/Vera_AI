#!/bin/bash

echo "Starting Vera Bot setup..."

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "pip3 not found, installing via get-pip.py..."
    curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    python3 get-pip.py --user --break-system-packages
fi

# Add local bin to PATH just in case
export PATH=$PATH:$HOME/.local/bin

# Install requirements
echo "Installing dependencies..."
python3 -m pip install --user --break-system-packages fastapi "uvicorn[standard]" httpx pydantic python-dotenv

# Start the server in the background
echo "Starting FastAPI server on port 8080..."
python3 -m uvicorn main:app --host 0.0.0.0 --port 8080 &
SERVER_PID=$!

echo "Waiting for server to start..."
sleep 5

# Run the judge simulator
echo "Running Judge Simulator..."
cd ..
export BOT_URL="http://localhost:8080"
python3 judge_simulator.py

# Cleanup after judge finishes
echo "Cleaning up..."
kill $SERVER_PID
echo "Done."
