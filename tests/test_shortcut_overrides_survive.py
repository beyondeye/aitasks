#!/usr/bin/env python3
"""A binding's action id is persisted user config, not an internal name (t1705_7).

`keybinding_registry.register_app_bindings` resolves a user's key override with
``overrides.get(str(binding.action))`` against the ``shortcuts:`` section of
``userconfig.yaml``, scoped per app. The action string is therefore a PUBLIC,
PERSISTED IDENTIFIER — renaming one silently orphans every override that names
it, with no error anywhere: the customized key just reverts to the default.

This module exists because t1705_7's first draft did exactly that. It widened
the `P` filter to hide frozen agents as well as parked ones and renamed the
action to match the new `_hide_inactive` state. The behaviour was right; the
rename would have reverted a customized `P` to default in BOTH the `monitor` and
`minimonitor` scopes. A Python method alias would not have saved it either —
the registry keys off the string in ``BINDINGS``, and Textual dispatches
``action_<that string>``.

So the pin is deliberately about the ID, not the label: descriptions are stored
as a *value* in ``_DEFAULTS`` and are free to change (this one did).

Run: python3 tests/test_shortcut_overrides_survive.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts"))
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))

import keybinding_registry  # noqa: E402
from textual.binding import Binding  # noqa: E402

#: Widened by t1705_7 to hide frozen agents too. The id must NOT follow.
FILTER_ACTION = "toggle_parked_visibility"

#: Both apps register their own scope, so an orphaned override in one would be
#: invisible from the other.
SCOPES = ("monitor", "minimonitor")


class _RegistryCase(unittest.TestCase):
    def setUp(self) -> None:
        keybinding_registry._DEFAULTS.clear()
        self.addCleanup(keybinding_registry._DEFAULTS.clear)

    def resolve(self, scope, bindings, overrides):
        with patch.object(keybinding_registry, "load_user_overrides",
                          lambda: overrides):
            return keybinding_registry.register_app_bindings(scope, bindings)


class ActionIdIsPersistedTests(_RegistryCase):
    """The mechanism, shown on a synthetic binding first."""

    def test_an_override_is_resolved_by_the_action_string(self):
        out = self.resolve(
            "monitor", [Binding("P", FILTER_ACTION, "Parked/frozen")],
            {"monitor": {FILTER_ACTION: "ctrl+p"}},
        )
        self.assertEqual(out[0].key, "ctrl+p")

    def test_renaming_the_action_orphans_the_override_silently(self):
        """THE failure this module exists to prevent. No exception, no warning —
        the key just goes back to its default."""
        out = self.resolve(
            "monitor", [Binding("P", "toggle_inactive_visibility", "…")],
            {"monitor": {FILTER_ACTION: "ctrl+p"}},
        )
        self.assertEqual(
            out[0].key, "P",
            "a renamed action silently ignored the user's override — which is "
            "exactly why the id must not be renamed",
        )

    def test_the_description_is_free_to_change(self):
        """Labels are a VALUE in `_DEFAULTS`, never a key, so widening the
        binding's text is safe. That asymmetry is the whole reason the id can
        stay while the behaviour changes."""
        out = self.resolve(
            "monitor", [Binding("P", FILTER_ACTION, "a completely new label")],
            {"monitor": {FILTER_ACTION: "ctrl+p"}},
        )
        self.assertEqual(out[0].key, "ctrl+p")


class RealAppBindingsTests(_RegistryCase):
    """The same, against the apps' actual BINDINGS."""

    def _bindings(self, scope):
        if scope == "monitor":
            from monitor.monitor_app import MonitorApp
            return list(MonitorApp.BINDINGS)
        from monitor.minimonitor_app import MiniMonitorApp
        return list(MiniMonitorApp.BINDINGS)

    def test_a_customized_filter_key_survives_in_both_scopes(self):
        for scope in SCOPES:
            with self.subTest(scope=scope):
                self.setUp()
                out = self.resolve(
                    scope, self._bindings(scope),
                    {scope: {FILTER_ACTION: "ctrl+p"}},
                )
                got = [b for b in out if b.action == FILTER_ACTION]
                self.assertEqual(len(got), 1, "the filter binding vanished")
                self.assertEqual(
                    got[0].key, "ctrl+p",
                    f"the user's {scope} override for the parked/frozen filter "
                    f"was not applied — its action id moved",
                )

    def test_the_filter_action_id_is_still_the_published_one(self):
        for scope in SCOPES:
            with self.subTest(scope=scope):
                actions = {b.action for b in self._bindings(scope)}
                self.assertIn(
                    FILTER_ACTION, actions,
                    f"{scope} no longer publishes {FILTER_ACTION!r}; every "
                    f"existing user override for it is now orphaned",
                )

    def test_the_new_frozen_actions_are_registered_in_both_scopes(self):
        """The new ids are equally public from the moment they ship — a user can
        rebind them today, so they carry the same no-rename obligation."""
        for scope in SCOPES:
            with self.subTest(scope=scope):
                self.setUp()
                out = self.resolve(scope, self._bindings(scope), {})
                actions = {b.action for b in out}
                self.assertIn("freeze_current", actions)
                self.assertIn("freeze_all", actions)

    def test_overrides_for_the_new_actions_resolve_too(self):
        for scope in SCOPES:
            with self.subTest(scope=scope):
                self.setUp()
                out = self.resolve(
                    scope, self._bindings(scope),
                    {scope: {"freeze_all": "ctrl+z"}},
                )
                got = [b for b in out if b.action == "freeze_all"]
                self.assertEqual(got[0].key, "ctrl+z")


if __name__ == "__main__":
    unittest.main(verbosity=2)
