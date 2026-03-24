#!/usr/bin/env bash
. bash_tap_tw.sh

task add modtest modified:yesterday
ID=$(task_id 1)
old_modified=`task _get ${ID}.modified`
echo $old_modified

task $ID start
new_modified=`task _get ${ID}.modified`
echo $new_modified

# `task start` should have updated modified
[[ $old_modified != $new_modified ]]
