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

    def write_codex_named(self, name: str, session_id: str, cwd: str, *,
                          date="2026/09/07", mtime: float | None = None) -> Path:
        """A rollout whose FILENAME id need not match its payload session id.

        Real stores hold both shapes: a subagent thread carries its parent's
        `session_id`, and 159 of 1168 measured rollouts carry no `session_id` at
        all (the filename is then the only source).
        """
        d = self.home / ".codex" / "sessions" / date
        d.mkdir(parents=True, exist_ok=True)
        path = d / name
        payload = {"cwd": cwd, "originator": "codex-tui"}
        if session_id:
            payload["session_id"] = session_id
        path.write_text(json.dumps(
            {"type": "session_meta", "payload": payload}) + "\n")
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def write_not_a_rollout(self, name: str) -> Path:
        """A rollout-SHAPED filename whose first line is not a `session_meta`.

        The pid resolver reads whatever a process holds open, so a shaped name
        is not by itself evidence that the file is a codex session.
        """
        d = self.home / ".codex" / "sessions" / "2026/09/07"
        d.mkdir(parents=True, exist_ok=True)
        path = d / name
        path.write_text(json.dumps({"type": "turn", "payload": {}}) + "\n")
        return path

    def write_proc(self, pid: int, *, argv=("/usr/bin/codex", "-m", "gpt-5.6-terra"),
                   fds=()) -> Path:
        """A fake `/proc/<pid>`: a cmdline plus one symlink per open file."""
        d = self.home / "proc" / str(pid)
        (d / "fd").mkdir(parents=True, exist_ok=True)
        (d / "cmdline").write_bytes(
            b"\0".join(a.encode() for a in argv) + b"\0")
        for index, target in enumerate(fds):
            link = d / "fd" / str(index)
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(str(target))
        return d

    def resolve_pid(self, pid):
        return agent_sessions.codex_session_for_pid(
            pid, proc_root=str(self.home / "proc"))

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

    def test_two_sessions_under_one_root_are_ambiguous(self):
        """REGRESSION (t1820): this used to return the NEWEST match.

        Two claude agents in one repo write to the same project directory, so
        the newest cwd-match is routinely another agent's conversation. Unlike
        codex there is no live-process correlation (a claude process holds no
        transcript fd), so refusing is the only honest answer.
        """
        root = os.path.realpath(str(self.home / "proj"))
        d = agent_sessions.claude_project_dirname(root)
        self.write_claude(d, "old", root, mtime=1_000_000)
        self.write_claude(d, "new", root, mtime=2_000_000)
        sid, path, miss = self.resolve(root, "claudecode")
        self.assertEqual((sid, path, miss), ("", "", agent_sessions.MISS_AMBIGUOUS))

    def test_other_projects_are_not_matched(self):
        root = os.path.realpath(str(self.home / "mine"))
        other = os.path.realpath(str(self.home / "theirs"))
        self.write_claude(agent_sessions.claude_project_dirname(other), "sid-x", other)
        sid, _, miss = self.resolve(root, "claudecode")
        self.assertEqual((sid, miss), ("", agent_sessions.MISS_NO_PROJECT_DIR))

    def test_equal_mtimes_are_ambiguous_not_a_tie_break(self):
        """Equal mtimes used to be settled by name; now nothing is picked."""
        root = os.path.realpath(str(self.home / "proj"))
        d = agent_sessions.claude_project_dirname(root)
        self.write_claude(d, "aaa", root, mtime=5_000_000)
        self.write_claude(d, "zzz", root, mtime=5_000_000)
        answers = {self.resolve(root, "claudecode") for _ in range(5)}
        self.assertEqual(answers, {("", "", agent_sessions.MISS_AMBIGUOUS)})

    def test_another_projects_session_does_not_make_it_ambiguous(self):
        """The refusal counts sessions OF THIS ROOT, not files in the dir."""
        root = os.path.realpath(str(self.home / "proj"))
        other = os.path.realpath(str(self.home / "other"))
        d = agent_sessions.claude_project_dirname(root)
        self.write_claude(d, "mine", root, mtime=1_000_000)
        self.write_claude(d, "theirs", other, mtime=2_000_000)
        sid, _, miss = self.resolve(root, "claudecode")
        self.assertEqual((sid, miss), ("mine", ""))

    def test_a_session_in_a_scanned_only_dir_is_not_hidden_by_the_computed_dir(self):
        """Uniqueness is decided over EVERY directory, not the first that matches.

        Stopping at the computed directory would call its one session unique
        while a different session for the same root sits in a directory whose
        name the encode rule did not predict (a changed or older layout).
        """
        root = os.path.realpath(str(self.home / "proj"))
        self.write_claude(agent_sessions.claude_project_dirname(root),
                          "computed", root, mtime=2_000_000)
        self.write_claude("an-older-encoding", "scanned", root, mtime=1_000_000)
        sid, path, miss = self.resolve(root, "claudecode")
        self.assertEqual((sid, path, miss), ("", "", agent_sessions.MISS_AMBIGUOUS))

    def test_one_session_in_two_stores_is_not_ambiguous(self):
        """The same session id under the override and the default store is one
        candidate; its newest file answers."""
        root = os.path.realpath(str(self.home / "proj"))
        d = agent_sessions.claude_project_dirname(root)
        self.write_claude(d, "sid-both", root, mtime=1_000_000)
        override = self.home / "cfg"
        dest = override / "projects" / d
        dest.mkdir(parents=True)
        newer = dest / "sid-both.jsonl"
        newer.write_text((self.home / ".claude" / "projects" / d
                          / "sid-both.jsonl").read_text())
        os.utime(newer, (2_000_000, 2_000_000))
        sid, path, miss = self.resolve(
            root, "claudecode", env={"CLAUDE_CONFIG_DIR": str(override)})
        self.assertEqual((sid, path, miss), ("sid-both", str(newer), ""))

    def test_a_directory_reached_twice_is_still_one_session(self):
        """A symlinked project directory must not be read as a second session.

        (Directory dedup only saves the re-read; the stem grouping is what
        keeps this unambiguous, so this pins the outcome, not the dedup.)"""
        root = os.path.realpath(str(self.home / "proj"))
        d = agent_sessions.claude_project_dirname(root)
        real = self.write_claude(d, "sid-once", root)
        store = self.home / ".claude" / "projects"
        (store / "alias-of-the-same-dir").symlink_to(store / d)
        sid, path, miss = self.resolve(root, "claudecode")
        self.assertEqual((sid, miss), ("sid-once", ""))
        self.assertEqual(os.path.realpath(path), os.path.realpath(str(real)))


class CodexLayoutTests(_TranscriptTestCase):
    def test_codex_reads_payload_not_top_level(self):
        """REGRESSION: the plan read a top-level 'cwd' that never exists."""
        root = os.path.realpath(str(self.home / "proj"))
        self.write_codex("01a07b46-2849-7612-bc01-ec1403808969", root)
        sid, path, miss = self.resolve(root, "codex")
        self.assertEqual(miss, "")
        self.assertEqual(sid, "01a07b46-2849-7612-bc01-ec1403808969")
        self.assertIn("rollout-", path)

    def test_two_sessions_under_one_root_are_ambiguous(self):
        """REGRESSION (t1804): this used to return the NEWEST match.

        Nothing here ties a rollout to a particular agent, so with two codex
        agents in one repo the newest match is routinely a *different* agent's
        conversation -- and a restore would replay it into the frozen pane.
        Refusing is the only honest answer; correlating needs the live process
        (`codex_session_for_pid`).
        """
        root = os.path.realpath(str(self.home / "proj"))
        self.write_codex("01a00000-0000-7000-8000-000000000001", root,
                         date="2026/09/06", mtime=1_000_000)
        self.write_codex("01a00000-0000-7000-8000-000000000002", root,
                         date="2026/09/07", mtime=2_000_000)
        sid, path, miss = self.resolve(root, "codex")
        self.assertEqual((sid, path), ("", ""))
        self.assertEqual(miss, agent_sessions.MISS_AMBIGUOUS)

    def test_a_single_session_root_still_resolves(self):
        """The refusal is about ambiguity, not about codex."""
        root = os.path.realpath(str(self.home / "proj"))
        self.write_codex("01a00000-0000-7000-8000-000000000009", root,
                         date="2026/09/06", mtime=1_000_000)
        sid, _, miss = self.resolve(root, "codex")
        self.assertEqual((sid, miss),
                         ("01a00000-0000-7000-8000-000000000009", ""))

    def test_one_session_in_several_files_is_not_ambiguous(self):
        """Grouping is by SESSION, not by file: a resumed session can appear in
        more than one rollout, and that is still one conversation."""
        root = os.path.realpath(str(self.home / "proj"))
        sid_one = "01a00000-0000-7000-8000-00000000000b"
        self.write_codex(sid_one, root, date="2026/09/06", mtime=1_000_000)
        newer = self.write_codex_named(
            "rollout-2026-09-07T12-00-00-01a00000-0000-7000-8000-0000000000ff.jsonl",
            sid_one, root, date="2026/09/07", mtime=2_000_000)
        sid, path, miss = self.resolve(root, "codex")
        self.assertEqual((sid, miss), (sid_one, ""))
        self.assertEqual(path, str(newer), "newest file OF THAT SESSION")

    def test_other_projects_are_not_matched(self):
        root = os.path.realpath(str(self.home / "mine"))
        other = os.path.realpath(str(self.home / "theirs"))
        self.write_codex("01a00000-0000-7000-8000-00000000000a", other)
        sid, _, miss = self.resolve(root, "codex")
        self.assertEqual((sid, miss), ("", agent_sessions.MISS_NO_MATCH))


class CodexPidCorrelationTests(_TranscriptTestCase):
    """`codex_session_for_pid` — the correlated resolver (t1804).

    A codex process holds its rollout OPEN (measured, codex 0.154), so the open
    fd ties one session to one process. That is the identity a cwd scan cannot
    supply, and it is why the freeze engine resolves while the agent is alive.
    """

    def test_each_agent_resolves_its_own_session_not_the_newest(self):
        """THE t1797 REGRESSION, in one fixture.

        Two codex agents in one repo. The uncorrelated scan can only refuse;
        each pid resolves to the rollout IT holds — including the agent whose
        session is the OLDER one, which is exactly the case that used to hand
        back a stranger's conversation.
        """
        root = os.path.realpath(str(self.home / "proj"))
        mine = "01a00000-0000-7000-8000-00000000aaaa"
        theirs = "01a00000-0000-7000-8000-00000000bbbb"
        mine_path = self.write_codex(mine, root, date="2026/09/06",
                                     mtime=1_000_000)
        theirs_path = self.write_codex(theirs, root, date="2026/09/07",
                                       mtime=2_000_000)
        self.write_proc(101, fds=[mine_path])
        self.write_proc(102, fds=[theirs_path])

        self.assertEqual(self.resolve_pid(101), (mine, str(mine_path), ""))
        self.assertEqual(self.resolve_pid(102), (theirs, str(theirs_path), ""))
        self.assertEqual(self.resolve(root, "codex")[2],
                         agent_sessions.MISS_AMBIGUOUS,
                         "uncorrelated, the resolver must refuse to choose")

    def test_a_subagent_rollout_folds_into_its_parent_session(self):
        """A subagent thread carries its PARENT's session id, so a process
        holding both is running ONE session, not two rival ones."""
        root = os.path.realpath(str(self.home / "proj"))
        parent = "01a00000-0000-7000-8000-00000000cccc"
        main_path = self.write_codex(parent, root)
        sub_path = self.write_codex_named(
            "rollout-2026-09-07T13-00-00-01a00000-0000-7000-8000-00000000dddd.jsonl",
            parent, root)
        self.write_proc(103, fds=[main_path, sub_path])
        sid, path, miss = self.resolve_pid(103)
        self.assertEqual((sid, miss), (parent, ""))
        self.assertEqual(path, str(main_path),
                         "the path whose filename id IS the session id")

    def test_two_distinct_sessions_held_at_once_are_ambiguous(self):
        root = os.path.realpath(str(self.home / "proj"))
        one = self.write_codex("01a00000-0000-7000-8000-00000000eeee", root)
        two = self.write_codex("01a00000-0000-7000-8000-00000000ffff", root,
                               date="2026/09/08")
        self.write_proc(104, fds=[one, two])
        sid, path, miss = self.resolve_pid(104)
        self.assertEqual((sid, path), ("", ""))
        self.assertEqual(miss, agent_sessions.MISS_AMBIGUOUS)

    def test_a_non_codex_process_holding_a_rollout_is_refused(self):
        """THE WRONG-AGENT GUARD. A recycled pane, or any program holding a
        rollout-shaped file, must never write its session into a codex record.
        """
        root = os.path.realpath(str(self.home / "proj"))
        rollout = self.write_codex("01a00000-0000-7000-8000-000000001111", root)
        self.write_proc(105, argv=("/usr/bin/python3", "-m", "http.server"),
                        fds=[rollout])
        self.assertEqual(self.resolve_pid(105),
                         ("", "", agent_sessions.MISS_NOT_CODEX))

    def test_a_codex_process_holding_no_rollout_is_a_plain_miss(self):
        """A codex that has taken no turn yet holds nothing — it opens its
        rollout at the FIRST turn (measured). Distinct from "not codex"."""
        self.write_proc(106, fds=[])
        self.assertEqual(self.resolve_pid(106),
                         ("", "", agent_sessions.MISS_NO_MATCH))

    def test_files_that_are_not_rollouts_are_ignored(self):
        root = os.path.realpath(str(self.home / "proj"))
        shaped = self.write_not_a_rollout(
            "rollout-2026-09-07T14-00-00-01a00000-0000-7000-8000-000000002222.jsonl")
        ordinary = self.home / "notes.txt"
        ordinary.write_text("hello\n")
        self.write_proc(107, fds=[shaped, ordinary])
        self.assertEqual(self.resolve_pid(107)[2], agent_sessions.MISS_NO_MATCH)
        # ...and the same process ALSO holding a real one still resolves.
        real = self.write_codex("01a00000-0000-7000-8000-000000003333", root)
        self.write_proc(108, fds=[shaped, ordinary, real])
        self.assertEqual(self.resolve_pid(108)[0],
                         "01a00000-0000-7000-8000-000000003333")

    def test_a_rollout_without_a_payload_session_id_falls_back_to_the_filename(self):
        root = os.path.realpath(str(self.home / "proj"))
        path = self.write_codex_named(
            "rollout-2026-09-07T15-00-00-01a00000-0000-7000-8000-000000004444.jsonl",
            "", root)
        self.write_proc(109, fds=[path])
        self.assertEqual(self.resolve_pid(109),
                         ("01a00000-0000-7000-8000-000000004444", str(path), ""))

    def test_an_uninspectable_process_is_not_evidence(self):
        """`MISS_NO_PROCESS` vs `MISS_NOT_CODEX` is load-bearing: the freeze
        engine CLEARS a stale session id on the latter and must not on the
        former (no `/proc` at all — every macOS freeze)."""
        self.assertEqual(self.resolve_pid(4242)[2],
                         agent_sessions.MISS_NO_PROCESS)
        self.assertEqual(self.resolve_pid(0)[2], agent_sessions.MISS_NO_PROCESS)
        self.assertEqual(self.resolve_pid(-1)[2], agent_sessions.MISS_NO_PROCESS)
        # A pid whose fd dir exists but whose cmdline does not: "could not
        # look", never "not codex".
        (self.home / "proc" / "110" / "fd").mkdir(parents=True)
        self.assertEqual(self.resolve_pid(110)[2],
                         agent_sessions.MISS_NO_PROCESS)


class CodexProcessModelTests(_TranscriptTestCase):
    """`codex_process_model` — is this process codex, and which model?"""

    def model(self, pid):
        return agent_sessions.codex_process_model(
            pid, proc_root=str(self.home / "proc"))

    def test_reads_the_model_flag_in_each_accepted_spelling(self):
        for index, argv in enumerate((
            ("/usr/bin/codex", "-m", "gpt-5.6-terra"),
            ("/usr/bin/codex", "--model", "gpt-5.6-terra"),
            ("/usr/bin/codex", "--model=gpt-5.6-terra"),
            # A resumed agent: the flag is NOT adjacent to the binary.
            ("/usr/bin/codex", "resume", "01a0-sid", "-c", "tui.animations=false",
             "-m", "gpt-5.6-terra"),
        )):
            with self.subTest(argv=argv):
                self.write_proc(200 + index, argv=argv)
                self.assertEqual(self.model(200 + index),
                                 (True, "gpt-5.6-terra"))

    def test_a_codex_launched_without_a_model_is_still_codex(self):
        self.write_proc(210, argv=("/usr/bin/codex",))
        self.assertEqual(self.model(210), (True, ""))

    def test_a_non_codex_process_names_no_model(self):
        self.write_proc(211, argv=("/usr/bin/claude", "-m", "opus"))
        self.assertEqual(self.model(211), (False, ""))

    def test_an_unreadable_process_is_not_codex(self):
        self.assertEqual(self.model(9999), (False, ""))


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
            agent_sessions.MISS_AMBIGUOUS,
            agent_sessions.MISS_NO_PROCESS,
            agent_sessions.MISS_NOT_CODEX,
        }
        self.assertEqual(len(reasons), 7)
        self.assertNotIn("", reasons)

    def test_could_not_look_is_distinct_from_looked_and_found_nothing(self):
        """The t1804 pair the freeze engine BRANCHES on: `MISS_NO_PROCESS`
        (absence of evidence) must never read as `MISS_NOT_CODEX` /
        `MISS_NO_MATCH` (positive evidence), because only the latter may clear a
        recorded session id."""
        self.assertNotEqual(agent_sessions.MISS_NO_PROCESS,
                            agent_sessions.MISS_NOT_CODEX)
        self.assertNotEqual(agent_sessions.MISS_NO_PROCESS,
                            agent_sessions.MISS_NO_MATCH)


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
