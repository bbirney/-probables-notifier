#!/bin/bash
set -a  # Automatically export all variables
source .env
set +a  # Stop automatically exporting
cd $PROBABLES_ROOT_DIR
#!/bin/bash
NOW=$(date +"%Y-%m-%d %H:%M:%S")
echo "Starting execution at $NOW" >> log.txt
/opt/homebrew/bin/python3 fetch_data.py >> log.txt 2>> error.txt
NOW=$(date +"%Y-%m-%d %H:%M:%S")
echo "Finished execution at $NOW" >> log.txt