#!/bin/bash
# demo.sh - Example process for macpmd
# Prints a message every 3 seconds for 1 minute then exits.

for i in $(seq 1 6); do
    echo "[$(date '+%H:%M:%S')] Hello from demo process (tick $i/6)"
    sleep 3
done

echo "[$(date '+%H:%M:%S')] Demo process finished."
