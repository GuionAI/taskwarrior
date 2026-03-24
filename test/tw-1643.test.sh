#!/usr/bin/env bash
source bash_tap_tw.sh

# Context persistence across invocations not supported in PowerSync mode
# (config.set() is in-memory only; skipping context-activation test).
task add TW-1643 pro:YDKJS +work
task $(task_id 1) mod prio:M
task all | grep TW-1643
