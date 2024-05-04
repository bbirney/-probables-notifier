#!/bin/bash

# Set up environment variables or necessary paths
set -a
source .env
set +a

# setup cronjob
# ┌───────────── min (0 - 59)
# │ ┌────────────── hour (0 - 23)
# │ │ ┌─────────────── day of month (1 - 31)
# │ │ │ ┌──────────────── month (1 - 12)
# │ │ │ │ ┌───────────────── day of week (0 - 7) (Sunday to Saturday; 7 is also Sunday)
# │ │ │ │ │
# │ │ │ │ │
SCRIPT_PATH="$PROBABLES_ROOT_DIR"run_fetch.sh
(crontab -l 2>/dev/null; echo "0,30 * * * * $SCRIPT_PATH") | crontab -
