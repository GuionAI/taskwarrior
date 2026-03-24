#!/usr/bin/env bash
. bash_tap_tw.sh

# This problems only appears for "modify", not for "add"
# The 'proj:mod' is interpreted as 'proj:modified', then DOM lookup substitutes
# the 'modified' date.
task add a
task $(task_id 1) mod proj:mod
task $(task_id 1) _project | grep mod
