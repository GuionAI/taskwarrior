#!/usr/bin/env bash
. bash_tap_tw.sh

# TW-1718: String UDA values that look like durations should not be parsed as durations
# Use rc overrides to ensure UDA config is applied before argument parsing
task rc.uda.foo.label:foo rc.uda.foo.type:string add bar foo:"3h+10h"
ID=$(task_id 1)

# Show the problem in TAP output
task rc.uda.foo.label:foo rc.uda.foo.type:string _get ${ID}.foo

task rc.uda.foo.label:foo rc.uda.foo.type:string _get ${ID}.foo | grep '3h+10h'
