"""Integration / contract tests for the brainstorm ``module_sync`` apply +
scan-bundle path (t913).

Risk-mitigation ("after") coverage for t756_4. The existing
``test_brainstorm_module_sync.py`` covers the happy path and refusal at *unit*
level, but it ``patch``-es out all three scan helpers
(``_sync_touched_files`` / ``_sync_scoped_diff`` / ``_sync_explain_context``).
So the genuinely-new subprocess + large-bundle surface that t756_4's risk
evaluation flagged — real ``git log --grep=(tN)``, the ``--since
last_synced_at`` horizon, the 60k truncation cap, and the
``aitask_explain_context.sh`` shell-out — was untested. This module hardens it,
paralleling ``test_brainstorm_module_ops_integration.py`` (t906), including its
Group D ``_StubRepo`` pattern (subprocess + stdout-parse boundary against a
stubbed shell script).

  A. Apply round-trip — drive a real worktree fixture through
     ``apply_module_syncer_output``: single-parent node, module-HEAD advance,
     umbrella HEAD untouched, ``last_synced_at`` stamp, and the group↔agent
     round-trip the poller dispatch relies on (plus a re-sync that chains off
     the prior synced node).
  B. Live scan bundling — exercise ``register_module_syncer`` against a *real*
     git repo and a stubbed ``aitask_explain_context.sh`` (NOT patched): the
     three Sync Sources streams, the ``--since`` horizon, the 60k truncation
     cap, the explain-context unavailable notice, and the empty-streams path.
  C. Refuse path / decision contract — ``register_module_syncer`` raises both
     when the module has no linked task AND when it has no source HEAD.

Scope honesty: the wizard's Next-disable predicate
(``_config_module_sync`` in ``brainstorm_app.py``,
``disabled = not bool(linked) or not bool(source_head)``) is a Textual App
method that mounts widgets and cannot run headless — mirroring t906 Group B's
headless-poller note. Group C therefore asserts the two raise-conditions in
``register_module_syncer`` that *back* that predicate, not the live Button
state.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from brainstorm.brainstorm_crew import (  # noqa: E402
    _SYNC_DIFF_MAX_CHARS,
    register_module_syncer,
)
from brainstorm.brainstorm_dag import (  # noqa: E402
    GRAPH_STATE_FILE,
    NODES_DIR,
    PROPOSALS_DIR,
    _read_graph_state,
    create_node,
    get_head,
    read_node,
    set_head,
)
from brainstorm.brainstorm_session import (  # noqa: E402
    _agent_to_group_name,
    _module_syncer_needs_apply,
    apply_module_syncer_output,
    record_operation,
)

TASK = "756"


def _seed_base(wt: Path, module_tasks=None, last_synced=None,
               with_parser_head=True) -> None:
    """Seed a worktree: umbrella root + (optionally) a 'parser' module subgraph.

    ``with_parser_head=False`` seeds the umbrella only — used by the refuse-path
    test for "linked task present but module has no HEAD".
    """
    (wt / NODES_DIR).mkdir(parents=True, exist_ok=True)
    (wt / PROPOSALS_DIR).mkdir(parents=True, exist_ok=True)
    (wt / GRAPH_STATE_FILE).write_text(
        yaml.safe_dump({
            "current_head": None,
            "current_heads": {},
            "history": {},
            "next_node_id": 1,
            "active_dimensions": [],
            "module_tasks": module_tasks or {},
            "last_synced_at": last_synced or {},
        }),
        encoding="utf-8",
    )
    create_node(
        wt, "n000_init", [], "Umbrella", {"component_core": "Core"},
        "## Overview\nUmbrella\n", "bootstrap",
    )
    set_head(wt, "n000_init")
    if with_parser_head:
        create_node(
            wt, "n001_parser", ["n000_init"], "Parser root",
            {"component_parser": "Parser"}, "## Overview\nParser\n",
            "module_decompose_001", module_label="parser",
        )
        set_head(wt, "n001_parser", module="parser")


def _sync_output(node_id: str) -> str:
    return f"""--- NODE_YAML_START ---
node_id: {node_id}
parents: []
description: "Synced parser to as-built"
proposal_file: br_proposals/{node_id}.md
created_at: "2026-06-02 12:00"
component_parser: "Parser as implemented"
--- NODE_YAML_END ---
--- PROPOSAL_START ---
## Overview
Refreshed parser proposal reflecting the landed task.
--- PROPOSAL_END ---
"""


# --------------------------------------------------------------------------- #
# Group A — apply path round-trip (worktree fixture)
# --------------------------------------------------------------------------- #
class ApplyRoundTripTests(unittest.TestCase):
    def test_apply_round_trip_all_properties(self):
        """One apply asserts every apply contract at once + group↔agent round-trip."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt, module_tasks={"parser": "756_8"})
            (wt / "module_syncer_001_output.md").write_text(
                _sync_output("n002_module_syncer_001"), encoding="utf-8"
            )
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                record_operation(
                    TASK, "module_sync_001", "module_sync",
                    ["module_syncer_001"], "n001_parser", subgraph="parser",
                )
                self.assertTrue(
                    _module_syncer_needs_apply(TASK, "module_syncer_001")
                )
                new_id = apply_module_syncer_output(TASK, "module_syncer_001")

            node = read_node(wt, new_id)
            self.assertEqual(node["parents"], ["n001_parser"])  # single parent
            self.assertEqual(node["module_label"], "parser")
            self.assertEqual(get_head(wt, module="parser"), new_id)  # module advanced
            self.assertEqual(get_head(wt), "n000_init")  # umbrella untouched
            synced = _read_graph_state(wt).get("last_synced_at", {})
            self.assertIn("parser", synced)
            self.assertTrue(synced["parser"])  # non-empty timestamp
            # Poller dispatch contract: the syncer agent name resolves back to
            # its op group, which is how apply scopes the subgraph.
            self.assertEqual(
                _agent_to_group_name("module_syncer_001"), "module_sync_001"
            )

    def test_resync_chains_off_prior_synced_head(self):
        """A second sync's node is single-parented on the FIRST synced node."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt, module_tasks={"parser": "756_8"})
            (wt / "module_syncer_001_output.md").write_text(
                _sync_output("n002_module_syncer_001"), encoding="utf-8"
            )
            (wt / "module_syncer_002_output.md").write_text(
                _sync_output("n003_module_syncer_002"), encoding="utf-8"
            )
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                record_operation(
                    TASK, "module_sync_001", "module_sync",
                    ["module_syncer_001"], "n001_parser", subgraph="parser",
                )
                first = apply_module_syncer_output(TASK, "module_syncer_001")
                record_operation(
                    TASK, "module_sync_002", "module_sync",
                    ["module_syncer_002"], first, subgraph="parser",
                )
                second = apply_module_syncer_output(TASK, "module_syncer_002")

            self.assertEqual(read_node(wt, second)["parents"], [first])
            self.assertEqual(get_head(wt, module="parser"), second)
            self.assertEqual(get_head(wt), "n000_init")  # umbrella still untouched


# --------------------------------------------------------------------------- #
# Group B — live scan bundling against a real git repo + stubbed explain script
# --------------------------------------------------------------------------- #
class _GitSyncRepo:
    """Context manager: a temp git repo that is ALSO the brainstorm session dir.

    The scan helpers (``_sync_touched_files`` / ``_sync_scoped_diff`` /
    ``_sync_explain_context``) run from ``cwd`` (the repo root), so this fixture
    ``git init``s a real repo, seeds the brainstorm graph state in the same dir
    (``session_dir`` == repo root), drops a stub ``aitask_explain_context.sh``,
    and switches ``cwd`` in. ``register_module_syncer`` is then driven against it
    with only ``_run_addwork`` / ``_write_agent_input`` patched — the three scan
    helpers run for real.
    """

    def __init__(self, module_tasks, last_synced=None,
                 explain_stdout="EXPLAIN_MARKER", explain_rc=0,
                 with_parser_head=True):
        self._module_tasks = module_tasks
        self._last_synced = last_synced
        self._explain_stdout = explain_stdout
        self._explain_rc = explain_rc
        self._with_parser_head = with_parser_head
        self.root = None
        self._tmp = None
        self._prev_cwd = None

    def _git(self, *args, env=None):
        full_env = dict(os.environ)
        if env:
            full_env.update(env)
        subprocess.run(
            ["git", *args], cwd=self.root, env=full_env,
            check=True, capture_output=True, text=True,
        )

    def __enter__(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "Test")
        self._git("config", "commit.gpgsign", "false")
        _seed_base(
            self.root, module_tasks=self._module_tasks,
            last_synced=self._last_synced,
            with_parser_head=self._with_parser_head,
        )
        scripts = self.root / ".aitask-scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        stub = scripts / "aitask_explain_context.sh"
        if self._explain_rc == 0:
            stub.write_text(
                "#!/usr/bin/env bash\n"
                f"echo {self._explain_stdout!r}\n",
                encoding="utf-8",
            )
        else:
            stub.write_text(
                "#!/usr/bin/env bash\n"
                'echo "explain boom" >&2\n'
                f"exit {self._explain_rc}\n",
                encoding="utf-8",
            )
        stub.chmod(0o755)
        self._prev_cwd = os.getcwd()
        os.chdir(self.root)
        return self

    def commit_file(self, rel_path, content, task="756_8", date=None):
        """Write+commit a file with a ``(t<task>)``-suffixed message.

        ``date`` (e.g. ``"2026-05-01T09:00:00"``) pins author+committer dates so
        the ``--since`` horizon test is deterministic.
        """
        p = self.root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        self._git("add", rel_path)
        env = None
        if date:
            env = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
        self._git("commit", "-q", "-m", f"feature: change (t{task})", env=env)

    def write_plan(self, task_id, content):
        """Drop a linked-task plan where ``_resolve_linked_plan_path`` looks."""
        parent = task_id.split("_", 1)[0] if "_" in task_id else task_id
        d = self.root / "aiplans" / f"p{parent}"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"p{task_id}_x.md").write_text(content, encoding="utf-8")

    def __exit__(self, *exc):
        if self._prev_cwd is not None:
            os.chdir(self._prev_cwd)
        return False


def _register_and_capture(repo, **kwargs):
    """Run register_module_syncer against ``repo`` capturing the bundled input.

    Only the launch/write side-effects are patched; the three scan helpers run
    for real against the repo's git history and stub script.
    """
    captured = {}

    def _capture_input(session_dir, agent_name, content):
        captured["agent"] = agent_name
        captured["content"] = content

    with patch("brainstorm.brainstorm_crew._run_addwork"), \
         patch("brainstorm.brainstorm_crew._write_agent_input", _capture_input):
        agent = register_module_syncer(
            repo.root, "crew-756", "parser", "module_sync_001", **kwargs
        )
    captured["returned_agent"] = agent
    return captured


class LiveScanBundlingTests(unittest.TestCase):
    def test_register_bundles_live_git_and_explain(self):
        with _GitSyncRepo(module_tasks={"parser": "756_8"}) as repo:
            repo.commit_file("a.py", "ALPHA_LINE\n")
            repo.write_plan("756_8", "## Final Implementation Notes\nPLAN_MARKER\n")
            cap = _register_and_capture(
                repo, instructions="focus on the cache path"
            )

        self.assertEqual(cap["returned_agent"], "module_syncer_001")
        body = cap["content"]
        self.assertIn("## Sync Sources", body)
        self.assertIn("t756_8", body)            # linked task reference
        self.assertIn("a.py", body)              # real git diff scoped to touched file
        self.assertIn("ALPHA_LINE", body)        # the actual added hunk
        self.assertIn("PLAN_MARKER", body)       # linked-task plan stream
        self.assertIn("EXPLAIN_MARKER", body)    # stubbed explain-context stdout
        self.assertIn("focus on the cache path", body)

    def test_since_horizon_excludes_pre_sync_commits(self):
        with _GitSyncRepo(
            module_tasks={"parser": "756_8"},
            last_synced={"parser": "2026-05-15 00:00"},
        ) as repo:
            repo.commit_file("a.py", "OLD_CONTENT\n", date="2026-05-01T09:00:00")
            repo.commit_file("b.py", "NEW_CONTENT\n", date="2026-06-01T09:00:00")
            cap = _register_and_capture(repo)

        body = cap["content"]
        # Only the post-horizon commit's file is in the scoped diff.
        self.assertIn("b.py", body)
        self.assertIn("NEW_CONTENT", body)
        self.assertNotIn("OLD_CONTENT", body)
        self.assertNotIn("a.py", body)

    def test_scoped_diff_truncation_cap(self):
        with _GitSyncRepo(module_tasks={"parser": "756_8"}) as repo:
            big = ("a" * 100 + "\n") * 800  # ~80k chars, exceeds the 60k cap
            repo.commit_file("big.py", big)
            cap = _register_and_capture(repo)

        body = cap["content"]
        self.assertIn(
            f"[... scoped diff truncated at {_SYNC_DIFF_MAX_CHARS} chars ...]",
            body,
        )

    def test_explain_context_unavailable_notice(self):
        with _GitSyncRepo(
            module_tasks={"parser": "756_8"}, explain_rc=1
        ) as repo:
            repo.commit_file("a.py", "ALPHA_LINE\n")  # touched non-empty → explain runs
            cap = _register_and_capture(repo)

        self.assertIn("(explain-context unavailable:", cap["content"])

    def test_no_matching_commits_yields_empty_stream_placeholders(self):
        # Linked task 756_9 has no (t756_9) commits in this repo.
        with _GitSyncRepo(module_tasks={"parser": "756_9"}) as repo:
            repo.commit_file("a.py", "ALPHA_LINE\n", task="756_8")  # different task
            cap = _register_and_capture(repo)

        body = cap["content"]
        self.assertIn("(no scoped changes found since last sync)", body)
        self.assertIn("(no explain-context available)", body)


# --------------------------------------------------------------------------- #
# Group C — refuse path / decision contract (backs the wizard Next-disable)
# --------------------------------------------------------------------------- #
class RefuseGuardContractTests(unittest.TestCase):
    def test_refuses_without_linked_task(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(wt, module_tasks={})  # no linkage
            with self.assertRaisesRegex(ValueError, "requires a linked task"):
                register_module_syncer(wt, "crew-756", "parser", "module_sync_001")

    def test_refuses_without_source_head(self):
        """Linked task present, but the module has no HEAD — the second half of
        the wizard's ``disabled = not linked or not source_head`` predicate."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_base(
                wt, module_tasks={"parser": "756_8"}, with_parser_head=False
            )
            with self.assertRaisesRegex(ValueError, "requires a HEAD"):
                register_module_syncer(wt, "crew-756", "parser", "module_sync_001")


if __name__ == "__main__":
    unittest.main()
