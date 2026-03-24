#!/usr/bin/env bash
. bash_tap_tw.sh

# Setup the tasks
task add Something I did yesterday
ID=$(task_id 1)
task $ID mod start:yesterday+18h
task $ID done end:yesterday+20h

# Check that 2 hour interval is reported by task info
task $ID info | grep -F "Start deleted"
[[ ! -z `task $ID info | grep -F "Start deleted (duration: 2:00:00)."` ]]
