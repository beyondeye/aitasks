"""Transcript-store fallback resolver tests (t1705_3).

`newest_transcript_for` is what recovers a codeagent session id when the
SessionStart hook never fired. For interactive codex that is not a backstop but
THE mechanism: codex 0.153.4 fires SessionStart under `codex exec` only.

WHY THIS SUITE IS NOT OPTIONAL
------------------------------
Nothing else exercises the resolver. The hook-install suites all pass whether
the layout assumptions are right or wrong, so a bad assumption ships green and
surfaces only as "restores never have a session id". Two assumptions in the
original plan were in fact wrong, and both are pinned here as regressions:

  * the claude project-directory encoding replaces BOTH '/' and '_' with '-'.
    The '/'-only rule the plan specified matched 2 of 6 real directories --
    every path containing an underscore resolved to a directory that does not
    exist. `test_underscore_path_resolves` is that case.
  * codex puts `cwd` and `session_id` under `payload`, not at the top level.
    A top-level lookup returns nothing for EVERY codex session.
    `test_codex_reads_payload_not_top_level` is that case.

Ground truth for both lives in tests/data/session_hooks/transcript_layout.json.

The MISS REASON is part of the contract and is asserted throughout: without it
a wrong layout is indistinguishable from "this agent genuinely has no session",
which is exactly how a silent regression survives.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_sessions  # noqa: E402

LAYOUT_FIXTURE = REPO_ROOT / "tests" / "data" / "session_hooks" / "transcript_layout.json"


class _TranscriptTestCase(unittest.TestCase):
    """A synthetic HOME holding a claude and/or codex transcript store."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # --- builders ---------------------------------------------------------

    def write_claude(self, project_dir: str, session_id: str, cwd: str,
                     *, mtime: float | None = None, cwd_on_line: int = 3) -> Path:
        """A claude transcript. `cwd` deliberately does NOT appear on line 1 --
        that is what the real files look like (observed at lines 2-5)."""
        d = self.home / ".claude" / "projects" / project_dir
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{session_id}.jsonl"
        lines = []
        for i in range(cwd_on_line + 1):
            if i == cwd_on_line:
                lines.append({"type": "user", "sessionId": session_id, "cwd": cwd})
            else:
                lines.append({"type": "meta", "sessionId": session_id})
        path.write_text("\n".join(json.dumps(o) for o in lines) + "\n")
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def write_codex(self, session_id: str, cwd: str, *, date="2026/09/07",
                    mtime: float | None = None, top_level_cwd=False) -> Path:
        d = self.home / ".codex" / "sessions" / date
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"rollout-2026-09-07T12-49-50-{session_id}.jsonl"
        meta = {"timestamp": "2026-09-07T09:49:50Z", "ordinal": 0,
                "type": "session_meta",
                "payload": {"session_id": session_id, "cwd": cwd,
                            "originator": "codex-tui"}}
        if top_level_cwd:
            meta["cwd"] = cwd
        path.write_text(json.dumps(meta) + "\n" + json.dumps({"type": "turn"}) + "\n")
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def resolve(self, root, kind, env=None):
        # env={} by default: HERMETIC. Without it, a developer whose shell
        # exports CODEX_HOME or CLAUDE_CONFIG_DIR would have these tests scan
        # their real transcript store and pass or fail for the wrong reason.
        return agent_sessions.newest_transcript_for(
            root, kind, home=self.home, env={} if env is None else env)


class ClaudeLayoutTests(_TranscriptTestCase):
    def test_encode_rule_replaces_slash_and_underscore(self):
        self.assertEqual(
            agent_sessions.claude_project_dirname("/a/b_c/d"), "-a-b-c-d")

    def test_simple_path_resolves(self):
        root = os.path.realpath(str(self.home / "proj"))
        self.write_claude(agent_sessions.claude_project_dirname(root), "sid-1", root)
        sid, path, miss = self.resolve(root, "claudecode")
        self.assertEqual(sid, "sid-1")
        self.assertEqual(miss, "")
        self.assertTrue(path.endswith("sid-1.jsonl"))

    def test_underscore_path_resolves(self):
        """REGRESSION: the plan's '/'-only rule failed on every path with '_'."""
        root = os.path.realpath(str(self.home / "my_project_dir"))
        naive = root.replace("/", "-")
        actual = agent_sessions.claude_project_dirname(root)
        self.assertNotEqual(naive, actual, "fixture must exercise the difference")
        self.write_claude(actual, "sid-us", root)
        sid, _, miss = self.resolve(root, "claudecode")
        self.assertEqual((sid, miss), ("sid-us", ""))

    def test_cwd_not_on_first_line(self):
        """Real transcripts carry cwd at lines 2-5; a line-1 peek finds nothing."""
        root = os.path.realpath(str(self.home / "proj"))
        self.write_claude(agent_sessions.claude_project_dirname(root),
                          "sid-late", root, cwd_on_line=5)
        sid, _, miss = self.resolve(root, "claudecode")
        self.assertEqual((sid, miss), ("sid-late", ""))

    def test_unknown_encoding_still_resolves_by_scanning(self):
        """The encode rule is only PARTIALLY determined ('.' and ' ' unobserved),
        so a candidate whose directory name we cannot compute must still be
        found by verifying cwd across the store. This is the design property
        that stops an unobserved character from silently yielding no session."""
        root = os.path.realpath(str(self.home / "weird.dir name"))
        self.write_claude("some-encoding-we-did-not-predict", "sid-scan", root)
        sid, _, miss = self.resolve(root, "claudecode")
        self.assertEqual((sid, miss), ("sid-scan", ""))

    def test_selection_picks_the_newest(self):
        root = os.path.realpath(str(self.home / "proj"))
        d = agent_sessions.claude_project_dirname(root)
        self.write_claude(d, "old", root, mtime=1_000_000)
        self.write_claude(d, "new", root, mtime=2_000_000)
        sid, _, _ = self.resolve(root, "claudecode")
        self.assertEqual(sid, "new")

    def test_other_projects_are_not_matched(self):
        root = os.path.realpath(str(self.home / "mine"))
        other = os.path.realpath(str(self.home / "theirs"))
        self.write_claude(agent_sessions.claude_project_dirname(other), "sid-x", other)
        sid, _, miss = self.resolve(root, "claudecode")
        self.assertEqual((sid, miss), ("", agent_sessions.MISS_NO_PROJECT_DIR))

    def test_tie_break_is_deterministic(self):
        """Equal mtimes must not make the answer depend on readdir order."""
        root = os.path.realpath(str(self.home / "proj"))
        d = agent_sessions.claude_project_dirname(root)
        self.write_claude(d, "aaa", root, mtime=5_000_000)
        self.write_claude(d, "zzz", root, mtime=5_000_000)
        picks = {self.resolve(root, "claudecode")[0] for _ in range(5)}
        self.assertEqual(picks, {"zzz"}, "name-descending tie-break, stable")


class CodexLayoutTests(_TranscriptTestCase):
    def test_codex_reads_payload_not_top_level(self):
        """REGRESSION: the plan read a top-level 'cwd' that never exists."""
        root = os.path.realpath(str(self.home / "proj"))
        self.write_codex("01a07b46-2849-7612-bc01-ec1403808969", root)
        sid, path, miss = self.resolve(root, "codex")
        self.assertEqual(miss, "")
        self.assertEqual(sid, "01a07b46-2849-7612-bc01-ec1403808969")
        self.assertIn("rollout-", path)

    def test_date_partitioned_selection_picks_the_newest(self):
        root = os.path.realpath(str(self.home / "proj"))
        self.write_codex("01a00000-0000-7000-8000-000000000001", root,
                         date="2026/09/06", mtime=1_000_000)
        self.write_codex("01a00000-0000-7000-8000-000000000002", root,
                         date="2026/09/07", mtime=2_000_000)
        sid, _, _ = self.resolve(root, "codex")
        self.assertEqual(sid, "01a00000-0000-7000-8000-000000000002")

    def test_other_projects_are_not_matched(self):
        root = os.path.realpath(str(self.home / "mine"))
        other = os.path.realpath(str(self.home / "theirs"))
        self.write_codex("01a00000-0000-7000-8000-00000000000a", other)
        sid, _, miss = self.resolve(root, "codex")
        self.assertEqual((sid, miss), ("", agent_sessions.MISS_NO_MATCH))


class MissReasonTests(_TranscriptTestCase):
    def test_no_store_dir(self):
        for kind in ("claudecode", "codex"):
            with self.subTest(kind=kind):
                sid, path, miss = self.resolve("/whatever", kind)
                self.assertEqual((sid, path), ("", ""))
                self.assertEqual(miss, agent_sessions.MISS_NO_STORE_DIR)

    def test_empty_store(self):
        (self.home / ".claude" / "projects").mkdir(parents=True)
        (self.home / ".codex" / "sessions").mkdir(parents=True)
        self.assertEqual(self.resolve("/whatever", "claudecode")[2],
                         agent_sessions.MISS_NO_PROJECT_DIR)
        self.assertEqual(self.resolve("/whatever", "codex")[2],
                         agent_sessions.MISS_NO_MATCH)

    def test_unsupported_agent(self):
        sid, path, miss = self.resolve("/whatever", "opencode")
        self.assertEqual((sid, path), ("", ""))
        self.assertEqual(miss, agent_sessions.MISS_UNSUPPORTED_AGENT)

    def test_every_miss_reason_is_distinguishable(self):
        """The reason is the whole point: a wrong layout must not look like
        'this agent has no session'."""
        reasons = {
            agent_sessions.MISS_NO_STORE_DIR,
            agent_sessions.MISS_NO_PROJECT_DIR,
            agent_sessions.MISS_NO_MATCH,
            agent_sessions.MISS_UNSUPPORTED_AGENT,
        }
        self.assertEqual(len(reasons), 4)
        self.assertNotIn("", reasons)


class StoreRootOverrideTests(_TranscriptTestCase):
    """CLAUDE_CONFIG_DIR / CODEX_HOME relocate an agent's store.

    Ignoring them reports `no_store_dir` for sessions that exist -- forcing
    re-pick on exactly the path this fallback is meant to rescue. CODEX_HOME
    relocating sessions/ is established (the spike reads
    `find "$CODEX_HOME_DIR/sessions"`); for CLAUDE_CONFIG_DIR it is NOT, so
    both roots are searched and both behaviours are pinned below.
    """

    def _alt(self) -> Path:
        alt = self.home / "alt_config"
        alt.mkdir(parents=True, exist_ok=True)
        return alt

    def write_codex_at(self, base: Path, session_id: str, cwd: str) -> Path:
        d = base / "sessions" / "2026" / "09" / "07"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"rollout-2026-09-07T12-49-50-{session_id}.jsonl"
        path.write_text(json.dumps({
            "type": "session_meta",
            "payload": {"session_id": session_id, "cwd": cwd,
                        "originator": "codex-tui"}}) + "\n")
        return path

    def write_claude_at(self, base: Path, session_id: str, cwd: str) -> Path:
        d = base / "projects" / agent_sessions.claude_project_dirname(cwd)
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{session_id}.jsonl"
        path.write_text(
            json.dumps({"type": "meta", "sessionId": session_id}) + "\n"
            + json.dumps({"type": "user", "sessionId": session_id, "cwd": cwd}) + "\n")
        return path

    # --- codex (override ESTABLISHED) ------------------------------------

    def test_codex_home_override_is_found(self):
        root = os.path.realpath(str(self.home / "proj"))
        alt = self._alt()
        self.write_codex_at(alt, "01a00000-0000-7000-8000-0000000000c1", root)
        sid, _, miss = self.resolve(root, "codex", env={"CODEX_HOME": str(alt)})
        self.assertEqual((sid, miss),
                         ("01a00000-0000-7000-8000-0000000000c1", ""))

    def test_codex_without_the_override_reports_no_store(self):
        """The regression this group exists for: the session IS there, and a
        resolver that only scans $HOME says it does not exist."""
        root = os.path.realpath(str(self.home / "proj"))
        alt = self._alt()
        self.write_codex_at(alt, "01a00000-0000-7000-8000-0000000000c2", root)
        sid, _, miss = self.resolve(root, "codex")  # hermetic: no override
        self.assertEqual((sid, miss), ("", agent_sessions.MISS_NO_STORE_DIR))

    def test_codex_default_still_works_with_an_override_set(self):
        """An override must ADD a root, never replace the default."""
        root = os.path.realpath(str(self.home / "proj"))
        self.write_codex("01a00000-0000-7000-8000-0000000000c3", root)
        alt = self._alt()  # exists but holds nothing
        sid, _, miss = self.resolve(root, "codex", env={"CODEX_HOME": str(alt)})
        self.assertEqual((sid, miss),
                         ("01a00000-0000-7000-8000-0000000000c3", ""))

    # --- claude (override NOT established -> both roots searched) --------

    def test_claude_config_dir_override_is_found(self):
        root = os.path.realpath(str(self.home / "proj"))
        alt = self._alt()
        self.write_claude_at(alt, "sid-alt", root)
        sid, _, miss = self.resolve(root, "claudecode",
                                    env={"CLAUDE_CONFIG_DIR": str(alt)})
        self.assertEqual((sid, miss), ("sid-alt", ""))

    def test_claude_default_still_works_with_an_override_set(self):
        """The observed reality: claude writes to ~/.claude/projects even when
        CLAUDE_CONFIG_DIR points elsewhere. Searching both is what makes the
        resolver correct without having to settle that question."""
        root = os.path.realpath(str(self.home / "proj"))
        self.write_claude(agent_sessions.claude_project_dirname(root),
                          "sid-default", root)
        alt = self._alt()
        (alt / "projects").mkdir(parents=True, exist_ok=True)
        sid, _, miss = self.resolve(root, "claudecode",
                                    env={"CLAUDE_CONFIG_DIR": str(alt)})
        self.assertEqual((sid, miss), ("sid-default", ""))

    # --- degenerate override values --------------------------------------

    def test_blank_and_whitespace_overrides_are_ignored(self):
        root = os.path.realpath(str(self.home / "proj"))
        self.write_codex("01a00000-0000-7000-8000-0000000000c4", root)
        for value in ("", "   "):
            with self.subTest(value=repr(value)):
                sid, _, miss = self.resolve(root, "codex",
                                            env={"CODEX_HOME": value})
                self.assertEqual(miss, "")
                self.assertEqual(sid, "01a00000-0000-7000-8000-0000000000c4")

    def test_an_override_equal_to_the_default_is_not_scanned_twice(self):
        root = os.path.realpath(str(self.home / "proj"))
        self.write_codex("01a00000-0000-7000-8000-0000000000c5", root)
        sid, _, miss = self.resolve(root, "codex",
                                    env={"CODEX_HOME": str(self.home / ".codex")})
        self.assertEqual((sid, miss),
                         ("01a00000-0000-7000-8000-0000000000c5", ""))

    def test_a_nonexistent_override_does_not_mask_the_default(self):
        root = os.path.realpath(str(self.home / "proj"))
        self.write_codex("01a00000-0000-7000-8000-0000000000c6", root)
        sid, _, miss = self.resolve(root, "codex",
                                    env={"CODEX_HOME": str(self.home / "nope")})
        self.assertEqual((sid, miss),
                         ("01a00000-0000-7000-8000-0000000000c6", ""))


class LayoutFixtureTests(unittest.TestCase):
    """The committed fixture is the ground truth the resolver is written
    against; it must stay valid, redacted, and in agreement with the code."""

    def setUp(self) -> None:
        self.assertTrue(LAYOUT_FIXTURE.is_file(), f"missing {LAYOUT_FIXTURE}")
        self.data = json.loads(LAYOUT_FIXTURE.read_text())

    def test_records_both_corrected_assumptions(self):
        corrected = self.data["_plan_assumptions_corrected"]
        self.assertIn("claude_escape_rule", corrected)
        self.assertIn("codex_cwd_location", corrected)

    def test_agrees_with_the_implemented_encode_rule(self):
        rule = self.data["claudecode"]["project_dir"]["encode_rule"]
        self.assertIn("'/'", rule)
        self.assertIn("'_'", rule)
        ex = self.data["claudecode"]["project_dir"]["example"]
        self.assertEqual(agent_sessions.claude_project_dirname(ex["cwd"]), ex["dir"])

    def test_records_the_store_root_overrides(self):
        """The resolver honours both; the fixture must name both, so a reader
        cannot conclude the default root is the only one that matters."""
        self.assertIn("CLAUDE_CONFIG_DIR",
                      self.data["claudecode"]["store_root_env_override"])
        self.assertIn("CODEX_HOME",
                      self.data["codex"]["store_root_env_override"])

    def test_redaction(self):
        raw = LAYOUT_FIXTURE.read_text()
        for bad in ("/Users/", "/home/", os.path.expanduser("~")):
            self.assertNotIn(bad, raw, f"fixture leaks {bad!r}")


if __name__ == "__main__":
    unittest.main()
