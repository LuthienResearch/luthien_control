#!/bin/bash

# Basic log rotation script for development_log.md

LOG_DIR="dev"
LOG_FILE="$LOG_DIR/development_log.md"
ARCHIVE_DIR="$LOG_DIR/log_archive"
MAX_LINES=1000 # Rotate when the log exceeds this many lines
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ARCHIVE_FILE="$ARCHIVE_DIR/development_log_$TIMESTAMP.md.gz"

# Ensure log directory exists
if [ ! -d "$LOG_DIR" ]; then
    echo "Log directory $LOG_DIR not found. Exiting."
    exit 1
fi

# Ensure log file exists, create if not
if [ ! -f "$LOG_FILE" ]; then
    echo "# Development Log - $(date)" > "$LOG_FILE"
    echo "Log file $LOG_FILE created."
fi

# Count lines in the current log file
CURRENT_LINES=$(wc -l < "$LOG_FILE")

# Check if rotation is needed
if [ "$CURRENT_LINES" -gt "$MAX_LINES" ]; then
    echo "Log file $LOG_FILE has $CURRENT_LINES lines, exceeding max $MAX_LINES. Rotating..."

    # Ensure archive directory exists
    mkdir -p "$ARCHIVE_DIR"

    # Compress and move the current log file to the archive
    gzip -c "$LOG_FILE" > "$ARCHIVE_FILE"
    if [ $? -eq 0 ]; then
        echo "Archived log to $ARCHIVE_FILE"

        # Create a new log file with a continuation header
        echo "# Development Log - $(date) (Continued from $ARCHIVE_FILE)" > "$LOG_FILE"
        echo "Created new log file $LOG_FILE."
    else
        echo "Error: Failed to archive log file. Rotation aborted."
        exit 1
    fi
fi

# print a timestamp
echo "$(date '+%Y-%m-%d %H:%M')"

exit 0
