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


def get_subtasks(t, parent_uuid):
    """Return all exported tasks whose parent_id matches parent_uuid."""
    return [task for task in t.export() if task.get("parent_id") == parent_uuid]


class TestPlanFencedCodeBlocks(TestCase):
    """Tests that fenced code blocks do not produce spurious headings."""

    def setUp(self):
        self.t = Task()

    def test_heading_syntax_inside_fence_not_parsed(self):
        """A '# heading' line inside a fenced block must not become a subtask.

        Uses '# inline comment' which starts with '# ' and WOULD be parsed as a
        heading outside a fence — exercising the fence guard directly.
        """
        self.t("add Parent")
        parent_uuid = get_uuid(self.t, "Parent")

        markdown = (
            "## Step 1\n"
            "Some setup.\n"
            "```rust\n"
            "# inline comment that looks like a heading\n"
            "let x = 1;\n"
            "```\n"
            "## Step 2\n"
            "Teardown.\n"
        )
        self.t(f"{parent_uuid[:8]} plan", input=markdown)

        subtasks = get_subtasks(self.t, parent_uuid)
        descriptions = [s["description"] for s in subtasks]

        self.assertEqual(len(subtasks), 2, f"Expected 2 subtasks, got: {descriptions}")
        self.assertIn("Step 1", descriptions)
        self.assertIn("Step 2", descriptions)
        # The comment line inside the fence must NOT appear as a subtask
        self.assertNotIn("inline comment that looks like a heading", descriptions)

    def test_hash_comment_inside_fence_not_a_heading(self):
        """A # comment line inside a fenced block must not become a subtask."""
        self.t("add Parent")
        parent_uuid = get_uuid(self.t, "Parent")

        markdown = (
            "## Real Heading\n"
            "```\n"
            "# this is a shell comment, not a heading\n"
            "echo hello\n"
            "```\n"
        )
        self.t(f"{parent_uuid[:8]} plan", input=markdown)

        subtasks = get_subtasks(self.t, parent_uuid)
        descriptions = [s["description"] for s in subtasks]

        self.assertEqual(len(subtasks), 1, f"Expected 1 subtask, got: {descriptions}")
        self.assertEqual(descriptions[0], "Real Heading")

    def test_boundary_heading_before_and_after_fence(self):
        """Headings immediately before and after a code fence are parsed correctly."""
        self.t("add Parent")
        parent_uuid = get_uuid(self.t, "Parent")

        markdown = (
            "## Before Fence\n"
            "```\n"
            "# inside fence\n"
            "```\n"
            "## After Fence\n"
        )
        self.t(f"{parent_uuid[:8]} plan", input=markdown)

        subtasks = get_subtasks(self.t, parent_uuid)
        descriptions = [s["description"] for s in subtasks]

        self.assertEqual(len(subtasks), 2, f"Expected 2 subtasks, got: {descriptions}")
        self.assertIn("Before Fence", descriptions)
        self.assertIn("After Fence", descriptions)


class TestPlanReplace(TestCase):
    """Tests for plan replace with fenced code blocks."""

    def setUp(self):
        self.t = Task()

    def test_plan_replace_with_fenced_blocks(self):
        """plan replace replaces existing subtasks; fenced content is not parsed."""
        self.t("add Parent")
        parent_uuid = get_uuid(self.t, "Parent")

        # First plan: two real headings plus a code fence with a hash comment
        markdown_v1 = (
            "## Alpha\n"
            "## Beta\n"
            "```\n"
            "# not a heading\n"
            "```\n"
        )
        self.t(f"{parent_uuid[:8]} plan", input=markdown_v1)

        subtasks = get_subtasks(self.t, parent_uuid)
        self.assertEqual(len(subtasks), 2)

        # Replace with a single heading; fence content must still be ignored
        markdown_v2 = (
            "## Gamma\n"
            "```python\n"
            "# module-level comment\n"
            "x = 1\n"
            "```\n"
        )
        self.t(f"{parent_uuid[:8]} plan replace", input=markdown_v2)

        all_tasks = self.t.export()
        pending = [
            t for t in all_tasks
            if t.get("parent_id") == parent_uuid and t.get("status") == "pending"
        ]
        descriptions = [t["description"] for t in pending]

        self.assertEqual(len(pending), 1, f"Expected 1 pending subtask, got: {descriptions}")
        self.assertEqual(descriptions[0], "Gamma")


class TestPlanRegression(TestCase):
    """Regression tests: normal markdown without fences must still work."""

    def setUp(self):
        self.t = Task()

    def test_normal_markdown_two_headings(self):
        """Plain markdown with two ## headings creates two subtasks."""
        self.t("add Parent")
        parent_uuid = get_uuid(self.t, "Parent")

        markdown = "## Task One\nDo the thing.\n\n## Task Two\nDo another thing.\n"
        self.t(f"{parent_uuid[:8]} plan", input=markdown)

        subtasks = get_subtasks(self.t, parent_uuid)
        descriptions = [s["description"] for s in subtasks]

        self.assertEqual(len(subtasks), 2, f"Expected 2 subtasks, got: {descriptions}")
        self.assertIn("Task One", descriptions)
        self.assertIn("Task Two", descriptions)

    def test_annotation_preserved(self):
        """Body text under a heading becomes the subtask annotation."""
        self.t("add Parent")
        parent_uuid = get_uuid(self.t, "Parent")

        markdown = "## Step\nThis is the annotation text.\n"
        self.t(f"{parent_uuid[:8]} plan", input=markdown)

        subtasks = get_subtasks(self.t, parent_uuid)
        self.assertEqual(len(subtasks), 1)

        step = subtasks[0]
        annotations = step.get("annotations", [])
        self.assertTrue(
            any("annotation text" in ann.get("description", "") for ann in annotations),
            f"Annotation not found in: {annotations}",
        )

    def test_nested_headings_create_child_subtasks(self):
        """### headings become grandchildren of the parent."""
        self.t("add Parent")
        parent_uuid = get_uuid(self.t, "Parent")

        markdown = "## Phase\n### Sub-task\n"
        self.t(f"{parent_uuid[:8]} plan", input=markdown)

        all_tasks = self.t.export()
        phase = next((t for t in all_tasks if t.get("description") == "Phase"), None)
        sub = next((t for t in all_tasks if t.get("description") == "Sub-task"), None)

        self.assertIsNotNone(phase, "Phase task not found")
        self.assertIsNotNone(sub, "Sub-task not found")
        self.assertEqual(phase.get("parent_id"), parent_uuid)
        self.assertEqual(sub.get("parent_id"), phase["uuid"])

    def test_no_headings_returns_error(self):
        """Markdown with no headings returns exit code 1."""
        self.t("add Parent")
        parent_uuid = get_uuid(self.t, "Parent")

        code, out, err = self.t.runError(
            f"{parent_uuid[:8]} plan", input="just plain text, no headings\n"
        )
        self.assertIn("No headings", out + err)

    def test_h1_and_h2_produce_flat_siblings(self):
        """# and ## headings both map to depth=1, producing flat siblings not a hierarchy.

        The squash rule (level <= 2 → depth 1) is intentional: a user writing
        '# Phase' followed by '## Step' expects two siblings, not nesting.
        """
        self.t("add Parent")
        parent_uuid = get_uuid(self.t, "Parent")

        markdown = "# Phase One\n## Phase Two\n"
        self.t(f"{parent_uuid[:8]} plan", input=markdown)

        subtasks = get_subtasks(self.t, parent_uuid)
        descriptions = [s["description"] for s in subtasks]

        self.assertEqual(len(subtasks), 2, f"Expected 2 flat siblings, got: {descriptions}")
        self.assertIn("Phase One", descriptions)
        self.assertIn("Phase Two", descriptions)
        # Both are direct children of the parent (not nested under each other)
        for s in subtasks:
            self.assertEqual(s.get("parent_id"), parent_uuid)

    def test_unclosed_fence_swallows_remaining_headings(self):
        """An unclosed fenced block causes subsequent headings to be ignored.

        This is the most common accidental mistake. The result is 'No headings
        found' if the only real heading comes before the fence, or fewer subtasks
        than expected if some come before.
        """
        self.t("add Parent")
        parent_uuid = get_uuid(self.t, "Parent")

        # Heading before the fence is parsed; heading after the unclosed fence is swallowed.
        markdown = (
            "## Before Fence\n"
            "```\n"
            "# inside unclosed fence\n"
            "## Also Inside\n"
        )
        self.t(f"{parent_uuid[:8]} plan", input=markdown)

        subtasks = get_subtasks(self.t, parent_uuid)
        descriptions = [s["description"] for s in subtasks]

        # Only "Before Fence" should survive; everything after the open fence is body text.
        self.assertEqual(len(subtasks), 1, f"Expected 1 subtask, got: {descriptions}")
        self.assertEqual(descriptions[0], "Before Fence")


if __name__ == "__main__":
    from simpletap import TAPTestRunner
    unittest.main(testRunner=TAPTestRunner())
