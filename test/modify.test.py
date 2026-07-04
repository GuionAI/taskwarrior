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

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from basetest import Task, TestCase


class TestBug1306(TestCase):
    def setUp(self):
        self.t = Task()

    def test_mod_before_add(self):
        """FILTER before 'add' command upgraded to MODIFICATION"""
        self.t("project:PROJ add foo")
        code, out, err = self.t("project:PROJ info")
        self.assertIn("PROJ", out)


class TestBug1763(TestCase):
    def setUp(self):
        self.t = Task()

    def test_mod_nop(self):
        """Removing the due date of a task with no due date modifies the task"""
        self.t("add foo")
        code, out, err = self.t("1 modify due:")
        self.assertIn("Modified 0 tasks.", out)


class TestBug3584(TestCase):
    def setUp(self):
        self.t = Task()

    def test_mod_pending_task_end_date(self):
        """Adding end date for a pending task throws an error"""
        self.t("add foo")
        code, out, err = self.t.runError("1 modify end:1d")
        self.assertIn("You cannot set an end date on a pending task.", err)


class TestModifyDescriptionInput(TestCase):
    def setUp(self):
        self.t = Task()
        self.t("add original")

    def test_modify_description_from_pipe(self):
        "Testing modify command with description read from piped stdin"

        description = '"Line one" with `code`\nLine two with $HOME and (parens)'
        self.t.runSuccess("1 modify", input=description)

        self.assertEqual(self.t.export_one("1")["description"], description)

    def test_modify_with_modification_ignores_piped_stdin(self):
        "Testing modify command keeps stdin available when modifications are present"

        self.t.runSuccess("1 modify priority:H", input="not a description")

        self.assertEqual(self.t.export_one("1")["description"], "original")
        self.assertEqual(self.t.export_one("1")["priority"], "H")

    def test_modify_with_bulk_confirmation_keeps_stdin_for_prompt(self):
        "Testing bulk modify still reads confirmation from stdin"

        self.t("add second")
        self.t.config("bulk", "2")

        self.t.runSuccess("1 2 modify priority:H", input="All\n")

        self.assertEqual(self.t.export_one("1")["description"], "original")
        self.assertEqual(self.t.export_one("2")["description"], "second")
        self.assertEqual(self.t.export_one("1")["priority"], "H")
        self.assertEqual(self.t.export_one("2")["priority"], "H")

    def test_modify_positional_description_ignores_piped_stdin(self):
        "Testing modify command keeps positional description when stdin is piped"

        self.t.runSuccess("1 modify positional description", input="piped description")

        self.assertEqual(self.t.export_one("1")["description"], "positional description")


if __name__ == "__main__":
    from simpletap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())

# vim: ai sts=4 et sw=4 ft=python
