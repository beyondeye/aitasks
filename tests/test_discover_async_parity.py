"""Parity tests for async aitasks session discovery.

t1111_3 adds `discover_aitasks_sessions_async()` for monitor refresh paths.
These tests pin it to the same behavior as the existing sync discovery helper.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__), "..", ".aitask-scripts", "lib"
    ),
)

import agent_launch_utils as alu  # noqa: E402


class _FakeTmux:
    def __init__(self, responses: dict[tuple[str, ...], tuple[int, str]]) -> None:
        self.responses = responses
        self.sync_calls: list[tuple[str, ...]] = []
        self.async_calls: list[tuple[str, ...]] = []

    def _response(self, args: list[str]) -> tuple[int, str]:
        return self.responses.get(tuple(args), (1, ""))

    def run(self, args: list[str], timeout: float = 5.0) -> tuple[int, str]:
        self.sync_calls.append(tuple(args))
        return self._response(args)

    async def run_async(
        self, args: list[str], timeout: float = 5.0
    ) -> tuple[int, str]:
        self.async_calls.append(tuple(args))
        return self._response(args)


def _make_project(
    root: Path,
    *,
    default_session: str | None = None,
    project_group: str | None = None,
) -> Path:
    metadata = root / "aitasks" / "metadata"
    metadata.mkdir(parents=True)
    lines = ["project:\n", f"  name: {root.name}\n"]
    if project_group is not None:
        lines.append(f"  project_group: {project_group}\n")
    if default_session is not None:
        lines.extend(["tmux:\n", f"  default_session: {default_session}\n"])
    (metadata / "project_config.yaml").write_text("".join(lines))
    return root


class DiscoverAitasksSessionsAsyncParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        self._saved_tmux = alu._TMUX

    def tearDown(self) -> None:
        alu._TMUX = self._saved_tmux
        os.environ.pop("AITASKS_PROJECTS_INDEX", None)
        self._tmpdir.cleanup()

    def test_async_matches_sync_for_live_registry_group_and_registered_rows(self):
        pane_root = _make_project(self.tmp / "pane_proj")
        env_root = _make_project(
            self.tmp / "env_proj", project_group="cfg_env"
        )
        registered_root = _make_project(
            self.tmp / "registered_proj",
            default_session="aaa_registered",
            project_group="cfg_registered",
        )
        stale_root = self.tmp / "stale_proj"

        registry = self.tmp / "projects.yaml"
        registry.write_text(
            "projects:\n"
            "  - name: pane_alias\n"
            f"    path: {pane_root}\n"
            "    project_group: reg_live\n"
            "  - name: registered_proj\n"
            f"    path: {registered_root}\n"
            "    project_group: reg_registered\n"
            "  - name: stale_proj\n"
            f"    path: {stale_root}\n"
            "    project_group: reg_stale\n"
        )
        os.environ["AITASKS_PROJECTS_INDEX"] = str(registry)

        responses = {
            ("list-sessions", "-F", "#{session_name}"): (
                0,
                "pane_sess\nenv_sess\n",
            ),
            (
                "list-panes", "-s", "-t", "=pane_sess",
                "-F", "#{pane_current_path}",
            ): (0, f"{pane_root / 'subdir'}\n"),
            (
                "list-panes", "-s", "-t", "=env_sess",
                "-F", "#{pane_current_path}",
            ): (0, f"{self.tmp / 'not_a_project'}\n"),
            ("show-environment", "-g", "AITASKS_PROJECT_env_sess"): (
                0,
                f"AITASKS_PROJECT_env_sess={env_root}\n",
            ),
        }
        fake_tmux = _FakeTmux(responses)
        alu._TMUX = fake_tmux

        sync_result = alu.discover_aitasks_sessions(include_registered=True)
        async_result = asyncio.run(
            alu.discover_aitasks_sessions_async(include_registered=True)
        )

        self.assertEqual(async_result, sync_result)
        by_session = {s.session: s for s in async_result}
        self.assertEqual(by_session["pane_sess"].project_group, "reg_live")
        self.assertEqual(by_session["env_sess"].project_group, "cfg_env")
        self.assertEqual(
            by_session["aaa_registered"].project_group, "reg_registered"
        )
        self.assertTrue(by_session["aitasks"].is_stale)
        self.assertEqual(by_session["aitasks"].project_group, "reg_stale")
        self.assertIn(
            ("show-environment", "-g", "AITASKS_PROJECT_env_sess"),
            fake_tmux.async_calls,
        )
        self.assertNotIn(
            ("show-environment", "-g", "AITASKS_PROJECT_pane_sess"),
            fake_tmux.async_calls,
        )


if __name__ == "__main__":
    unittest.main()
