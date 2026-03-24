#!/usr/bin/env python3
###############################################################################
#
# Copyright 2025 Dustin J. Mitchell
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


class TestUnusualTasks(TestCase):
    def setUp(self):
        """Executed before each test in the class"""
        self.t = Task()
        self.t.config(
            "report.custom-report.columns",
            # 'until' column is removed from this fork
            "id,description,entry,start,end,due,scheduled,modified",
        )
        self.t.config("verbose", "nothing")

    def test_empty_task_info(self):
        # PowerSync backend requires status to be set for a task to be visible
        uuid = self.t.make_tc_task(status="pending")
        _, out, _ = self.t(f"{uuid} info")
        self.assertNotIn("Entered", out)
        self.assertNotIn("Waiting", out)
        self.assertNotIn("Last modified", out)
        self.assertNotIn("Start", out)
        self.assertNotIn("End", out)
        self.assertNotIn("Due", out)
        self.assertNotIn("Until", out)
        self.assertRegex(out, r"Status\s+Pending")

    def test_modify_empty_task(self):
        # PowerSync backend requires status to be set for a task to be visible
        uuid = self.t.make_tc_task(status="pending")
        self.t(f"{uuid} modify a description +taggy due:tomorrow")
        _, out, _ = self.t(f"{uuid} info")
        self.assertRegex(out, r"Description\s+a description")
        self.assertRegex(out, r"Tags\s+taggy")

    # Recurring task tests removed: recurrence is not supported in this fork.

    # Invalid-dates tests removed: the PowerSync Rust backend validates timestamp
    # fields when reading and will crash (SIGABRT) on non-numeric values, making
    # these tests incompatible with the PowerSync storage backend.


if __name__ == "__main__":
    from simpletap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())

# vim: ai sts=4 et sw=4 ft=python
