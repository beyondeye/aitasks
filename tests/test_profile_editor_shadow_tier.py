"""Registration + round-trip tests for `shadow_impl_review_tier` (t1311).

The key is the shadow's default implementation-review effort tier. It has to be
registered at three sites in `.aitask-scripts/lib/profile_editor.py` for the
settings TUI to render it at all:

  * ``PROFILE_SCHEMA``      — type + allowed values (drives the cycle widget)
  * ``PROFILE_FIELD_INFO``  — summary + detail shown next to the field
  * ``PROFILE_FIELD_GROUPS``— which group the field appears under

A key registered in only some of those renders wrong (or not at all) while every
other test still passes, which is exactly how the framework accumulated keys
documented in one place and registered in another.

The enum values are the full tier words used by ``impl-challenge.md`` itself
(``quick`` / ``default`` / ``advanced`` / ``deep``) — deliberately NOT the
single-letter ``q``/``s``/``e`` shape ``qa_tier`` uses, which already disagrees
with its own documentation. That choice is pinned here so it cannot drift back.

Run: python3 tests/test_profile_editor_shadow_tier.py
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib"))
from profile_editor import (  # noqa: E402
    PROFILE_SCHEMA,
    PROFILE_FIELD_GROUPS,
    PROFILE_FIELD_INFO,
    collect_profile_values,
)

import yaml  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
KEY = "shadow_impl_review_tier"
TIERS = ["quick", "default", "advanced", "deep"]


class _FakeCycleField:
    """Stands in for CycleField, whose enum value is read via `current_value`
    (not `.value` — the string/int rows use that)."""

    def __init__(self, value):
        self.current_value = value


def _query_one_factory(values_by_id):
    def query_one(selector, _cls=None):
        widget_id = selector.lstrip("#")
        if widget_id in values_by_id:
            return _FakeCycleField(values_by_id[widget_id])
        raise LookupError(widget_id)
    return query_one


class TestShadowTierRegistration(unittest.TestCase):

    def test_schema_entry(self):
        self.assertEqual(PROFILE_SCHEMA.get(KEY), ("enum", TIERS))

    def test_enum_uses_full_tier_words_not_single_letters(self):
        """Pins the deliberate divergence from qa_tier's q/s/e shape."""
        _, values = PROFILE_SCHEMA[KEY]
        self.assertTrue(
            all(len(v) > 1 for v in values),
            f"{KEY} must use full tier words matching impl-challenge.md's own "
            f"vocabulary, not single-letter codes: {values}",
        )

    def test_field_group_membership(self):
        groups = dict(PROFILE_FIELD_GROUPS)
        self.assertIn(
            "Shadow Review", groups,
            "PROFILE_FIELD_GROUPS has no 'Shadow Review' group — the key would "
            "be registered in the schema but never rendered by the settings TUI.",
        )
        self.assertIn(KEY, groups["Shadow Review"])

    def test_every_grouped_key_is_in_the_schema(self):
        """A group entry naming an unregistered key renders a broken row."""
        for group, keys in PROFILE_FIELD_GROUPS:
            for key in keys:
                if key in ("name", "description"):
                    continue  # Identity fields are string-typed by convention.
                with self.subTest(group=group, key=key):
                    self.assertIn(key, PROFILE_SCHEMA)

    def test_field_info_present_and_states_the_activation_condition(self):
        self.assertIn(KEY, PROFILE_FIELD_INFO)
        summary, detail = PROFILE_FIELD_INFO[KEY]
        self.assertTrue(summary.strip())
        # The key is inert until default_profiles.shadow names the profile —
        # the settings TUI is the point of editing, so it must say so there.
        self.assertIn("default_profiles.shadow", detail)
        for tier in TIERS:
            self.assertIn(tier, detail, f"detail text never mentions tier {tier!r}")


class TestShadowTierRoundTrip(unittest.TestCase):

    PREFIX = "test"

    def _collect(self, value, base=None):
        values = {f"profile_{KEY}__{self.PREFIX}": value}
        data, errors = collect_profile_values(
            _query_one_factory(values), base or {"name": "p"},
            id_prefix=self.PREFIX)
        self.assertEqual(errors, [])
        return data

    def test_each_tier_round_trips(self):
        for tier in TIERS:
            with self.subTest(tier=tier):
                data = self._collect(tier)
                self.assertEqual(data.get(KEY), tier)
                reloaded = yaml.safe_load(yaml.safe_dump(data))
                self.assertEqual(reloaded.get(KEY), tier)

    def test_unset_is_absent_not_empty(self):
        """`(unset)` must remove the key so the tier prompt comes back."""
        data = self._collect("(unset)", base={"name": "p", KEY: "advanced"})
        self.assertNotIn(KEY, data)


class TestShippedProfileValues(unittest.TestCase):
    """AC 6: fast ships the advanced tier; default leaves it unset."""

    def _load(self, rel):
        path = REPO_ROOT / rel
        self.assertTrue(path.is_file(), f"missing profile: {rel}")
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def test_fast_profiles_ship_advanced(self):
        for rel in ("seed/profiles/fast.yaml", "aitasks/metadata/profiles/fast.yaml"):
            with self.subTest(profile=rel):
                self.assertEqual(self._load(rel).get(KEY), "advanced")

    def test_default_profiles_leave_it_unset(self):
        for rel in ("seed/profiles/default.yaml", "aitasks/metadata/profiles/default.yaml"):
            with self.subTest(profile=rel):
                self.assertNotIn(KEY, self._load(rel))

    def test_every_shipped_value_is_a_registered_tier(self):
        """A typo'd tier would render a prompt-skipping instruction naming a
        tier that has no section in impl-challenge.md."""
        for path in sorted((REPO_ROOT / "seed" / "profiles").glob("*.yaml")) + sorted(
            (REPO_ROOT / "aitasks" / "metadata" / "profiles").glob("*.yaml")
        ):
            value = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get(KEY)
            if value is None:
                continue
            with self.subTest(profile=str(path.relative_to(REPO_ROOT))):
                self.assertIn(value, TIERS)


if __name__ == "__main__":
    unittest.main()
