#!/bin/bash
#
# WMS Catalog Scraper - Weekly Run Script
# Run via cron every Sunday at 02:00 SAST (00:00 UTC)
#
# Crontab entry:
# 0 0 * * 0 /opt/wms-catalog-scraper/scripts/run_weekly.sh
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
VENV_DIR="$PROJECT_DIR/venv"
DATE_STAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/weekly_$DATE_STAMP.log"

# Create log directory
mkdir -p "$LOG_DIR"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "WMS Catalog Scraper - Weekly Run"
log "=========================================="

# Navigate to project directory
cd "$PROJECT_DIR"

# Activate virtual environment
if [ -d "$VENV_DIR" ]; then
    log "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
else
    log "WARNING: Virtual environment not found at $VENV_DIR"
    log "Using system Python"
fi

# Load environment variables
if [ -f "$PROJECT_DIR/.env" ]; then
    log "Loading environment variables..."
    export $(cat "$PROJECT_DIR/.env" | grep -v '^#' | xargs)
else
    log "ERROR: .env file not found at $PROJECT_DIR/.env"
    exit 1
fi

# Run scraper
log "Starting scraper..."
python -m src.scraper scrape --supplier all --headless --notify 2>&1 | tee -a "$LOG_FILE"

# Check exit code
EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    log "✓ Scraper completed successfully"
else
    log "✗ Scraper failed with exit code $EXIT_CODE"
fi

log "=========================================="
log "Weekly run complete"
log "Log file: $LOG_FILE"
log "=========================================="

exit $EXIT_CODE
