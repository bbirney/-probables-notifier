#!/bin/bash
set -a  # Automatically export all variables
source .env
set +a  # Stop automatically exporting
cd $PROBABLES_ROOT_DIR
/opt/homebrew/bin/python3 fetch_data.py