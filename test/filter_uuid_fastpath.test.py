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


# Hand-picked UUIDs so prefixes are deterministic and don't collide.
PENDING_UUIDS = [
    "11111111-1111-1111-1111-111111111111",
    "22222222-2222-2222-2222-222222222222",
    "33333333-3333-3333-3333-333333333333",
    "44444444-4444-4444-4444-444444444444",
    "55555555-5555-5555-5555-555555555555",
]
COMPLETED_UUIDS = [
    "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
]
RECURRING_UUID = "ccccccc1-cccc-cccc-cccc-cccccccccccc"


class TestFilterUuidFastPath(TestCase):
    """Pure-UUID filter short-circuit covers full UUID, 8-char prefix,
    comma sets, and falls back correctly to the slow path on mixed filters."""

    def setUp(self):
        self.t = Task()

        rows = []
        for i, u in enumerate(PENDING_UUIDS):
            rows.append(
                f'{{"description":"pending-{i}","entry":"1700000000",'
                f'"status":"pending","uuid":"{u}"}}'
            )
        for i, u in enumerate(COMPLETED_UUIDS):
            rows.append(
                f'{{"description":"completed-{i}","entry":"1700000000",'
                f'"end":"1700000000","status":"completed","uuid":"{u}"}}'
            )
        rows.append(
            f'{{"description":"recurring-template","entry":"1700000000",'
            f'"status":"recurring","uuid":"{RECURRING_UUID}",'
            f'"due":"1800000000","recur":"weekly"}}'
        )
        self.t("import -", input="[" + ",".join(rows) + "]")

    def test_full_uuid_export(self):
        """task <full-uuid> export returns the matching task."""
        code, out, err = self.t(PENDING_UUIDS[0] + " export")
        self.assertIn('"description":"pending-0"', out)

    def test_short_prefix_export(self):
        """task <8-char-prefix> export returns the matching task."""
        code, out, err = self.t(PENDING_UUIDS[1][:8] + " export")
        self.assertIn('"description":"pending-1"', out)

    def test_comma_set_export(self):
        """task <prefix1>,<prefix2> export returns both."""
        a, b = PENDING_UUIDS[0][:8], PENDING_UUIDS[2][:8]
        code, out, err = self.t(f"{a},{b} export")
        self.assertIn('"description":"pending-0"', out)
        self.assertIn('"description":"pending-2"', out)

    def test_bogus_prefix_export(self):
        """task <bogus-prefix> export returns no task — no crash."""
        code, out, err = self.t("99999999 export")
        self.assertNotIn('"description":"pending-', out)
        self.assertNotIn('"description":"completed-', out)

    def test_completed_target_export(self):
        """task <completed-uuid> export returns the completed task — covers
        TDB2::get tier 3 (all_task_data fallback) for non-pending targets."""
        code, out, err = self.t(COMPLETED_UUIDS[0] + " export")
        self.assertIn('"description":"completed-0"', out)

    def test_recurring_target_export(self):
        """task <recurring-template-uuid> export returns the template — full
        UUID hits TDB2::get tier 1 (PK fast-path) regardless of status."""
        code, out, err = self.t(RECURRING_UUID + " export")
        self.assertIn('"description":"recurring-template"', out)

    def test_mixed_filter_virtual_tag(self):
        """task <prefix> +PENDING list — predicate sees +PENDING (tag lex
        type) as a non-UUID FILTER token and bails. Slow path applies both
        filters; only the matching pending task appears."""
        prefix = PENDING_UUIDS[3][:8]
        code, out, err = self.t(prefix + " +PENDING list")
        self.assertIn("pending-3", out)
        self.assertNotIn("completed-", out)

    def test_mixed_filter_dom_attribute(self):
        """task <prefix> status:completed list — predicate sees status:completed
        (pair lex type) as non-UUID and bails. Slow path applies both filters,
        which intersect to nothing because the prefix points at a pending task."""
        prefix = PENDING_UUIDS[4][:8]
        code, out, err = self.t.runError(prefix + " status:completed list")
        self.assertNotIn("pending-4", out)
        self.assertNotIn("completed-", out)


if __name__ == "__main__":
    from simpletap import TAPTestRunner

    unittest.main(testRunner=TAPTestRunner())

# vim: ai sts=4 et sw=4 ft=python
