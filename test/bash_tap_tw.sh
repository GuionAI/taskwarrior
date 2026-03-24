#!/usr/bin/env bash
# This file only contains helper functions for making Taskwarrior testing
# easier. The magic happens in bash_tap.sh sourced at the end of this file.
#
# "task" is a bash function calling "/path/to/compiled/task rc:taskrc"
# Only local paths are searched, see bash_tap_tw.sh:find_task_binary().
#
# "taskrc" is a file set up in bash_tap_tw.sh:setup_taskrc(), and can be
# appended to or changed as needed.
#
# Subject to the MIT License. See LICENSE file or https://opensource.org/licenses/MIT
# Copyright (c) 2015 - 2021, Wilhelm Schürmann

function setup_taskrc {
    # Configuration
    for i in taskchampion.sqlite3 taskrc powersync.db; do
       if [ -f "$i" ]; then
           rm "$i" 2>&1 >/dev/null
       fi
    done

    export TASKDATA=.

    echo 'confirmation=off'               > taskrc
    echo 'color.debug=rgb025'             >> taskrc
    echo 'color.header=rgb025'            >> taskrc
    echo 'color.footer=rgb025'            >> taskrc
    echo 'color.error=bold white on red'  >> taskrc
    echo 'news.version=99.0.0'            >> taskrc

    # Set up PowerSync SQLite storage backend
    export POWERSYNC_DB_PATH="$(pwd)/powersync.db"
    export POWERSYNC_USER_ID="00000000-0000-0000-0000-000000000000"

    sqlite3 "$POWERSYNC_DB_PATH" <<'SCHEMA'
CREATE TABLE IF NOT EXISTS tc_tasks_data (
    id TEXT PRIMARY KEY, user_id TEXT, data TEXT NOT NULL DEFAULT '{}',
    entry_at TEXT, status TEXT, description TEXT, priority TEXT,
    modified_at TEXT, due_at TEXT, scheduled_at TEXT, start_at TEXT,
    end_at TEXT, wait_at TEXT, parent_id TEXT, position TEXT, project_id TEXT
);
CREATE VIEW IF NOT EXISTS tc_tasks AS
    SELECT id, user_id, data, entry_at, status, description, priority,
           modified_at, due_at, scheduled_at, start_at, end_at, wait_at,
           parent_id, position, project_id
    FROM tc_tasks_data;
CREATE TRIGGER IF NOT EXISTS tc_tasks_insert
    INSTEAD OF INSERT ON tc_tasks BEGIN
        INSERT OR REPLACE INTO tc_tasks_data
            (id, user_id, data, entry_at, status, description, priority,
             modified_at, due_at, scheduled_at, start_at, end_at, wait_at,
             parent_id, position, project_id)
        VALUES (NEW.id, NEW.user_id, COALESCE(NEW.data, '{}'), NEW.entry_at,
                NEW.status, NEW.description, NEW.priority, NEW.modified_at,
                NEW.due_at, NEW.scheduled_at, NEW.start_at, NEW.end_at,
                NEW.wait_at, NEW.parent_id, NEW.position, NEW.project_id);
    END;
CREATE TRIGGER IF NOT EXISTS tc_tasks_update
    INSTEAD OF UPDATE ON tc_tasks BEGIN
        UPDATE tc_tasks_data SET
            user_id = NEW.user_id, data = COALESCE(NEW.data, '{}'),
            entry_at = NEW.entry_at, status = NEW.status,
            description = NEW.description, priority = NEW.priority,
            modified_at = NEW.modified_at, due_at = NEW.due_at,
            scheduled_at = NEW.scheduled_at, start_at = NEW.start_at,
            end_at = NEW.end_at, wait_at = NEW.wait_at,
            parent_id = NEW.parent_id, position = NEW.position,
            project_id = NEW.project_id
        WHERE id = OLD.id;
    END;
CREATE TRIGGER IF NOT EXISTS tc_tasks_delete
    INSTEAD OF DELETE ON tc_tasks BEGIN
        DELETE FROM tc_tasks_data WHERE id = OLD.id;
    END;
CREATE TABLE IF NOT EXISTS tc_operations (
    id TEXT PRIMARY KEY, user_id TEXT, data TEXT NOT NULL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY, name TEXT, user_id TEXT,
    created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);
CREATE TABLE IF NOT EXISTS tc_tags (
    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, user_id TEXT,
    name TEXT NOT NULL, UNIQUE (task_id, name)
);
CREATE TABLE IF NOT EXISTS tc_annotations (
    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, user_id TEXT,
    entry_at TEXT NOT NULL, description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tc_working_set (
    uuid TEXT PRIMARY KEY
);
SCHEMA
}

function find_task_binary {
    # $bashtap_org_pwd is set in bash_tap.sh. It is the directory the parent script is
    # run from. Check for the task binary relative to that directory.
    # Do not use the system "task" if no local one is found, error out instead.
    for t in "${bashtap_org_pwd}/task" "${bashtap_org_pwd}/src/task" "${bashtap_org_pwd}/../task" "${bashtap_org_pwd}/../src/task" "${bashtap_org_pwd}/../build/src/task"; do
        if [ -f "$t" ] && [ -x "$t" ]; then
            t_abs=$(bashtap_get_absolute_path "$t")
            eval "function task { '${t_abs}' rc:taskrc \"\$@\"; }"
            return 0
        fi
    done

    echo "# ERROR: Could not find task binary!"

    # Needed for normal, i.e. "non-test" mode.
    eval "function task { exit; }"

    # Set $line so we can have useful TAP output.
    line="bash_tap.sh:find_task_binary()"

    return 1
}

function task_id {
    # Return the 8-char hex ID of the Nth task added (1-based, by entry_at order).
    # Usage: ID=$(task_id 1)
    local n="${1:-1}"
    sqlite3 "$POWERSYNC_DB_PATH" \
        "SELECT SUBSTR(id,1,8) FROM tc_tasks_data \
         WHERE user_id='$POWERSYNC_USER_ID' \
         ORDER BY entry_at LIMIT 1 OFFSET $((n-1));"
}

function reset_taskdb {
    # Delete and re-initialize the PowerSync database (used by tests that simulate data loss).
    rm -f "$POWERSYNC_DB_PATH"
    sqlite3 "$POWERSYNC_DB_PATH" <<'SCHEMA'
CREATE TABLE IF NOT EXISTS tc_tasks_data (
    id TEXT PRIMARY KEY, user_id TEXT, data TEXT NOT NULL DEFAULT '{}',
    entry_at TEXT, status TEXT, description TEXT, priority TEXT,
    modified_at TEXT, due_at TEXT, scheduled_at TEXT, start_at TEXT,
    end_at TEXT, wait_at TEXT, parent_id TEXT, position TEXT, project_id TEXT
);
CREATE VIEW IF NOT EXISTS tc_tasks AS
    SELECT id, user_id, data, entry_at, status, description, priority,
           modified_at, due_at, scheduled_at, start_at, end_at, wait_at,
           parent_id, position, project_id
    FROM tc_tasks_data;
CREATE TRIGGER IF NOT EXISTS tc_tasks_insert
    INSTEAD OF INSERT ON tc_tasks BEGIN
        INSERT OR REPLACE INTO tc_tasks_data
            (id, user_id, data, entry_at, status, description, priority,
             modified_at, due_at, scheduled_at, start_at, end_at, wait_at,
             parent_id, position, project_id)
        VALUES (NEW.id, NEW.user_id, COALESCE(NEW.data, '{}'), NEW.entry_at,
                NEW.status, NEW.description, NEW.priority, NEW.modified_at,
                NEW.due_at, NEW.scheduled_at, NEW.start_at, NEW.end_at,
                NEW.wait_at, NEW.parent_id, NEW.position, NEW.project_id);
    END;
CREATE TRIGGER IF NOT EXISTS tc_tasks_update
    INSTEAD OF UPDATE ON tc_tasks BEGIN
        UPDATE tc_tasks_data SET
            user_id = NEW.user_id, data = COALESCE(NEW.data, '{}'),
            entry_at = NEW.entry_at, status = NEW.status,
            description = NEW.description, priority = NEW.priority,
            modified_at = NEW.modified_at, due_at = NEW.due_at,
            scheduled_at = NEW.scheduled_at, start_at = NEW.start_at,
            end_at = NEW.end_at, wait_at = NEW.wait_at,
            parent_id = NEW.parent_id, position = NEW.position,
            project_id = NEW.project_id
        WHERE id = OLD.id;
    END;
CREATE TRIGGER IF NOT EXISTS tc_tasks_delete
    INSTEAD OF DELETE ON tc_tasks BEGIN
        DELETE FROM tc_tasks_data WHERE id = OLD.id;
    END;
CREATE TABLE IF NOT EXISTS tc_operations (
    id TEXT PRIMARY KEY, user_id TEXT, data TEXT NOT NULL,
    created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY, name TEXT, user_id TEXT,
    created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);
CREATE TABLE IF NOT EXISTS tc_tags (
    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, user_id TEXT,
    name TEXT NOT NULL, UNIQUE (task_id, name)
);
CREATE TABLE IF NOT EXISTS tc_annotations (
    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, user_id TEXT,
    entry_at TEXT NOT NULL, description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tc_working_set (
    uuid TEXT PRIMARY KEY
);
SCHEMA
}

function bashtap_setup {
    # This function is called by bash_tap.sh before running tests, or before
    # running the parent script normally.
    find_task_binary
    setup_taskrc
}


# Include the base script that does the actual work.
source bash_tap.sh
