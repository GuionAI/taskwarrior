#!/usr/bin/env python3
###############################################################################
#
# Copyright 2006 - 2021, Tomas Babej, Paul Beckingham, Federico Hernandez.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# https://www.opensource.org/licenses/mit-license.php
#
###############################################################################

import os
import sqlite3
import sys
import unittest

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from basetest import Task, TestCase


SHORT_ID_UUID = "aaaaaaaa-1111-4111-8111-111111111111"
NUMERIC_PREFIX_UUID = "12345678-2222-4222-8222-222222222222"


class TestShortID(TestCase):
    def setUp(self):
        self.t = Task()
        self.t(
            "import -",
            input="""[
        {"description":"short-id target","entry":"1700000000","status":"pending","uuid":"aaaaaaaa-1111-4111-8111-111111111111"},
        {"description":"numeric-prefix target","entry":"1700000000","status":"pending","uuid":"12345678-2222-4222-8222-222222222222"},
        {"description":"short-numeric-prefix target","entry":"1700000000","status":"pending","uuid":"42000000-3333-4333-8333-333333333333"}
        ]""",
        )
        self._set_short_id(SHORT_ID_UUID, 12345678)
        self._set_short_id(NUMERIC_PREFIX_UUID, 77)

    def _set_short_id(self, uuid, short_id):
        conn = sqlite3.connect(self.t.db_path)
        try:
            conn.execute(
                "UPDATE tc_tasks_data SET short_id = ? WHERE id = ?",
                (short_id, uuid),
            )
            conn.commit()
        finally:
            conn.close()

    def test_id_column_displays_short_id(self):
        code, out, err = self.t(
            "aaaaaaaa list rc.report.list.columns:id,description rc.report.list.labels:ID,Description"
        )
        self.assertIn("12345678", out)
        self.assertIn("short-id target", out)

    def test_numeric_short_id_filters_task(self):
        code, out, err = self.t("12345678 export")
        self.assertIn('"description":"short-id target"', out)
        self.assertNotIn('"description":"numeric-prefix target"', out)
        self.assertNotIn('"short_id"', out)

    def test_numeric_short_id_modifies_task(self):
        self.t("12345678 modify priority:H")
        code, out, err = self.t("aaaaaaaa export")
        self.assertIn('"priority":"H"', out)

    def test_numeric_ambiguity_prefers_short_id_over_uuid_prefix(self):
        code, out, err = self.t("12345678 info")
        self.assertIn("short-id target", out)
        self.assertNotIn("numeric-prefix target", out)

    def test_uuid_prefix_falls_back_when_no_short_id_matches(self):
        code, out, err = self.t("aaaaaaaa export")
        self.assertIn('"description":"short-id target"', out)

    def test_short_numeric_id_miss_does_not_fallback_to_uuid_prefix(self):
        code, out, err = self.t.runError("42 info")
        self.assertNotIn("short-numeric-prefix target", out)
        self.assertNotIn("short-numeric-prefix target", err)


if __name__ == "__main__":
    from simpletap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())

# vim: ai sts=4 et sw=4 ft=python
