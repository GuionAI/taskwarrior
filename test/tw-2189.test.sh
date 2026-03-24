#!/usr/bin/env bash
. bash_tap_tw.sh

task add "foo \' bar"
task list

# Assert the task was correctly added
[[ ! -z `task list | grep "foo ' bar"` ]]
ID1=$(task_id 1)
[[ `task _get ${ID1}.description` == "foo ' bar" ]]

# Bonus: Assert escaped double quotes are also handled correctly
task add 'foo \" bar'
task list

# Assert the task was correctly added
[[ ! -z `task list | grep 'foo " bar'` ]]
ID2=$(task_id 2)
[[ `task _get ${ID2}.description` == 'foo " bar' ]]
