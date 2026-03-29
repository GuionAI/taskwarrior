#!/usr/bin/env python3
###############################################################################
#
# Copyright 2006 - 2021, Tomas Babej, Paul Beckingham, Federico Hernandez.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# https://www.opensource.org/licenses/mit-license.php
#
###############################################################################

import sys
import os
import unittest

# Ensure python finds the local simpletap module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from basetest import Task, TestCase


def get_uuid(t, description):
    """Get UUID of a task by description via export."""
    tasks = t.export()
    for task in tasks:
        if task.get("description") == description:
            return task["uuid"]
    raise AssertionError(f"Task '{description}' not found")


class TestTreeAdd(TestCase):
    """Tests for adding tasks with parent relationships."""

    def setUp(self):
        self.t = Task()

    def test_add_creates_child_relationship(self):
        """Adding a task with parent_id: sets parent field."""
        self.t("rc.verbose=new-uuid add Project Alpha")
        parent_uuid = get_uuid(self.t, "Project Alpha")

        self.t(f"rc.verbose=new-uuid add Research parent_id:{parent_uuid}")
        child_tasks = self.t.export()
        child = next(
            (t for t in child_tasks if t.get("description") == "Research"), None
        )
        self.assertIsNotNone(child)
        self.assertEqual(child.get("parent_id"), parent_uuid)

    def test_add_parent_sets_position(self):
        """Adding a child task assigns a position."""
        self.t("add Project")
        parent_uuid = get_uuid(self.t, "Project")

        self.t(f"add Task1 parent_id:{parent_uuid}")
        self.t(f"add Task2 parent_id:{parent_uuid}")

        tasks = self.t.export()
        task1 = next(t for t in tasks if t.get("description") == "Task1")
        task2 = next(t for t in tasks if t.get("description") == "Task2")

        self.assertIn("position", task1)
        self.assertIn("position", task2)
        # Task2 added after Task1 should sort later lexicographically
        self.assertGreater(task2["position"], task1["position"])

    def test_add_output_shows_short_uuid(self):
        """CmdAdd output shows 8-char hex UUID."""
        code, out, err = self.t("rc.verbose=new-uuid add Buy milk")
        # Should show 8-char UUID in output
        import re
        self.assertRegex(out, r"Created task [0-9a-f]{8}\.")

    def test_add_parent_id_prefix(self):
        """Adding a child with 8-char parent_id prefix resolves to full UUID."""
        self.t("add Project")
        parent_uuid = get_uuid(self.t, "Project")
        prefix = parent_uuid[:8]

        self.t(f"add Child parent_id:{prefix}")

        tasks = self.t.export()
        child = next(t for t in tasks if t.get("description") == "Child")
        # Stored parent_id should be the full UUID, not the prefix
        self.assertEqual(child.get("parent_id"), parent_uuid)

    def test_modify_parent_id_prefix(self):
        """Modifying parent_id with 8-char prefix resolves to full UUID."""
        self.t("add Project")
        self.t("add Orphan")
        parent_uuid = get_uuid(self.t, "Project")
        orphan_uuid = get_uuid(self.t, "Orphan")

        self.t(f"{orphan_uuid[:8]} modify parent_id:{parent_uuid[:8]}")

        tasks = self.t.export()
        orphan = next(t for t in tasks if t.get("description") == "Orphan")
        self.assertEqual(orphan.get("parent_id"), parent_uuid)


class TestTreeDisplay(TestCase):
    """Tests for task tree display."""

    def setUp(self):
        self.t = Task()

    def test_tree_shows_hierarchy(self):
        """task tree shows box-drawing tree output."""
        self.t("add Project")
        parent_uuid = get_uuid(self.t, "Project")
        self.t(f"add Research parent_id:{parent_uuid}")
        self.t(f"add Implementation parent_id:{parent_uuid}")

        code, out, err = self.t(f"{parent_uuid[:8]} tree")
        self.assertIn("[" + parent_uuid[:8] + "] Project", out)
        self.assertIn("Research", out)
        self.assertIn("Implementation", out)
        # Box-drawing characters
        self.assertIn("└─", out)

    def test_tree_no_tasks_returns_error(self):
        """task tree with no matching tasks returns 1."""
        code, out, err = self.t.runError("all tree")

    def test_tree_single_task_subtree_mode(self):
        """Filtering to single task shows subtree."""
        self.t("add Root")
        root_uuid = get_uuid(self.t, "Root")
        self.t(f"add Child parent_id:{root_uuid}")

        code, out, err = self.t(f"{root_uuid[:8]} tree")
        self.assertIn("[" + root_uuid[:8] + "]", out)
        self.assertIn("Child", out)

    def test_tree_shows_done_indicator(self):
        """Completed tasks show [done] in tree output."""
        self.t("add Root")
        root_uuid = get_uuid(self.t, "Root")
        self.t(f"add Child parent_id:{root_uuid}")
        child_uuid = get_uuid(self.t, "Child")

        self.t(f"{child_uuid[:8]} rc.confirmation=no done")

        code, out, err = self.t(f"{root_uuid[:8]} tree")
        self.assertIn("[done]", out)


class TestTreeValidation(TestCase):
    """Tests for tree validation (cycles, self-parent)."""

    def setUp(self):
        self.t = Task()

    def test_self_parent_rejected(self):
        """A task cannot be its own parent."""
        self.t("add Task A")
        uuid = get_uuid(self.t, "Task A")

        code, out, err = self.t.runError(
            f"{uuid[:8]} modify parent_id:{uuid}"
        )
        self.assertIn("cannot be its own parent", err + out)

    def test_circular_reference_rejected(self):
        """Circular parent references are rejected."""
        self.t("add Task A")
        self.t("add Task B")
        uuid_a = get_uuid(self.t, "Task A")
        uuid_b = get_uuid(self.t, "Task B")

        # Make B a child of A
        self.t(f"{uuid_b[:8]} modify parent_id:{uuid_a}")

        # Try to make A a child of B (would create cycle)
        code, out, err = self.t.runError(
            f"{uuid_a[:8]} modify parent_id:{uuid_b}"
        )
        self.assertIn("Circular reference", err + out)

    def test_nonexistent_parent_rejected(self):
        """Parent task must exist."""
        self.t("add Task A")
        uuid = get_uuid(self.t, "Task A")
        fake_uuid = "00000000-0000-0000-0000-000000000099"

        code, out, err = self.t.runError(
            f"{uuid[:8]} modify parent_id:{fake_uuid}"
        )
        self.assertIn("does not exist", err + out)

    def test_nonexistent_prefix_rejected(self):
        """parent_id with prefix matching no task is rejected."""
        self.t("add Task A")
        uuid = get_uuid(self.t, "Task A")

        code, out, err = self.t.runError(f"add Child parent_id:00000000")
        self.assertIn("does not exist", err + out)

    def test_self_parent_via_prefix_rejected(self):
        """A task cannot be its own parent even when prefix is used."""
        self.t("add Task A")
        uuid = get_uuid(self.t, "Task A")

        code, out, err = self.t.runError(f"{uuid[:8]} modify parent_id:{uuid[:8]}")
        self.assertIn("cannot be its own parent", err + out)


class TestTreeDone(TestCase):
    """Tests for recursive completion."""

    def setUp(self):
        self.t = Task()

    def test_done_completes_descendants(self):
        """Completing a parent auto-completes all descendants."""
        self.t("add Project")
        parent_uuid = get_uuid(self.t, "Project")
        self.t(f"add Task1 parent_id:{parent_uuid}")
        self.t(f"add Task2 parent_id:{parent_uuid}")
        task1_uuid = get_uuid(self.t, "Task1")
        task2_uuid = get_uuid(self.t, "Task2")

        self.t(f"rc.confirmation=no {parent_uuid[:8]} done")

        tasks = {t["uuid"]: t for t in self.t.export()}
        self.assertEqual(tasks[parent_uuid]["status"], "completed")
        self.assertEqual(tasks[task1_uuid]["status"], "completed")
        self.assertEqual(tasks[task2_uuid]["status"], "completed")


class TestTreeDelete(TestCase):
    """Tests for recursive deletion."""

    def setUp(self):
        self.t = Task()

    def test_delete_prompts_for_descendants(self):
        """Deleting a parent with children prompts and deletes all."""
        self.t("add Project")
        parent_uuid = get_uuid(self.t, "Project")
        self.t(f"add Child parent_id:{parent_uuid}")
        child_uuid = get_uuid(self.t, "Child")

        # Answer yes to both: parent deletion prompt and child deletion prompt.
        self.t(f"{parent_uuid[:8]} delete", input="y\ny\n")

        tasks = {t["uuid"]: t for t in self.t.export()}
        self.assertEqual(tasks[parent_uuid]["status"], "deleted")
        self.assertEqual(tasks[child_uuid]["status"], "deleted")


class TestPlanCommand(TestCase):
    """Tests for task plan command."""

    def setUp(self):
        self.t = Task()

    def test_plan_creates_subtasks(self):
        """task plan creates subtasks from markdown headings."""
        self.t("add Project Alpha")
        parent_uuid = get_uuid(self.t, "Project Alpha")

        markdown = "## Research\nLook into solutions.\n## Implementation\nWrite the code.\n"
        code, out, err = self.t(
            f"{parent_uuid[:8]} plan", input=markdown
        )

        tasks = self.t.export()
        descriptions = [t["description"] for t in tasks]
        self.assertIn("Research", descriptions)
        self.assertIn("Implementation", descriptions)

        # Both subtasks should have parent set
        for task in tasks:
            if task["description"] in ("Research", "Implementation"):
                self.assertEqual(task.get("parent_id"), parent_uuid)

    def test_plan_nested_headings(self):
        """### headings become grandchildren."""
        self.t("add Project")
        parent_uuid = get_uuid(self.t, "Project")

        markdown = "## Phase 1\n### Backend\n### Frontend\n"
        self.t(f"{parent_uuid[:8]} plan", input=markdown)

        tasks = self.t.export()
        phase1 = next(
            (t for t in tasks if t.get("description") == "Phase 1"), None
        )
        self.assertIsNotNone(phase1)

        backend = next(
            (t for t in tasks if t.get("description") == "Backend"), None
        )
        self.assertIsNotNone(backend)
        self.assertEqual(backend.get("parent_id"), phase1["uuid"])

    def test_plan_replace_removes_existing(self):
        """task plan replace deletes existing children first."""
        self.t("add Project")
        parent_uuid = get_uuid(self.t, "Project")

        # Initial plan
        self.t(f"{parent_uuid[:8]} plan", input="## Old Task\n")
        old_uuid = get_uuid(self.t, "Old Task")

        # Replace with new plan
        self.t(f"{parent_uuid[:8]} plan replace", input="## New Task\n")

        tasks = {t["uuid"]: t for t in self.t.export()}
        # Old task should be deleted
        self.assertEqual(tasks[old_uuid]["status"], "deleted")
        # New task should exist
        new_task = next(
            (t for t in tasks.values() if t.get("description") == "New Task"), None
        )
        self.assertIsNotNone(new_task)

    def test_plan_no_markdown_returns_error(self):
        """task plan with no stdin returns error."""
        self.t("add Project")
        parent_uuid = get_uuid(self.t, "Project")
        code, out, err = self.t.runError(f"{parent_uuid[:8]} plan", input="")


class TestPositionOrdering(TestCase):
    """Tests for fractional-index position ordering."""

    def setUp(self):
        self.t = Task()

    def test_children_have_ordered_positions(self):
        """Children added sequentially have increasing positions."""
        self.t("add Root")
        root_uuid = get_uuid(self.t, "Root")

        self.t(f"add First parent_id:{root_uuid}")
        self.t(f"add Second parent_id:{root_uuid}")
        self.t(f"add Third parent_id:{root_uuid}")

        tasks = self.t.export()
        children = sorted(
            [t for t in tasks if t.get("parent_id") == root_uuid],
            key=lambda t: t.get("position", "")
        )
        descriptions = [t["description"] for t in children]
        self.assertEqual(descriptions, ["First", "Second", "Third"])


class TestSiblingReordering(TestCase):
    """Tests for before:/after: pseudo-attributes."""

    def setUp(self):
        self.t = Task()

    def _setup_siblings(self):
        """Create root with three children, return (root, first, second, third) UUIDs."""
        self.t("add Root")
        root_uuid = get_uuid(self.t, "Root")
        self.t(f"add First parent_id:{root_uuid}")
        self.t(f"add Second parent_id:{root_uuid}")
        self.t(f"add Third parent_id:{root_uuid}")
        first_uuid = get_uuid(self.t, "First")
        second_uuid = get_uuid(self.t, "Second")
        third_uuid = get_uuid(self.t, "Third")
        return root_uuid, first_uuid, second_uuid, third_uuid

    def test_after_repositions_task(self):
        """task modify after:<uuid> positions task after target sibling."""
        root_uuid, first_uuid, second_uuid, third_uuid = self._setup_siblings()

        # Move Third after First (so order becomes: First, Third, Second)
        self.t(f"{third_uuid[:8]} modify after:{first_uuid}")

        tasks = self.t.export()
        children = sorted(
            [t for t in tasks if t.get("parent_id") == root_uuid],
            key=lambda t: t.get("position", "")
        )
        descriptions = [t["description"] for t in children]
        self.assertEqual(descriptions, ["First", "Third", "Second"])

    def test_before_repositions_task(self):
        """task modify before:<uuid> positions task before target sibling."""
        root_uuid, first_uuid, second_uuid, third_uuid = self._setup_siblings()

        # Move First before Third (so order becomes: Second, First, Third)
        self.t(f"{first_uuid[:8]} modify before:{third_uuid}")

        tasks = self.t.export()
        children = sorted(
            [t for t in tasks if t.get("parent_id") == root_uuid],
            key=lambda t: t.get("position", "")
        )
        descriptions = [t["description"] for t in children]
        self.assertEqual(descriptions, ["Second", "First", "Third"])

    def test_after_last_sibling_appends(self):
        """after: the last sibling puts task at end."""
        root_uuid, first_uuid, second_uuid, third_uuid = self._setup_siblings()

        # Move First after Third (last) — should end up at the end
        self.t(f"{first_uuid[:8]} modify after:{third_uuid}")

        tasks = self.t.export()
        children = sorted(
            [t for t in tasks if t.get("parent_id") == root_uuid],
            key=lambda t: t.get("position", "")
        )
        self.assertEqual(children[-1]["description"], "First")

    def test_before_first_sibling_prepends(self):
        """before: the first sibling puts task at start."""
        root_uuid, first_uuid, second_uuid, third_uuid = self._setup_siblings()

        # Move Third before First (first) — should end up at the start
        self.t(f"{third_uuid[:8]} modify before:{first_uuid}")

        tasks = self.t.export()
        children = sorted(
            [t for t in tasks if t.get("parent_id") == root_uuid],
            key=lambda t: t.get("position", "")
        )
        self.assertEqual(children[0]["description"], "Third")

    def test_both_before_and_after_errors(self):
        """Specifying both before: and after: simultaneously errors."""
        root_uuid, first_uuid, second_uuid, third_uuid = self._setup_siblings()
        code, out, err = self.t.runError(
            f"{third_uuid[:8]} modify before:{first_uuid} after:{second_uuid}"
        )
        self.assertIn("Cannot specify both", err + out)


class TestTreeFullMode(TestCase):
    """Tests for CmdTree full-tree (multi-match) mode."""

    def setUp(self):
        self.t = Task()

    def test_full_tree_multiple_roots(self):
        """Full-tree mode shows multiple root tasks."""
        self.t("add Alpha")
        self.t("add Beta")
        alpha_uuid = get_uuid(self.t, "Alpha")
        beta_uuid = get_uuid(self.t, "Beta")

        code, out, err = self.t(f"{alpha_uuid[:8]} {beta_uuid[:8]} tree")
        self.assertIn("Alpha", out)
        self.assertIn("Beta", out)

    def test_full_tree_orphan_promoted_to_root(self):
        """Child with unmatched parent appears as root in full-tree mode."""
        self.t("add Parent")
        parent_uuid = get_uuid(self.t, "Parent")
        self.t(f"add Child parent_id:{parent_uuid}")
        child_uuid = get_uuid(self.t, "Child")

        # Filter to only the child — it should appear as root since parent not matched.
        code, out, err = self.t(f"{child_uuid[:8]} tree")
        self.assertIn("[" + child_uuid[:8] + "]", out)

    def test_full_tree_correct_box_glyphs(self):
        """Last matched child gets └─ not ├─ even if unmatched siblings exist."""
        self.t("add Root")
        root_uuid = get_uuid(self.t, "Root")
        self.t(f"add First parent_id:{root_uuid}")
        self.t(f"add Second parent_id:{root_uuid}")
        self.t(f"add Third parent_id:{root_uuid}")
        first_uuid = get_uuid(self.t, "First")
        third_uuid = get_uuid(self.t, "Third")

        # Filter root + first + third (skip second) — full-tree mode (3 UUIDs).
        # Third is the last matched child — should get └─ not ├─.
        second_uuid = get_uuid(self.t, "Second")
        code, out, err = self.t(f"{root_uuid[:8]} {first_uuid[:8]} {third_uuid[:8]} tree")
        lines = [l for l in out.strip().split("\n") if "Third" in l]
        self.assertTrue(any("└─" in l for l in lines))
        # Second is not in the filter — should not appear
        self.assertNotIn("Second", out)


class TestPlanAnnotations(TestCase):
    """Tests for CmdPlan annotation handling."""

    def setUp(self):
        self.t = Task()

    def test_plan_body_becomes_annotation(self):
        """Body text under a heading becomes a task annotation."""
        self.t("add Project")
        parent_uuid = get_uuid(self.t, "Project")

        markdown = "## Research\nLook into existing solutions.\nCheck prior art.\n"
        self.t(f"{parent_uuid[:8]} plan", input=markdown)

        tasks = self.t.export()
        research = next((t for t in tasks if t.get("description") == "Research"), None)
        self.assertIsNotNone(research)
        annotations = research.get("annotations", [])
        self.assertTrue(len(annotations) > 0)
        # Annotation description should contain body text
        ann_text = " ".join(a.get("description", "") for a in annotations)
        self.assertIn("Look into", ann_text)


class TestTreeDeleteIndicator(TestCase):
    """Tests for [del] indicator in CmdTree."""

    def setUp(self):
        self.t = Task()

    def test_tree_shows_del_indicator(self):
        """Deleted tasks show [del] in tree output."""
        self.t("add Root")
        root_uuid = get_uuid(self.t, "Root")
        self.t(f"add Child parent_id:{root_uuid}")
        child_uuid = get_uuid(self.t, "Child")

        # Delete the child (answer no to child-of-child prompt — child has no children)
        self.t(f"{child_uuid[:8]} delete", input="y\n")

        code, out, err = self.t(f"{root_uuid[:8]} tree")
        self.assertIn("[del]", out)


class TestTreeExportKey(TestCase):
    """Tests for correct JSON export key usage."""

    def setUp(self):
        self.t = Task()

    def test_export_uses_parent_id_key(self):
        """Exported JSON uses parent_id key, not parent."""
        self.t("add Project")
        parent_uuid = get_uuid(self.t, "Project")
        self.t(f"add SubTask parent_id:{parent_uuid}")
        code, out, err = self.t("export")
        import json
        tasks = json.loads(out)
        tree_child = next(t for t in tasks if t.get("description") == "SubTask")
        self.assertIn("parent_id", tree_child)
        self.assertNotIn("parent", tree_child)  # tree children use parent_id, not parent


class TestRecurrenceTreeCoexistence(TestCase):
    """Tests verifying recurrence and tree hierarchy use separate fields."""

    def setUp(self):
        self.t = Task()

    def test_recurrence_parent_separate_from_tree_parent_id(self):
        """Recurrence 'parent' and tree 'parent_id' are separate fields."""
        import json

        # Create a recurring task
        self.t("add Weekly due:tomorrow recur:weekly")
        self.t("list")  # triggers handleRecurrence

        # Get all tasks
        code, out, err = self.t("export")
        tasks = json.loads(out)

        recurring = [t for t in tasks if t.get("status") == "recurring"]
        children = [t for t in tasks if "parent" in t and t.get("status") == "pending"]

        # Recurrence children should have 'parent' (template link)
        for child in children:
            self.assertIn("parent", child)
            self.assertNotIn("parent_id", child)

        # Tree hierarchy uses parent_id
        self.t("add Project")
        proj_uuid = get_uuid(self.t, "Project")
        self.t(f"add SubTask parent_id:{proj_uuid}")

        code, out, err = self.t("export")
        tasks = json.loads(out)
        subtask = next(t for t in tasks if t.get("description") == "SubTask")
        self.assertIn("parent_id", subtask)
        self.assertNotIn("parent", subtask)

        # task tree should NOT show recurrence children as tree nodes
        code, out, err = self.t(f"{proj_uuid[:8]} tree")
        self.assertIn("SubTask", out)
        self.assertNotIn("Weekly", out)


class TestTreeDefaultFilter(TestCase):
    """Tests for tree.filter default — plain 'task tree' excludes completed/deleted roots."""

    def setUp(self):
        self.t = Task()

    def test_plain_tree_excludes_completed_roots(self):
        """task tree (no args) does not show completed root tasks."""
        self.t("add Pending Root")
        self.t("add Completed Root")
        pending_uuid = get_uuid(self.t, "Pending Root")
        completed_uuid = get_uuid(self.t, "Completed Root")

        self.t(f"rc.confirmation=no {completed_uuid[:8]} done")

        code, out, err = self.t("tree")
        self.assertIn(pending_uuid[:8], out)
        self.assertNotIn(completed_uuid[:8], out)

    def test_plain_tree_excludes_deleted_roots(self):
        """task tree (no args) does not show deleted root tasks."""
        self.t("add Pending Root")
        self.t("add Deleted Root")
        pending_uuid = get_uuid(self.t, "Pending Root")
        deleted_uuid = get_uuid(self.t, "Deleted Root")

        self.t(f"{deleted_uuid[:8]} delete", input="y\n")

        code, out, err = self.t("tree")
        self.assertIn(pending_uuid[:8], out)
        self.assertNotIn(deleted_uuid[:8], out)

    def test_plain_tree_includes_pending_children_of_pending_roots(self):
        """task tree shows pending root and its pending children."""
        self.t("add Root Task")
        root_uuid = get_uuid(self.t, "Root Task")
        self.t(f"add Child Task parent_id:{root_uuid}")
        child_uuid = get_uuid(self.t, "Child Task")

        code, out, err = self.t("tree")
        self.assertIn(root_uuid[:8], out)
        self.assertIn("Child Task", out)

    def test_tree_filter_override_via_taskrc(self):
        """Setting rc.tree.filter= (empty) shows completed/deleted roots."""
        self.t("add Pending Root")
        self.t("add Completed Root")
        pending_uuid = get_uuid(self.t, "Pending Root")
        completed_uuid = get_uuid(self.t, "Completed Root")

        self.t(f"rc.confirmation=no {completed_uuid[:8]} done")

        # Empty tree.filter override — should show all tasks including completed
        code, out, err = self.t("rc.tree.filter= tree")
        self.assertIn(pending_uuid[:8], out)
        self.assertIn(completed_uuid[:8], out)

    def test_plain_tree_excludes_waiting_roots(self):
        """task tree (no args) excludes waiting tasks (-WAITING in default filter)."""
        self.t("add Pending Root")
        self.t("add Waiting Root wait:tomorrow")
        pending_uuid = get_uuid(self.t, "Pending Root")
        waiting_uuid = get_uuid(self.t, "Waiting Root")

        code, out, err = self.t("tree")
        self.assertIn(pending_uuid[:8], out)
        self.assertNotIn(waiting_uuid[:8], out)

        # Empty override should reveal the waiting task
        code, out, err = self.t("rc.tree.filter= tree")
        self.assertIn(waiting_uuid[:8], out)

    def test_plain_tree_shows_completed_child_of_pending_root_with_indicator(self):
        """Completed child of a pending root shows with [done] indicator.

        The default filter applies only to visual roots — descendants are always
        rendered (with status indicators) so the full subtree stays visible.
        """
        self.t("add Root Task")
        root_uuid = get_uuid(self.t, "Root Task")
        self.t(f"add Done Child parent_id:{root_uuid}")
        child_uuid = get_uuid(self.t, "Done Child")

        self.t(f"rc.confirmation=no {child_uuid[:8]} done")

        code, out, err = self.t("tree")
        self.assertIn(root_uuid[:8], out)
        self.assertIn(child_uuid[:8], out)
        self.assertIn("[done]", out)

    def test_tree_user_filter_and_default_filter_compose(self):
        """task tree project:Foo shows only pending tasks in that project."""
        self.t("add Alpha project:Foo")
        self.t("add Beta project:Bar")
        self.t("add Gamma project:Foo")
        alpha_uuid = get_uuid(self.t, "Alpha")
        beta_uuid = get_uuid(self.t, "Beta")
        gamma_uuid = get_uuid(self.t, "Gamma")

        self.t(f"rc.confirmation=no {gamma_uuid[:8]} done")

        code, out, err = self.t("rc.context= tree project:Foo")
        self.assertIn(alpha_uuid[:8], out)
        self.assertNotIn(beta_uuid[:8], out)
        self.assertNotIn(gamma_uuid[:8], out)


class TestTreeProjectDisplay(TestCase):
    """Tests for project field display in tree output."""

    def setUp(self):
        self.t = Task()

    def test_tree_shows_project_for_task_with_project(self):
        """Tasks with a project show (ProjectName) in tree output."""
        self.t("add Root project:Work")
        root_uuid = get_uuid(self.t, "Root")
        self.t(f"add Child parent_id:{root_uuid} project:Work")

        code, out, err = self.t(f"{root_uuid[:8]} tree")
        self.assertIn("(Work)", out)

    def test_tree_no_project_no_parens(self):
        """Tasks without a project render as [uuid] description with no parens."""
        self.t("add Bare Task")
        root_uuid = get_uuid(self.t, "Bare Task")
        self.t(f"add Child parent_id:{root_uuid}")

        code, out, err = self.t(f"{root_uuid[:8]} tree")
        self.assertNotIn("()", out)
        # Verify exact format: [uuid8] description (no parens at all)
        self.assertIn(f"[{root_uuid[:8]}] Bare Task", out)

    def test_tree_mixed_projects(self):
        """Children with different projects show their respective projects."""
        self.t("add Root project:Alpha")
        root_uuid = get_uuid(self.t, "Root")
        self.t(f"add Task1 parent_id:{root_uuid} project:Alpha")
        self.t(f"add Task2 parent_id:{root_uuid} project:Beta")

        code, out, err = self.t(f"{root_uuid[:8]} tree")
        self.assertIn("(Alpha)", out)
        self.assertIn("(Beta)", out)

    def test_tree_project_with_hierarchy(self):
        """Hierarchical project names (e.g. Work.Backend) display correctly."""
        self.t("add Root project:Work.Backend")
        root_uuid = get_uuid(self.t, "Root")

        code, out, err = self.t(f"{root_uuid[:8]} tree")
        self.assertIn("(Work.Backend)", out)

    def test_tree_project_before_description(self):
        """Project appears between uuid and description: [uuid] (Project) desc."""
        self.t("add MyTask project:Ops")
        task_uuid = get_uuid(self.t, "MyTask")

        code, out, err = self.t(f"{task_uuid[:8]} tree")
        # Format: [uuid8] (Ops) MyTask
        self.assertIn("(Ops) MyTask", out)

    def test_tree_project_with_status_indicator(self):
        """Project and status indicators coexist: [uuid] (Project) desc [done]."""
        self.t("add Root project:Ops")
        root_uuid = get_uuid(self.t, "Root")
        self.t(f"add Child parent_id:{root_uuid} project:Ops")
        child_uuid = get_uuid(self.t, "Child")

        self.t(f"{child_uuid[:8]} rc.confirmation=no done")

        code, out, err = self.t(f"{root_uuid[:8]} tree")
        # Both indicators present on the completed child line
        child_line = [l for l in out.split("\n") if "Child" in l][0]
        self.assertIn("(Ops)", child_line)
        self.assertIn("[done]", child_line)
        # Verify order: project before description, status after
        ops_idx = child_line.index("(Ops)")
        child_idx = child_line.index("Child")
        done_idx = child_line.index("[done]")
        self.assertLess(ops_idx, child_idx)
        self.assertLess(child_idx, done_idx)

    def test_tree_project_in_full_tree_mode(self):
        """Full-tree mode shows distinct projects for roots; renderTree() child also shows project."""
        self.t("add Alpha project:ProjectA")
        self.t("add Beta project:ProjectB")
        alpha_uuid = get_uuid(self.t, "Alpha")
        beta_uuid = get_uuid(self.t, "Beta")
        # Add a child under Alpha; include it in the filter to exercise renderTree() in full-tree mode
        self.t(f"add AlphaChild parent_id:{alpha_uuid} project:ProjectA")
        child_uuid = get_uuid(self.t, "AlphaChild")

        code, out, err = self.t(f"{alpha_uuid[:8]} {beta_uuid[:8]} {child_uuid[:8]} tree")
        # Both root projects appear
        self.assertIn("(ProjectA)", out)
        self.assertIn("(ProjectB)", out)
        # Child rendered via renderTree() also shows its project
        child_line = [l for l in out.split("\n") if "AlphaChild" in l][0]
        self.assertIn("(ProjectA)", child_line)

    def test_tree_project_cross_contamination(self):
        """Parent with project and child without (or vice versa) each show only their own project."""
        self.t("add Root project:Infra")
        root_uuid = get_uuid(self.t, "Root")
        self.t(f"add Child parent_id:{root_uuid}")  # no project

        code, out, err = self.t(f"{root_uuid[:8]} tree")
        lines = [l for l in out.split("\n") if l.strip()]
        root_line = [l for l in lines if "Root" in l][0]
        child_line = [l for l in lines if "Child" in l][0]
        # Root shows project, child does not
        self.assertIn("(Infra)", root_line)
        self.assertNotIn("(Infra)", child_line)
        self.assertNotIn("()", child_line)


if __name__ == "__main__":
    from simpletap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())

# vim: ai sts=4 et sw=4 ft=python
