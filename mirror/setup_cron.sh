#!/bin/bash
# Sets up cron jobs for mirror daily and weekly runners.
# Run once: bash setup_cron.sh
# Safe to re-run -- removes existing mirror cron entries before adding.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON=/usr/local/bin/python3
LOG_DIR="$SCRIPT_DIR/../../mirror-outputs/logs"

mkdir -p "$LOG_DIR"

# Remove any existing mirror cron entries
crontab -l 2>/dev/null | grep -v "mirror" | crontab -

# Add new entries
(crontab -l 2>/dev/null; cat <<EOF
# mirror daily runner -- midnight every day
0 0 * * * cd "$SCRIPT_DIR" && $PYTHON daily_runner.py >> "$LOG_DIR/daily.log" 2>&1

# mirror weekly runner -- sunday midnight
0 0 * * 0 cd "$SCRIPT_DIR" && $PYTHON weekly_runner.py >> "$LOG_DIR/weekly.log" 2>&1
EOF
) | crontab -

echo "Cron jobs installed:"
crontab -l | grep mirror
