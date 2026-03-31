////////////////////////////////////////////////////////////////////////////////
//
// Copyright 2006 - 2021, Tomas Babej, Paul Beckingham, Federico Hernandez.
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included
// in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
// OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
// THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.
//
// https://www.opensource.org/licenses/mit-license.php
//
////////////////////////////////////////////////////////////////////////////////

#include <cmake.h>
// cmake.h include header must come first

#include <Color.h>
#include <Context.h>
#include <Datetime.h>
#include <TDB2.h>
#include <Table.h>
#include <format.h>
#include <shared.h>
#include <stdlib.h>
#include <util.h>

#include <algorithm>
#include <set>
#include <unordered_set>
#include <vector>

bool TDB2::debug_mode = false;
static void dependency_scan(std::vector<Task>&);

// Keys that must never be written to TaskChampion storage:
//   uuid/id  — synthetic keys managed by tch itself
//   tags     — legacy comma-separated representation; tch-native tag_* keys carry the same data
//   depends  — legacy comma-separated representation; tch-native dep_* keys carry the same data
static const std::unordered_set<std::string> kTCSkippedKeys = {"uuid", "id", "tags", "depends"};

////////////////////////////////////////////////////////////////////////////////
void TDB2::open_replica(const std::string& db_path) {
  _replica = tc::new_replica_powersync(db_path);
  // Seed existing tags into the registry on first use after upgrade.
  // Idempotent: already-registered tags are skipped.
  replica()->seed_tags_from_tasks();
}

////////////////////////////////////////////////////////////////////////////////
void TDB2::open_replica_for_test() { _replica = tc::new_replica_for_test(); }

////////////////////////////////////////////////////////////////////////////////
// Add the new task to the replica.
void TDB2::add(Task& task) {
  // Ensure the task is consistent, and provide defaults if necessary.
  // bool argument to validate() is "applyDefault", to apply default values for
  // properties not otherwise given.
  task.validate(true);

  rust::Vec<tc::Operation> ops;
  maybe_add_undo_point(ops);

  auto uuid = task.get("uuid");
  changes[uuid] = task;
  tc::Uuid tcuuid = tc::uuid_from_string(uuid);

  // run hooks for this new task
  Context::getContext().hooks.onAdd(task);

  auto taskdata = tc::create_task(tcuuid, ops);

  // add the task attributes
  for (auto& attr : task.all()) {
    if (kTCSkippedKeys.count(attr)) {
      continue;
    }

    taskdata->update(attr, task.get(attr), ops);
  }
  replica()->commit_operations(std::move(ops));

  invalidate_cached_info();

  // Assign the 8-char hex UUID prefix as the task ID.
  task.id = (uuid.length() >= 8) ? uuid.substr(0, 8) : "";
}

////////////////////////////////////////////////////////////////////////////////
// Modify the task in storage to match the given task.
//
// Note that there are a few race conditions to consider here.  Taskwarrior
// loads the enitre task into memory and this method then essentially writes
// the entire task back to the database. So, if the task in the database
// changes between loading the task and this method being called, this method
// will "revert" those changes. In practice this would only occur when multiple
// `task` invocatoins run at the same time and try to modify the same task.
//
// There is also the possibility that another task process has deleted the task
// from the database between the time this process loaded the tsak and called
// this method. In this case, this method throws an error that will make sense
// to the user. This is especially unlikely since tasks are only deleted when
// they have been unmodified for a long time.
void TDB2::modify(Task& task) {
  // All locally modified tasks are timestamped, implicitly overwriting any
  // changes the user or hooks tried to apply to the "modified" attribute.
  task.setAsNow("modified");
  task.validate(false);
  auto uuid = task.get("uuid");

  rust::Vec<tc::Operation> ops;
  maybe_add_undo_point(ops);

  changes[uuid] = task;

  // invoke the hook and allow it to modify the task before updating
  Task original;
  get(uuid, original);
  Context::getContext().hooks.onModify(original, task);

  tc::Uuid tcuuid = tc::uuid_from_string(uuid);
  auto maybe_tctask = replica()->get_task_data(tcuuid);
  if (maybe_tctask.is_none()) {
    throw std::string("task no longer exists");
  }
  auto tctask = maybe_tctask.take();

  // Perform the necessary `update` operations to set all keys in `tctask`
  // equal to those in `task`.
  std::unordered_set<std::string> seen;
  for (auto k : task.all()) {
    if (kTCSkippedKeys.count(k)) {
      continue;
    }
    seen.insert(k);
    bool update = false;
    auto v_new = task.get(k);
    std::string v_tctask;
    if (tctask->get(k, v_tctask)) {
      update = v_tctask != v_new;
    } else {
      // tctask does not contain k, so update it
      update = true;
    }
    if (update) {
      // An empty string indicates the value should be removed.
      if (v_new == "") {
        tctask->update_remove(k, ops);
      } else {
        tctask->update(k, v_new, ops);
      }
    }
  }

  // we've now added and updated properties; but must find any deleted properties.
  // This sweep also acts as a migration: any stale "tags" or "depends" keys
  // written before this fix was deployed will be removed on the next modify().
  for (auto k : tctask->properties()) {
    auto kstr = static_cast<std::string>(k);
    if (seen.find(kstr) == seen.end()) {
      tctask->update_remove(kstr, ops);
    }
  }

  replica()->commit_operations(std::move(ops));

  invalidate_cached_info();
}

////////////////////////////////////////////////////////////////////////////////
void TDB2::purge(Task& task) {
  auto uuid = tc::uuid_from_string(task.get("uuid"));
  rust::Vec<tc::Operation> ops;
  auto maybe_tctask = replica()->get_task_data(uuid);
  if (maybe_tctask.is_some()) {
    auto tctask = maybe_tctask.take();
    tctask->delete_task(ops);
    replica()->commit_operations(std::move(ops));
  }

  invalidate_cached_info();
}

////////////////////////////////////////////////////////////////////////////////
rust::Box<tc::Replica>& TDB2::replica() {
  // One of the open_replica_ methods must be called before this one.
  assert(_replica);
  return _replica.value();
}

////////////////////////////////////////////////////////////////////////////////
void TDB2::maybe_add_undo_point(rust::Vec<tc::Operation>& ops) {
  // Only add an UndoPoint if there are not yet any changes.
  if (changes.size() == 0) {
    tc::add_undo_point(ops);
  }
}

////////////////////////////////////////////////////////////////////////////////
void TDB2::get_changes(std::vector<Task>& changes) {
  std::map<std::string, Task>& changes_map = this->changes;
  changes.clear();
  std::transform(changes_map.begin(), changes_map.end(), std::back_inserter(changes),
                 [](const auto& kv) { return kv.second; });
}

////////////////////////////////////////////////////////////////////////////////
void TDB2::expire_tasks() { replica()->expire_tasks(); }

////////////////////////////////////////////////////////////////////////////////
const std::vector<Task> TDB2::all_tasks() {
  Timer timer;
  auto all_tctasks = replica()->all_task_data();
  std::vector<Task> all;
  for (auto& maybe_tctask : all_tctasks) {
    auto tctask = maybe_tctask.take();
    all.push_back(Task(std::move(tctask)));
  }

  dependency_scan(all);

  Context::getContext().time_load_us += timer.total_us();
  return all;
}

////////////////////////////////////////////////////////////////////////////////
const std::vector<Task> TDB2::pending_tasks() {
  if (!_pending_tasks) {
    Timer timer;

    auto pending_tctasks = replica()->pending_task_data();
    std::vector<Task> result;
    for (auto& maybe_tctask : pending_tctasks) {
      auto tctask = maybe_tctask.take();
      result.push_back(Task(std::move(tctask)));
    }

    dependency_scan(result);

    Context::getContext().time_load_us += timer.total_us();
    _pending_tasks = result;
  }

  return *_pending_tasks;
}

////////////////////////////////////////////////////////////////////////////////
const std::vector<Task> TDB2::completed_tasks() {
  if (!_completed_tasks) {
    auto all_tctasks = replica()->all_task_data();

    std::string status_key = "status";
    std::vector<Task> result;
    for (auto& maybe_tctask : all_tctasks) {
      auto tctask = maybe_tctask.take();
      std::string status;
      tctask->get(status_key, status);
      // Include only explicitly completed or deleted tasks.
      if (status == "completed" || status == "deleted") {
        result.push_back(Task(std::move(tctask)));
      }
    }
    _completed_tasks = result;
  }
  return *_completed_tasks;
}

////////////////////////////////////////////////////////////////////////////////
void TDB2::invalidate_cached_info() {
  _pending_tasks = std::nullopt;
  _completed_tasks = std::nullopt;
}

////////////////////////////////////////////////////////////////////////////////
// Locate task by UUID, including by partial ID, wherever it is.
bool TDB2::get(const std::string& uuid, Task& task) {
  // Load all pending tasks in order to get dependency data, and in particular
  // `task.is_blocking` and `task.is_blocked`, set correctly.
  std::vector<Task> pending = pending_tasks();

  // try by raw uuid, if the length is right
  for (auto& pending_task : pending) {
    if (closeEnough(pending_task.get("uuid"), uuid, uuid.length())) {
      task = pending_task;
      return true;
    }
  }

  // Nothing to do but iterate over all tasks and check whether it's closeEnough.
  for (auto& maybe_tctask : replica()->all_task_data()) {
    auto tctask = maybe_tctask.take();
    auto tctask_uuid = static_cast<std::string>(tctask->get_uuid().to_string());
    if (closeEnough(tctask_uuid, uuid, uuid.length())) {
      task = Task{std::move(tctask)};
      return true;
    }
  }

  return false;
}

////////////////////////////////////////////////////////////////////////////////
// Resolve a UUID prefix (or full UUID) to the canonical full 36-char UUID.
// Uses get() which supports prefix matching via closeEnough(). Throws if not found.
std::string TDB2::resolve_uuid(const std::string& prefix) {
  Task t;
  if (!get(prefix, t)) throw std::string("Task '" + prefix + "' does not exist.");
  return t.get("uuid");
}

////////////////////////////////////////////////////////////////////////////////
// Locate task by UUID, wherever it is.
bool TDB2::has(const std::string& uuid) {
  return replica()->get_task_data(tc::uuid_from_string(uuid)).is_some();
}

////////////////////////////////////////////////////////////////////////////////
// Returns all tasks whose `parent` field matches parent_uuid (direct children).
const std::vector<Task> TDB2::children(const std::string& parent_uuid) {
  std::vector<Task> results;
  for (auto& task : all_tasks()) {
    if (task.get("parent_id") == parent_uuid) results.push_back(task);
  }
  return results;
}

////////////////////////////////////////////////////////////////////////////////
// Returns all descendants (children, grandchildren, etc.) of parent_uuid.
const std::vector<Task> TDB2::descendants(const std::string& parent_uuid) {
  // Snapshot once to avoid O(N²) rescans and to prevent infinite loops on corrupt cycles.
  const auto snapshot = all_tasks();
  std::vector<Task> results;
  std::vector<std::string> queue = {parent_uuid};
  std::set<std::string> visited = {parent_uuid};
  while (!queue.empty()) {
    std::string current = queue.back();
    queue.pop_back();
    for (auto& task : snapshot) {
      if (task.get("parent_id") == current) {
        results.push_back(task);
        std::string uuid = task.get("uuid");
        if (!visited.count(uuid)) {
          visited.insert(uuid);
          queue.push_back(uuid);
        }
      }
    }
  }
  return results;
}

////////////////////////////////////////////////////////////////////////////////
// Build a TreeMap from all tasks via the TCH bridge.
rust::Box<tc::TreeMapWrapper> TDB2::tree_map() { return replica()->tree_map(); }

////////////////////////////////////////////////////////////////////////////////
int TDB2::num_local_changes() { return (int)replica()->num_local_operations(); }

////////////////////////////////////////////////////////////////////////////////
int TDB2::num_reverts_possible() { return (int)replica()->num_undo_points(); }

////////////////////////////////////////////////////////////////////////////////
// For any task that has depenencies, follow the chain of dependencies until the
// end.  Along the way, update the Task::is_blocked and Task::is_blocking data
// cache.
static void dependency_scan(std::vector<Task>& tasks) {
  for (auto& left : tasks) {
    for (auto& dep : left.getDependencyUUIDs()) {
      for (auto& right : tasks) {
        if (right.get("uuid") == dep) {
          // GC hasn't run yet, check both tasks for their current status
          Task::status lstatus = left.getStatus();
          Task::status rstatus = right.getStatus();
          if (lstatus != Task::completed && lstatus != Task::deleted &&
              rstatus != Task::completed && rstatus != Task::deleted) {
            left.is_blocked = true;
            right.is_blocking = true;
          }

          // Only want to break out of the "right" loop.
          break;
        }
      }
    }
  }
}

////////////////////////////////////////////////////////////////////////////////
// Returns sibling recurrence instances (same recurrence parent, excluding self).
const std::vector<Task> TDB2::siblings(Task& task) {
  std::vector<Task> results;
  if (task.has("parent")) {
    std::string parent = task.get("parent");
    std::string uuid = task.get("uuid");
    for (auto& i : this->pending_tasks()) {
      if (i.get("uuid") != uuid) {
        if (i.getStatus() != Task::completed && i.getStatus() != Task::deleted) {
          if (i.has("parent") && i.get("parent") == parent) {
            results.push_back(i);
          }
        }
      }
    }
  }
  return results;
}

////////////////////////////////////////////////////////////////////////////////
// Returns children of a recurrence template (tasks whose "parent" field matches).
const std::vector<Task> TDB2::recurrence_children(const std::string& parent_uuid) {
  std::vector<Task> results;
  for (auto& task : pending_tasks()) {
    if (task.has("parent") && task.get("parent") == parent_uuid) {
      results.push_back(task);
    }
  }
  return results;
}

////////////////////////////////////////////////////////////////////////////////
// vim: ts=2 et sw=2
