#!/bin/bash

LOG_DIR="log"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/backend_$TIMESTAMP.log"

# Check if port 5001 is already in use
if lsof -i :5001 >/dev/null; then
    echo "Error: Port 5001 is already in use. Please stop the process using it before starting the backend."
    echo "You can find the process with: lsof -i :5001"
    echo "And kill it with: kill -9 <PID> or taskkill /PID <PID> /F (Windows)"
    exit 1
fi

echo "Starting backend service..."
echo "Logs will be saved to: $LOG_FILE"

# Activate conda environment and run the app in the background
# Use 'nohup' to ensure it runs even if the terminal is closed
# Source conda.sh to make 'conda activate' available
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate arxiv-subscribe

# Run the Python app in the background, redirecting output
nohup python backend/app.py > "$LOG_FILE" 2>&1 &

# Get the PID of the background process
PID=$!

echo "Backend started with PID: $PID"
echo "You can tail the log file to see real-time output: tail -f $LOG_FILE"

# Deactivate conda environment in the current shell (optional, as nohup detaches)
# conda deactivate