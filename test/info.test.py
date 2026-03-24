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
import time
import os
import unittest

# Ensure python finds the local simpletap module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from basetest import Task, TestCase


class TestInfoCommand(TestCase):
    @classmethod
    def setUpClass(cls):
        """Executed once before any test in the class"""

    def setUp(self):
        """Executed before each test in the class"""
        self.t = Task()

    def test_missing_info(self):
        """Verify bad filter yields error"""
        code, out, err = self.t.runError("999 info")
        self.assertIn("No matches.", err)

    def test_info_display(self):
        """Verify info command shows everything in the task"""
        pass

    def test_info_display_basic(self):
        """Verify info command shows basic task fields"""
        self.t.config("uda.u_one.type", "date")
        self.t.config("uda.u_one.label", "U_ONE")
        self.t.config("uda.u_two.type", "duration")
        self.t.config("uda.u_two.label", "U_TWO")

        self.t.config("urgency.user.project.P.coefficient", "1.0")
        self.t.config("urgency.user.keyword.foo.coefficient", "1.0")
        self.t.config("urgency.uda.u_one.coefficient", "1.0")

        self.t(
            "add foo project:P +tag priority:H start:now due:eom wait:eom scheduled:eom u_one:now u_two:1day"
        )
        # Use tracked hex ID — 'annotate' is a description-context command
        # so numeric IDs are not translated automatically.
        task1_id = self.t._task_ids[0]
        self.t("{0} annotate bar".format(task1_id), input="n\n")
        code, out, err = self.t("1 info")

        self.assertRegex(out, r"ID\s+[0-9a-f]+")
        self.assertRegex(out, r"Description\s+foo")
        self.assertRegex(out, r"\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\s+bar")
        self.assertRegex(out, r"Project\s+P")
        self.assertRegex(out, r"Entered\s+\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}")
        self.assertRegex(out, r"Waiting until\s+\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}")
        self.assertRegex(out, r"Scheduled\s+\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}")
        self.assertRegex(out, r"Start\s+\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}")
        self.assertRegex(out, r"Due\s+\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}")
        self.assertRegex(out, r"Last modified\s+\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}")

        self.assertRegex(out, r"Tags\s+tag")
        self.assertIn("ACTIVE", out)
        self.assertIn("ANNOTATED", out)
        self.assertIn("MONTH", out)
        self.assertIn("SCHEDULED", out)
        self.assertIn("TAGGED", out)
        self.assertIn("UNBLOCKED", out)
        self.assertIn("YEAR", out)
        self.assertIn("UDA", out)

        self.assertRegex(
            out,
            r"UUID\s+[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        )
        self.assertRegex(out, r"Urgency\s+\d+(\.\d+)?")
        self.assertRegex(out, r"Priority\s+H")

        self.assertRegex(out, r"Annotation of 'bar' added\.")
        self.assertRegex(out, r"Tag 'tag' added\.")
        self.assertIn("project", out)
        self.assertIn("active", out)
        self.assertIn("annotations", out)
        self.assertIn("tags", out)
        self.assertIn("due", out)
        self.assertIn("UDA priority.H", out)
        self.assertIn("U_ONE", out)
        self.assertIn("U_TWO", out)

        # TW-#2060: Make sure UDA attributes are formatted
        self.assertRegex(out, r"U_ONE\s+\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
        self.assertRegex(out, r"U_TWO\s+P1D")

    def test_tags_without_tags_attribute(self):
        """Verify info command shows tags, even if the `tags` property is not present"""
        # Create a task directly with TC, avoiding TaskWarrior's creation of the deprecated
        # `tags` property.
        uuid = self.t.make_tc_task(
            status="pending",
            description="task with tags",
            due=str(int(time.time())),
            tag_foo="x",
            tag_bar="x",
        )
        uuid_prefix = uuid[:8]
        code, out, err = self.t(f"{uuid_prefix} info")
        # Tags can occur in any order
        self.assertRegex(out, r"Tags\s+(bar|foo)\s(foo|bar)")


class TestBug425(TestCase):
    def setUp(self):
        self.t = Task()

    def test_bug425(self):
        """425: Make sure parser sees 'in' and not an abbreviated 'info'"""
        self.t("add Foo")
        self.t("1 modify Bar in Bar")

        code, out, err = self.t("1 ls")
        self.assertRegex(out, r"[0-9a-f]{8}\s+Bar in Bar")


def get_uuid(t, description):
    """Get UUID of a task by description via export."""
    tasks = t.export()
    for task in tasks:
        if task.get("description") == description:
            return task["uuid"]
    raise AssertionError(f"Task '{description}' not found")


class TestInfoChildren(TestCase):
    def setUp(self):
        self.t = Task()

    def test_info_children(self):
        """Verify info command shows children with description, status, and annotations"""
        # Create parent task
        self.t("add Parent task")
        parent_uuid = get_uuid(self.t, "Parent task")
        parent_short = parent_uuid[:8]

        # Create child tasks under the parent
        self.t("add Child one parent_id:{0}".format(parent_short))
        child1_uuid = get_uuid(self.t, "Child one")
        child1_short = child1_uuid[:8]

        self.t("add Child two parent_id:{0}".format(parent_short))
        child2_uuid = get_uuid(self.t, "Child two")
        child2_short = child2_uuid[:8]

        # Add annotation to child1
        self.t("{0} annotate 'child1 note'".format(child1_short), input="n\n")

        # Complete child2
        self.t("{0} done".format(child2_short), input="n\n")

        # Run info on parent
        code, out, err = self.t("{0} info".format(parent_short))

        # Verify Children section exists
        self.assertIn("Children", out)

        # Slice to Children section to avoid matching parent's own fields
        children_section = out[out.index("Children"):]

        # Verify child descriptions + short UUIDs appear in Children section
        self.assertIn("Child one", children_section)
        self.assertIn("Child two", children_section)
        self.assertIn(child1_short, children_section)
        self.assertIn(child2_short, children_section)

        # Verify status indicators in Children section
        self.assertIn("Pending", children_section)
        self.assertIn("Completed", children_section)

        # Verify child1's annotation appears
        self.assertIn("child1 note", children_section)

    def test_info_no_children(self):
        """Verify info command does not show Children row for leaf tasks"""
        self.t("add Leaf task")
        leaf_short = get_uuid(self.t, "Leaf task")[:8]
        code, out, err = self.t("{0} info".format(leaf_short))
        self.assertNotIn("Children", out)

    def test_info_children_direct_only(self):
        """Verify info on grandparent shows only direct children, not grandchildren"""
        self.t("add Grandparent")
        gp_uuid = get_uuid(self.t, "Grandparent")
        gp_short = gp_uuid[:8]

        self.t("add Parent child parent_id:{0}".format(gp_short))
        parent_uuid = get_uuid(self.t, "Parent child")
        parent_short = parent_uuid[:8]

        self.t("add Grandchild parent_id:{0}".format(parent_short))

        code, out, err = self.t("{0} info".format(gp_short))
        self.assertIn("Children", out)

        children_section = out[out.index("Children"):]
        self.assertIn("Parent child", children_section)
        self.assertNotIn("Grandchild", children_section)

    def test_info_children_deleted(self):
        """Verify info shows deleted children with correct status"""
        self.t("add Parent for delete test")
        parent_short = get_uuid(self.t, "Parent for delete test")[:8]

        self.t("add Deleted child parent_id:{0}".format(parent_short))
        child_short = get_uuid(self.t, "Deleted child")[:8]

        self.t("{0} delete".format(child_short), input="y\n")

        code, out, err = self.t("{0} info".format(parent_short))
        self.assertIn("Children", out)
        children_section = out[out.index("Children"):]
        self.assertIn("Deleted child", children_section)
        self.assertIn("Deleted", children_section)


if __name__ == "__main__":
    from simpletap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())

# vim: ai sts=4 et sw=4 ft=python
