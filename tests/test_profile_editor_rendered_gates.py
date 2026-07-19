"""Round-trip tests for the profile editor's rendered_gates handling (t635_33).

The key-presence semantic is load-bearing: an explicit `rendered_gates: []` is
a render-nothing override and must survive edit → collect → serialize → load,
staying distinguishable from an unset key (which falls back to default_gates).

Run: python3 tests/test_profile_editor_rendered_gates.py
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib"))
from profile_editor import PROFILE_SCHEMA, PROFILE_FIELD_GROUPS, collect_profile_values  # noqa: E402

import yaml  # noqa: E402


class _FakeRow:
    def __init__(self, value):
        self.value = value


def _query_one_factory(values_by_id):
    """Stub for collect_profile_values' injected query_one: returns a fake row
    for known widget ids, raises for everything else (the collector swallows
    per-field lookup failures, mirroring absent widgets)."""
    def query_one(selector, _cls=None):
        widget_id = selector.lstrip("#")
        if widget_id in values_by_id:
            return _FakeRow(values_by_id[widget_id])
        raise LookupError(widget_id)
    return query_one


class TestRenderedGatesRegistration(unittest.TestCase):

    def test_schema_and_group(self):
        self.assertEqual(PROFILE_SCHEMA.get("rendered_gates"), ("list", None))
        gates_group = dict(PROFILE_FIELD_GROUPS)["Gates"]
        self.assertIn("rendered_gates", gates_group)


class TestRenderedGatesRoundTrip(unittest.TestCase):

    PREFIX = "test"

    def _collect(self, text_value, base=None):
        values = {f"profile_str_rendered_gates__{self.PREFIX}": text_value}
        data, errors = collect_profile_values(
            _query_one_factory(values), base or {"name": "p"},
            id_prefix=self.PREFIX)
        self.assertEqual(errors, [])
        return data

    def test_explicit_empty_survives_collect_serialize_load(self):
        # The literal `[]` text writes a present-but-EMPTY list...
        data = self._collect("[]")
        self.assertIn("rendered_gates", data)
        self.assertEqual(data["rendered_gates"], [])
        # ...and survives YAML serialize → load with the key still PRESENT.
        loaded = yaml.safe_load(yaml.dump(data))
        self.assertIn("rendered_gates", loaded)
        self.assertEqual(loaded["rendered_gates"], [])

    def test_empty_text_clears_the_key(self):
        # Blank field = unset (fallback-to-default_gates), NOT an empty list.
        data = self._collect("", base={"name": "p", "rendered_gates": ["x"]})
        self.assertNotIn("rendered_gates", data)

    def test_csv_text_parses_to_list(self):
        data = self._collect("risk_evaluated, tests_pass")
        self.assertEqual(data["rendered_gates"], ["risk_evaluated", "tests_pass"])

    def test_render_seam_distinguishes_empty_from_unset(self):
        # The real render entry point must honor key-presence: an explicit []
        # renders NOTHING even though default_gates is nonempty; unset falls
        # back to default_gates.
        from skill_template import render_skill
        with tempfile.TemporaryDirectory() as tmp:
            tpl = Path(tmp) / "probe.md"
            tpl.write_text("N={{ rendered_set | length }}", encoding="utf-8")
            explicit_empty = {"name": "p", "default_gates": ["risk_evaluated"],
                              "rendered_gates": []}
            unset = {"name": "p", "default_gates": ["risk_evaluated"]}
            self.assertEqual(render_skill(tpl, explicit_empty, "claude"), "N=0")
            self.assertEqual(render_skill(tpl, unset, "claude"), "N=1")


if __name__ == "__main__":
    unittest.main()
