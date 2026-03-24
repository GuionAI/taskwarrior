#!/usr/bin/env bash
. bash_tap_tw.sh

# TW-2392: project names with dots and numbers should parse correctly
task add test project:c.vs.2021-01

# Show the problem in TAP output
task rc.debug.parser:3 project:c.vs.2021-01 _ids

# Verify the task with this project is found (returns a non-empty hex ID)
[[ ! -z `task project:c.vs.2021-01 _ids` ]]

# Same thing now, but with 11 instead of 01
task add test project:c.vs.2021-11

# Show the problem in TAP output
task rc.debug.parser:3 project:c.vs.2021-11 _ids

# Verify the task with this project is found
[[ ! -z `task project:c.vs.2021-11 _ids` ]]
