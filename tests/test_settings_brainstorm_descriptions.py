"""Guard: brainstorm agent-default settings rows stay fully described and
free of orphaned config keys.

The settings "Agent Defaults" tab renders one row per brainstorm agent type and
its paired launch mode, pulling helper text from
``settings_app.OPERATION_DESCRIPTIONS``. The set of *live* types is the single
source of truth ``brainstorm_crew.BRAINSTORM_AGENT_TYPES``. These tests derive
their expectations from that set (rather than hardcoding a copy) so the coverage
gap cannot silently reopen when an agent type is added or removed.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# settings_app lives under .aitask-scripts/settings; brainstorm under .aitask-scripts
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "settings"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from settings_app import OPERATION_DESCRIPTIONS  # noqa: E402
from brainstorm.brainstorm_crew import BRAINSTORM_AGENT_TYPES  # noqa: E402

CONFIG_PATH = REPO_ROOT / "aitasks" / "metadata" / "codeagent_config.json"


class TestBrainstormSettingsDescriptions(unittest.TestCase):
    def test_every_live_type_has_description(self):
        """Each live brainstorm type needs helper text for its agent-string row
        and its paired launch-mode row."""
        for atype in BRAINSTORM_AGENT_TYPES:
            self.assertIn(
                f"brainstorm-{atype}", OPERATION_DESCRIPTIONS,
                f"missing agent-string description for brainstorm-{atype}",
            )
            self.assertIn(
                f"brainstorm-{atype}-launch-mode", OPERATION_DESCRIPTIONS,
                f"missing launch-mode description for brainstorm-{atype}",
            )

    def test_no_orphan_brainstorm_defaults(self):
        """Project config must not carry brainstorm-* defaults for types that no
        longer exist (e.g. the removed detailer/patcher)."""
        defaults = json.loads(CONFIG_PATH.read_text()).get("defaults", {})
        for key in defaults:
            if not key.startswith("brainstorm-"):
                continue
            atype = key[len("brainstorm-"):]
            if atype.endswith("-launch-mode"):
                atype = atype[: -len("-launch-mode")]
            self.assertIn(
                atype, BRAINSTORM_AGENT_TYPES,
                f"orphaned config key {key!r} maps to no live brainstorm type",
            )


if __name__ == "__main__":
    unittest.main()
