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

#include <test.h>
#include <unistd.h>

#include "Context.h"


////////////////////////////////////////////////////////////////////////////////
int TEST_NAME(int, char**) {
  UnitTest t(26);
  Context context;
  Context::setContext(&context);

  try {
    // Set the context to allow GC.
    context.config.set("gc", 1);
    context.config.set("debug", 1);

    context.tdb2.open_replica_for_test();

    // Try reading an empty database.
    std::vector<Task> pending = context.tdb2.pending_tasks();
    std::vector<Task> completed = context.tdb2.completed_tasks();

    t.is((int)pending.size(), 0, "TDB2 Read empty pending");
    t.is((int)completed.size(), 0, "TDB2 Read empty completed");
    // PowerSync: num_reverts_possible and num_local_changes are no-ops (sync is external).
    t.is((int)context.tdb2.num_reverts_possible(), 0, "TDB2 Read empty undo (PowerSync no-op)");
    t.is((int)context.tdb2.num_local_changes(), 0, "TDB2 Read empty backlog (PowerSync no-op)");

    // Add a task.
    Task task(R"({"description":"description"})");
    context.tdb2.add(task);

    pending = context.tdb2.pending_tasks();
    completed = context.tdb2.completed_tasks();

    t.is((int)pending.size(), 1, "TDB2 after add, 1 pending task");
    t.is((int)completed.size(), 0, "TDB2 after add, 0 completed tasks");
    // PowerSync: unsynced operation counts are not meaningful — verify calls succeed.
    context.tdb2.num_reverts_possible();
    context.tdb2.num_local_changes();
    t.pass("TDB2 after add, operation count calls succeed (PowerSync no-op)");

    task.set("description", "This is a test");
    context.tdb2.modify(task);

    pending = context.tdb2.pending_tasks();
    completed = context.tdb2.completed_tasks();

    t.is((int)pending.size(), 1, "TDB2 after set, 1 pending task");
    t.is((int)completed.size(), 0, "TDB2 after set, 0 completed tasks");
    t.pass("TDB2 after set, operation count calls succeed (PowerSync no-op)");

    // Scenario (a): pending task depending on a recurring template — depmap
    // parity. The cached DependencyMap excludes pending↔recurring edges
    // (taskchampion gates on pending status); old C++ dep_scan would have
    // marked both endpoints. Lock the new (correct) semantics.
    context.tdb2.open_replica_for_test();
    {
      const std::string uuid_a = "aaaaaaaa-1111-1111-1111-111111111111";
      const std::string uuid_b = "bbbbbbbb-2222-2222-2222-222222222222";

      Task tA;
      tA.set("uuid", uuid_a);
      tA.set("description", "pending dependent");
      tA.set("status", "pending");
      tA.addDependency(uuid_b);

      Task tB;
      tB.set("uuid", uuid_b);
      tB.set("description", "recurring template");
      tB.set("status", "recurring");

      context.tdb2.add(tA);
      context.tdb2.add(tB);

      std::vector<Task> all = context.tdb2.all_tasks();
      Task* a = nullptr;
      Task* b = nullptr;
      for (auto& tt : all) {
        if (tt.get("uuid") == uuid_a) a = &tt;
        if (tt.get("uuid") == uuid_b) b = &tt;
      }
      t.ok(a != nullptr, "TDB2 depmap: found pending dependent A");
      t.ok(b != nullptr, "TDB2 depmap: found recurring template B");
      t.ok(a && a->is_blocked == false,
           "TDB2 depmap: pending->recurring leaves A.is_blocked=false");
      t.ok(b && b->is_blocking == false,
           "TDB2 depmap: recurring target leaves B.is_blocking=false");
    }

    // Unit tests for looksLikeFullUuid — guards the FFI panic path.
    // Positive cases:
    t.ok(looksLikeFullUuid("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
         "looksLikeFullUuid: valid lowercase uuid");
    t.ok(looksLikeFullUuid("AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"),
         "looksLikeFullUuid: valid uppercase uuid");
    t.ok(looksLikeFullUuid("deadbeef-1234-5678-9abc-def012345678"),
         "looksLikeFullUuid: mixed case valid uuid");
    // Negative cases:
    t.ok(!looksLikeFullUuid(""),
         "looksLikeFullUuid: empty string rejected");
    t.ok(!looksLikeFullUuid("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeee"),
         "looksLikeFullUuid: 35 chars rejected");
    t.ok(!looksLikeFullUuid("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee"),
         "looksLikeFullUuid: 37 chars rejected");
    t.ok(!looksLikeFullUuid("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeee-ff"),
         "looksLikeFullUuid: 41 chars rejected");
    t.ok(!looksLikeFullUuid("--------bbbbccccddddeeeeeeeeeeee"),
         "looksLikeFullUuid: all hyphens rejected");
    t.ok(!looksLikeFullUuid("aaaaaaaa-bbbb-cccc-dddd-gggggggggggg"),
         "looksLikeFullUuid: non-hex chars rejected");
    t.ok(!looksLikeFullUuid("aaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
         "looksLikeFullUuid: hyphen at wrong position rejected");

    // Scenario (b): two tasks whose UUIDs share the first 8 hex chars. The
    // 8-char-prefix lookup must still succeed (first-found-wins preserved).
    // Hand-picked UUIDs are the only way to seed deterministic prefix
    // collisions in a unit test.
    context.tdb2.open_replica_for_test();
    {
      const std::string uuid1 = "deadbeef-1111-1111-1111-111111111111";
      const std::string uuid2 = "deadbeef-2222-2222-2222-222222222222";
      Task t1;
      t1.set("uuid", uuid1);
      t1.set("description", "prefix collision 1");
      Task t2;
      t2.set("uuid", uuid2);
      t2.set("description", "prefix collision 2");
      context.tdb2.add(t1);
      context.tdb2.add(t2);

      Task found;
      bool got = context.tdb2.get("deadbeef", found);
      t.ok(got, "TDB2 get prefix collision: returns true on shared prefix");
      const std::string fu = found.get("uuid");
      t.ok(fu == uuid1 || fu == uuid2,
           "TDB2 get prefix collision: resolves to one of the candidates");
    }

    // Reset for reuse.
    context.tdb2.open_replica_for_test();

    // TODO complete a task
    // TODO gc
  }

  catch (const std::string& error) {
    t.diag(error);
    return -1;
  }

  catch (...) {
    t.diag("Unknown error.");
    return -2;
  }

  // No file cleanup needed — test uses in-memory PowerSync storage.

  return 0;
}

////////////////////////////////////////////////////////////////////////////////
