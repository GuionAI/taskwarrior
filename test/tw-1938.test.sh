#!/usr/bin/env bash
# Ref: https://github.com/GothenburgBitFactory/taskwarrior/issues/1938

. bash_tap_tw.sh

# Add a task with two annotations with the same entry value
echo '{"description": "my description", "annotations": [{"entry": "20170813T120000Z", "description": "first"}, {"entry": "20170813T120000Z", "description": "second"}]}' | task import -

# Check that the task has 2 annotations
ID=$(task_id 1)
[[ `task _get ${ID}.annotations.count` == 2 ]]
