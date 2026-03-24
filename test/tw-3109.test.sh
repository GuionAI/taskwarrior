#!/usr/bin/env bash
. bash_tap_tw.sh

task add emptyval
ID=$(task_id 1)
task $ID done
task $ID mod end: status:pending
task_end=`task $ID info | grep ^End | sed -e 's/^End //' || true`
echo "task_end: $task_end"

# `task mod end:` should have deleted the end.
[[ "$task_end" == "" ]]
