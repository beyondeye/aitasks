"""Transcript-store fallback resolver tests (t1705_3).

`newest_transcript_for` is what recovers a codeagent session id when the
SessionStart hook never fired. For interactive codex that is a real path, not a
rare one. Codex 0.153.4 fired SessionStart under `codex exec` only, and 0.163.0
fires it in the TUI only at a session's first turn.

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
                   fds=(), children=None, job=None, ppid=1) -> Path:
        """A fake `/proc/<pid>`: a cmdline plus one symlink per open file.

        ``argv=None`` writes no cmdline (unreadable). ``children`` writes
        ``task/<pid>/children``; None writes no ``task/`` dir. ``job`` is
        ``(pgrp, tty_nr, tpgid)`` for a ``stat`` line; None writes no stat.
        """
        d = self.home / "proc" / str(pid)
        (d / "fd").mkdir(parents=True, exist_ok=True)
        if argv is not None:
            (d / "cmdline").write_bytes(
                b"\0".join(a.encode() for a in argv) + b"\0")
        elif (d / "cmdline").exists():
            (d / "cmdline").unlink()
        for index, target in enumerate(fds):
            link = d / "fd" / str(index)
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(str(target))
        if children is not None:
            task = d / "task" / str(pid)
            task.mkdir(parents=True, exist_ok=True)
            (task / "children").write_text(
                "".join(f"{child} " for child in children))
        if job is not None:
            self.write_job(pid, job, ppid=ppid)
        return d

    def write_job(self, pid: int, job, *, ppid=1) -> None:
        """``/proc/<pid>/stat`` with ``job = (pgrp, tty_nr, tpgid)``.

        `comm` carries a space and a `)` on purpose: the reader must count the
        fields from after the LAST `)`.
        """
        pgrp, tty_nr, tpgid = job
        (self.home / "proc" / str(pid) / "stat").write_text(
            f"{pid} (odd ) comm) S {ppid} {pgrp} {ppid} {tty_nr} {tpgid} "
            "4194304 0 0 0 0 0 0 0 0 20 0 1 0 100 0 0\n")

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


class _ShellPaneBase(_TranscriptTestCase):
    """`codex_observe_pid` through a pane SHELL (t2077).

    A codex typed at a shell prompt is the shell's direct child, so the pane
    pid is the shell (measured on codex 0.163.0: `-bash` -> codex, codex leads
    its own job, the terminal's tpgid is codex's pgrp, and a Ctrl-Z'd codex
    keeps its rollout open while tpgid flips back to the shell). Exactly one
    level, only through a known shell, and only the FOREGROUND job counts.
    """

    SHELL = 500
    TTY = 34860
    A = "01a00000-0000-7000-8000-00000000a001"
    B = "01a00000-0000-7000-8000-00000000b002"

    def setUp(self):
        super().setUp()
        self.root = os.path.realpath(str(self.home / "proj"))

    # --- fixture builders ----------------------------------------------------

    def shell(self, children, *, tpgid, argv=("-bash",), job=None):
        self.write_proc(self.SHELL, argv=argv, children=children,
                        job=job or (self.SHELL, self.TTY, tpgid))

    def codex(self, pid, session_id, *, tpgid, model="gpt-5.6-terra",
              pgrp=None, tty=None):
        rollout = self.write_codex(session_id, self.root)
        self.write_proc(pid, argv=("/usr/bin/codex", "-m", model),
                        fds=[rollout], ppid=self.SHELL,
                        job=(pgrp or pid, tty or self.TTY, tpgid))
        return rollout

    def other(self, pid, argv, *, tpgid, pgrp=None):
        self.write_proc(pid, argv=argv, ppid=self.SHELL,
                        job=(pgrp or pid, self.TTY, tpgid))

    def suspend_all(self, *pids):
        """Ctrl-Z of the foreground job: tpgid flips back to the shell."""
        for pid in (self.SHELL, *pids):
            stat = (self.home / "proc" / str(pid) / "stat").read_text()
            fields = stat.rpartition(")")[2].split()
            self.write_job(pid, (int(fields[2]), self.TTY, self.SHELL),
                           ppid=int(fields[1]))

    def observe(self, pid=None):
        return agent_sessions.codex_observe_pid(
            self.SHELL if pid is None else pid,
            proc_root=str(self.home / "proc"))

    def foreground_codex_pane(self):
        """The measured shape: a foreground codex at depth 1, holding A."""
        rollout = self.codex(501, self.A, tpgid=501)
        self.shell([501], tpgid=501)
        return rollout

    def _wrap(self, name, before=None, after=None, *, when=lambda *a: True):
        """Patch ``agent_sessions.<name>`` with a one-shot mutating wrapper."""
        target = agent_sessions.os if name == "readlink" else agent_sessions
        real = getattr(target, name)
        fired = []

        def wrapper(*args, **kwargs):
            once = not fired and when(*args)
            if once:
                fired.append(True)
                if before:
                    before()
            result = real(*args, **kwargs)
            if once and after:
                after()
            return result

        setattr(target, name, wrapper)
        self.addCleanup(setattr, target, name, real)
        return fired


class CodexShellPaneTests(_ShellPaneBase):
    """The shell-pane cases; fixture builders live on `_ShellPaneBase`."""

    # --- the measured case ---------------------------------------------------

    def test_a_foreground_codex_resolves_through_its_shell(self):
        """THE RED PROOF: before t2077 the shell pid answered `not_codex`."""
        rollout = self.foreground_codex_pane()
        self.assertEqual(self.observe(),
                         (self.A, str(rollout), "gpt-5.6-terra", ""))
        self.assertEqual(self.resolve_pid(self.SHELL),
                         (self.A, str(rollout), ""),
                         "the 3-tuple wrapper sees the same descent")

    def test_every_listed_shell_spelling_is_accepted(self):
        for argv in (("bash",), ("-zsh",), ("/usr/bin/fish", "-l"), ("sh",)):
            with self.subTest(argv=argv):
                self.codex(501, self.A, tpgid=501)
                self.shell([501], tpgid=501, argv=argv)
                self.assertEqual(self.observe()[0], self.A)

    def test_a_non_codex_job_mate_does_not_block_resolution(self):
        """`codex | tee` -- one foreground job, one codex in it."""
        self.codex(501, self.A, tpgid=501)
        self.other(502, ("tee", "log"), tpgid=501, pgrp=501)
        self.shell([501, 502], tpgid=501)
        self.assertEqual(self.observe()[0], self.A)

    def test_a_background_codex_is_not_a_candidate(self):
        self.codex(501, self.A, tpgid=501)
        self.codex(502, self.B, tpgid=501, model="gpt-5.4")
        self.shell([501, 502], tpgid=501)
        sid, _path, cli_id, miss = self.observe()
        self.assertEqual((sid, cli_id, miss), (self.A, "gpt-5.6-terra", ""),
                         "the foreground one's session AND model")

    # --- not the pane's agent -> today's answer, `not_codex` -----------------

    def test_a_suspended_codex_under_a_foreground_claude_is_not_the_agent(self):
        """THE OVERWRITE GUARD. A Ctrl-Z'd codex still holds its rollout, and a
        claude now runs in the foreground. A child-only rule returns codex's
        session here, and the freeze would file it over claude's record."""
        self.codex(501, self.A, tpgid=503)
        self.other(503, ("claude",), tpgid=503)
        self.shell([501, 503], tpgid=503)
        self.assertEqual(self.observe(),
                         ("", "", "", agent_sessions.MISS_NOT_CODEX))

    def test_a_suspended_codex_at_a_shell_prompt_is_not_the_agent(self):
        self.codex(501, self.A, tpgid=self.SHELL)
        self.shell([501], tpgid=self.SHELL)
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NOT_CODEX)

    def test_two_foreground_codex_children_are_not_one_agent(self):
        self.codex(501, self.A, tpgid=501)
        self.codex(502, self.B, tpgid=501, pgrp=501)
        self.shell([501, 502], tpgid=501)
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NOT_CODEX)

    def test_a_shell_with_no_children_is_not_codex(self):
        self.shell([], tpgid=self.SHELL)
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NOT_CODEX)

    def test_a_codex_child_of_another_agent_never_counts(self):
        """The claude Bash-tool exclusion: only a SHELL is descended."""
        rollout = self.write_codex(self.A, self.root)
        self.write_proc(501, argv=("/usr/bin/codex",), fds=[rollout],
                        ppid=self.SHELL, job=(501, self.TTY, 501))
        self.write_proc(self.SHELL, argv=("claude", "--resume", "x"),
                        children=[501], job=(self.SHELL, self.TTY, 501))
        self.assertEqual(self.observe(),
                         ("", "", "", agent_sessions.MISS_NOT_CODEX))

    def test_a_grandchild_codex_never_counts(self):
        """shell -> claude -> codex: depth 1 only."""
        rollout = self.write_codex(self.A, self.root)
        self.write_proc(502, argv=("/usr/bin/codex",), fds=[rollout], ppid=501,
                        job=(501, self.TTY, 501))
        self.write_proc(501, argv=("claude",), children=[502], ppid=self.SHELL,
                        job=(501, self.TTY, 501))
        self.shell([501], tpgid=501)
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NOT_CODEX)

    # --- could not look -> `no_process`, never a disproof --------------------

    def test_an_unreadable_children_list_is_not_evidence(self):
        self.codex(501, self.A, tpgid=501)
        self.write_proc(self.SHELL, argv=("-bash",), children=None,
                        job=(self.SHELL, self.TTY, 501))
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)

    def test_an_unreadable_child_cmdline_is_not_absence(self):
        self.write_proc(501, argv=None, job=(501, self.TTY, 501))
        self.shell([501], tpgid=501)
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS,
                         "an unread child could be the codex: not `not_codex`")

    def test_an_unreadable_child_cmdline_is_not_uniqueness(self):
        self.codex(501, self.A, tpgid=501)
        self.write_proc(502, argv=None, job=(501, self.TTY, 501))
        self.shell([501, 502], tpgid=501)
        self.assertEqual(self.observe(),
                         ("", "", "", agent_sessions.MISS_NO_PROCESS),
                         "uniqueness unproven: never the codex child's session")
        # Control: the same layout with that child readable resolves, so the
        # unreadable cmdline is what flipped it.
        self.other(502, ("sleep", "300"), tpgid=501, pgrp=501)
        self.assertEqual(self.observe()[0], self.A)

    def test_an_unreadable_child_stat_is_not_evidence(self):
        self.codex(501, self.A, tpgid=501)
        self.write_proc(502, argv=("sleep", "1"))
        self.shell([501, 502], tpgid=501)
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)

    def test_conflicting_foreground_evidence_is_not_evidence(self):
        cases = {
            "the child reports another tpgid":
                dict(child=dict(tpgid=777), shell_tpgid=501),
            "the child is on another terminal":
                dict(child=dict(tpgid=501, tty=999), shell_tpgid=501),
            "no job control: the child shares the shell's group":
                dict(child=dict(tpgid=self.SHELL, pgrp=self.SHELL),
                     shell_tpgid=self.SHELL),
            "the shell has no controlling terminal":
                dict(child=dict(tpgid=-1), shell_tpgid=-1),
        }
        for label, case in cases.items():
            with self.subTest(label):
                self.codex(501, self.A, **case["child"])
                self.shell([501], tpgid=case["shell_tpgid"])
                self.assertEqual(self.observe()[3],
                                 agent_sessions.MISS_NO_PROCESS)

    def test_an_unreadable_shell_stat_is_not_evidence(self):
        self.codex(501, self.A, tpgid=501)
        self.write_proc(self.SHELL, argv=("-bash",), children=[501])
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)

    def test_an_unreadable_child_fd_dir_is_not_evidence(self):
        import shutil
        self.foreground_codex_pane()
        fd_dir = self.home / "proc" / "501" / "fd"
        shutil.rmtree(fd_dir)
        fd_dir.write_text("")  # listing it raises, as for another user's pid
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)

    # --- a disproof needs a consistent, complete snapshot ----------------------

    def _move_codex_to_foreground(self):
        for pid in (self.SHELL, 501):
            self.write_job(pid, (pid, self.TTY, 501),
                           ppid=1 if pid == self.SHELL else self.SHELL)

    def test_a_job_moved_to_the_foreground_mid_look_is_not_a_disproof(self):
        """The shell is read while its own group is foreground; the codex is
        brought to the foreground (`fg`) before the child is read. Against the
        stale tpgid it is not a candidate -- and `not_codex` would clear its
        valid id."""
        self.codex(501, self.A, tpgid=self.SHELL)
        self.shell([501], tpgid=self.SHELL)
        fired = self._wrap("_proc_job", after=self._move_codex_to_foreground,
                           when=lambda pid, _root: int(pid) == self.SHELL)
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)
        self.assertTrue(fired)

    def test_control_a_stable_shell_prompt_is_still_not_codex(self):
        """Same fixture, nothing moves: the snapshot is consistent and the
        suspended codex is not the pane's agent."""
        self.codex(501, self.A, tpgid=self.SHELL)
        self.shell([501], tpgid=self.SHELL)
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NOT_CODEX)

    def test_an_unlisted_foreground_job_is_not_a_disproof(self):
        """`task/*/children` can skip a child under concurrent changes. A
        foreground group neither the shell's nor any listed child's means the
        look missed the very job that matters."""
        self.codex(501, self.A, tpgid=501)
        self.shell([], tpgid=501)
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)
        self.other(502, ("sleep", "300"), tpgid=501)  # a background job only
        self.shell([502], tpgid=501)
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)

    def test_a_child_listed_twice_is_one_child(self):
        """The children list is a union over threads; a duplicate must not
        make one codex look like two (`not_codex`)."""
        rollout = self.codex(501, self.A, tpgid=501)
        self.shell([501, 501], tpgid=501)
        self.assertEqual(self.observe(),
                         (self.A, str(rollout), "gpt-5.6-terra", ""))

    def test_a_child_reporting_another_foreground_is_not_a_disproof(self):
        self.other(502, ("sleep", "300"), tpgid=999)
        self.shell([502], tpgid=self.SHELL)
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)

    def _launcher(self):
        """A foreground `env` launcher that has not exec'd into codex yet."""
        self.write_proc(501, argv=("env", "X=1", "codex", "resume", self.A),
                        ppid=self.SHELL, job=(501, self.TTY, 501))
        self.shell([501], tpgid=501)

    def _exec_into_codex(self):
        """Same pid, group, tty and list place -- only argv and fds change."""
        rollout = self.write_codex(self.A, self.root)
        self.write_proc(501, argv=("/usr/bin/codex", "resume", self.A),
                        fds=[rollout])

    def test_a_launcher_that_execs_into_codex_mid_look_is_not_a_disproof(self):
        self._launcher()
        fired = self._wrap("_codex_cmdline_argv", after=self._exec_into_codex,
                           when=lambda pid, _root: int(pid) == 501)
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS,
                         "the disproof rested on an argv that is now codex")
        self.assertTrue(fired)

    def test_control_a_launcher_that_stays_a_launcher_is_not_codex(self):
        self._launcher()
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NOT_CODEX)

    def test_control_a_launcher_that_already_exec_d_resolves(self):
        self._launcher()
        self._exec_into_codex()
        self.assertEqual(self.observe()[0], self.A)

    def test_children_changing_during_the_look_is_not_a_disproof(self):
        self.other(502, ("sleep", "300"), tpgid=self.SHELL)
        self.shell([502], tpgid=self.SHELL)
        self.other(503, ("sleep", "5"), tpgid=self.SHELL)

        def relist():
            (self.home / "proc" / str(self.SHELL) / "task" / str(self.SHELL)
             / "children").write_text("502 503 ")

        self._wrap("_direct_children", after=relist)
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)

    # --- one observation, one process -----------------------------------------

    def _replace_child_with_b(self):
        import shutil
        shutil.rmtree(self.home / "proc" / "501")
        self.codex(502, self.B, tpgid=502, model="gpt-5.4")
        self.shell([502], tpgid=502)

    def _reuse_pid_501_for_b(self):
        import shutil
        shutil.rmtree(self.home / "proc" / "501")
        self.codex(501, self.B, tpgid=501, model="gpt-5.4")

    def test_a_child_replaced_after_selection_yields_no_process(self):
        """Red against a two-call implementation, which would pair A's
        session with B's model (or B's session with A's model)."""
        self.foreground_codex_pane()
        self._wrap("_codex_cmdline_argv", after=self._replace_child_with_b,
                   when=lambda pid, _root: int(pid) == 501)
        result = self.observe()
        self.assertEqual(result, ("", "", "", agent_sessions.MISS_NO_PROCESS))
        self.assertNotIn(self.B, result)
        self.assertNotIn("gpt-5.4", result)

    def test_a_reused_pid_fails_the_identity_recheck(self):
        self.foreground_codex_pane()
        self._wrap("_codex_cmdline_argv", after=self._reuse_pid_501_for_b,
                   when=lambda pid, _root: int(pid) == 501)
        result = self.observe()
        self.assertEqual(result, ("", "", "", agent_sessions.MISS_NO_PROCESS),
                         "B's fds were read under A's argv -- must not pair")

    def test_a_suspend_after_selection_yields_no_process(self):
        self.foreground_codex_pane()
        self._wrap("_codex_cmdline_argv", after=lambda: self.suspend_all(501),
                   when=lambda pid, _root: int(pid) == 501)
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)

    # --- mutation DURING the evidence loop (after `fd/` is listed) -----------
    #
    # Each is red against a design that validates before the loop: listing
    # `fd/` reads names only; targets and rollout headers come later.

    def test_a_suspend_during_rollout_inspection_yields_no_process(self):
        self.foreground_codex_pane()
        fired = self._wrap("_codex_rollout_identity",
                           after=lambda: self.suspend_all(501))
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)
        self.assertTrue(fired, "the mutation must actually have happened")

    def test_a_suspend_during_readlink_yields_no_process(self):
        self.foreground_codex_pane()
        fired = self._wrap("readlink", before=lambda: self.suspend_all(501))
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)
        self.assertTrue(fired)

    def test_a_child_gone_during_readlink_is_not_a_disproof(self):
        """Its links all fail, the candidate set is empty -- and that must not
        become `MISS_NO_MATCH`, which clears a stored id."""
        import shutil
        self.foreground_codex_pane()
        fired = self._wrap(
            "readlink",
            before=lambda: shutil.rmtree(self.home / "proc" / "501"))
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)
        self.assertTrue(fired)

    def test_a_depth0_codex_gone_during_readlink_is_not_a_disproof(self):
        """The same gap existed for a framework launch (pane pid IS codex)."""
        import shutil
        rollout = self.write_codex(self.A, self.root)
        self.write_proc(600, fds=[rollout])
        fired = self._wrap(
            "readlink", before=lambda: shutil.rmtree(self.home / "proc" / "600"))
        self.assertEqual(self.observe(600)[3], agent_sessions.MISS_NO_PROCESS)
        self.assertTrue(fired)

    def test_the_loop_wrappers_alone_change_nothing(self):
        """Control for the four tests above: delegate without mutating."""
        rollout = self.foreground_codex_pane()
        self._wrap("readlink")
        self._wrap("_codex_rollout_identity")
        self.assertEqual(self.observe(),
                         (self.A, str(rollout), "gpt-5.6-terra", ""))


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
            ("/usr/bin/codex", "resume", "01a0-sid", "-c", "tui.animations=true",
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


class ProcessAgentEvidenceTests(_TranscriptTestCase):
    """t1850: what a live process says about which agent and model it is."""

    def evidence(self, pid):
        return agent_sessions.process_model_evidence(
            pid, proc_root=str(self.home / "proc"))

    def environ(self, pid, name="AITASK_AGENT_STRING"):
        return agent_sessions.process_environ_value(
            pid, name, proc_root=str(self.home / "proc"))

    def test_argv0_names_the_kind_and_the_model_flag_the_model(self):
        for index, (argv, expected) in enumerate((
            (("/opt/claude/latest/claude", "--model", "claude-opus-5",
              "/aitask-pick 1"), ("claudecode", "claude-opus-5")),
            (("/usr/bin/codex", "resume", "sid", "-m", "gpt-5.4"),
             ("codex", "gpt-5.4")),
            (("opencode", "--model=openai/gpt-5"), ("opencode", "openai/gpt-5")),
            (("/opt/claude/claude",), ("claudecode", "")),
            (("/usr/bin/vim", "--model", "x"), ("", "")),
        )):
            with self.subTest(argv=argv):
                self.write_proc(300 + index, argv=argv)
                self.assertEqual(self.evidence(300 + index), expected)

    def test_an_unreadable_process_gives_no_evidence(self):
        self.assertEqual(self.evidence(9999), ("", ""))

    def test_environ_value_distinguishes_absent_from_unreadable(self):
        d = self.write_proc(320, argv=("/opt/claude/claude",))
        (d / "environ").write_bytes(
            b"PATH=/bin\0AITASK_AGENT_STRING=claudecode/opus5\0HOME=/h\0")
        self.assertEqual(self.environ(320), "claudecode/opus5")
        self.assertEqual(self.environ(320, "AITASK_MISSING"), "")
        self.assertIsNone(self.environ(9999))


# --- the macOS backend (t2048) -----------------------------------------------
#
# macOS has no /proc: argv comes from `sysctl(KERN_PROCARGS2)`, jobs and
# children from `ps`, open files from `lsof`. The fake below answers all three
# FROM THE SAME fake `/proc` fixture, so every fixture-driven class above can be
# re-run on the macOS backend unchanged -- the shell / foreground / identity
# logic is shared, and only the four readers differ.

LSOF_FIXTURE = (REPO_ROOT / "tests" / "data" / "session_hooks"
                / "lsof_escaped_names.json")

#: A real `KERN_PROCARGS2` buffer, captured on macOS 15 for
#: `perl -e 'sleep 20' 'explain -m gpt-5.4'` started under `env -i`.
REAL_PROCARGS2 = (b"\x04\x00\x00\x00/usr/bin/perl\x00\x00\x00/usr/bin/perl\x00"
                  b"-e\x00sleep 20\x00explain -m gpt-5.4\x00")


def lsof_render(path: str) -> str:
    """How lsof 4.91 prints a name under LC_ALL=C (pinned by the fixture test)."""
    named = {0x5C: "\\\\", 0x0A: "\\n", 0x09: "\\t", 0x0D: "\\r",
             0x08: "\\b", 0x0C: "\\f"}
    out = []
    for byte in os.fsencode(path):
        if byte in named:
            out.append(named[byte])
        elif byte < 0x20:
            out.append("^" + chr(byte + 0x40))
        elif byte >= 0x7F:
            out.append(f"\\x{byte:02x}")
        else:
            out.append(chr(byte))
    return "".join(out)


def procargs2_image(argv) -> bytes:
    """A `KERN_PROCARGS2` buffer: argc, exec path, padding, argv, environ."""
    raw = len(argv).to_bytes(4, sys.byteorder)
    raw += argv[0].encode() + b"\0\0\0"
    raw += b"".join(a.encode() + b"\0" for a in argv)
    return raw + b"HOME=/h\0"


class _PsBackend:
    """Mixin: run a fixture-driven test class on the macOS backend."""

    def setUp(self):
        super().setUp()
        self.probe_calls = []
        for name, value in (("_ps_probe", lambda _root: True),
                            ("_darwin_procargs", self._fake_procargs),
                            ("_run_probe", self._fake_probe)):
            real = getattr(agent_sessions, name)
            setattr(agent_sessions, name, value)
            self.addCleanup(setattr, agent_sessions, name, real)

    def _proc(self, pid) -> Path:
        return self.home / "proc" / str(int(pid))

    def _fake_procargs(self, pid):
        try:
            raw = (self._proc(pid) / "cmdline").read_bytes()
        except OSError:
            return None
        return procargs2_image([a.decode() for a in raw.split(b"\0") if a])

    def _stat(self, pid):
        try:
            text = (self._proc(pid) / "stat").read_text()
        except OSError:
            return None
        fields = text.rpartition(")")[2].split()
        return int(fields[1]), int(fields[2]), int(fields[4]), int(fields[5])

    def _fake_probe(self, cmd, env=None):
        self.probe_calls.append(cmd)
        if cmd[:2] == ["ps", "-p"]:
            stat = self._stat(cmd[2])
            if stat is None:
                return None
            _ppid, pgrp, tty_nr, tpgid = stat
            tty = f"ttys{tty_nr:03d}" if tty_nr else "??"
            return f"{pgrp:>5} {tpgid:>5} {tty}\n"
        if cmd[:2] == ["ps", "-A"]:
            # The fixture's children lists ARE the snapshot: a process no list
            # names is shown under init, so a fixture that leaves a child out
            # models a ps snapshot that missed it.
            rows: dict[int, int] = {}
            for d in sorted((self.home / "proc").iterdir()):
                for children in d.glob("task/*/children"):
                    for child in children.read_text().split():
                        rows.setdefault(int(child), int(d.name))
            for d in sorted((self.home / "proc").iterdir()):
                rows.setdefault(int(d.name), 1)
            return "".join(f"{pid:>5} {ppid:>5}\n" for pid, ppid in rows.items())
        if cmd[0] == "lsof":
            self.assertEqual((env or {}).get("LC_ALL"), "C")
            fd_dir = self._proc(cmd[-1]) / "fd"
            if not fd_dir.is_dir():
                return None
            lines = [f"p{int(cmd[-1])}", "fcwd", "n/", "ftxt", "n/usr/bin/codex"]
            for link in sorted(fd_dir.iterdir(), key=lambda p: int(p.name)):
                try:
                    target = os.readlink(link)
                except OSError:
                    continue
                lines += [f"f{link.name}", "n" + lsof_render(target)]
            return "\n".join(lines) + "\n"
        raise AssertionError(f"unexpected probe {cmd}")


_NO_PS_ANALOGUE = "fixture mechanism has no macOS analogue; see PsBackendTests"


class PsCodexPidCorrelationTests(_PsBackend, CodexPidCorrelationTests):
    pass


class PsCodexShellPaneTests(_PsBackend, CodexShellPaneTests):
    @unittest.skip("ps -A cannot be half-readable; " + _NO_PS_ANALOGUE)
    def test_an_unreadable_children_list_is_not_evidence(self):
        pass

    @unittest.skip("readlink is a /proc step; " + _NO_PS_ANALOGUE)
    def test_a_suspend_during_readlink_yields_no_process(self):
        pass

    @unittest.skip("readlink is a /proc step; " + _NO_PS_ANALOGUE)
    def test_a_child_gone_during_readlink_is_not_a_disproof(self):
        pass

    @unittest.skip("readlink is a /proc step; " + _NO_PS_ANALOGUE)
    def test_a_depth0_codex_gone_during_readlink_is_not_a_disproof(self):
        pass


class PsCodexProcessModelTests(_PsBackend, CodexProcessModelTests):
    pass


class PsProcessAgentEvidenceTests(_PsBackend, ProcessAgentEvidenceTests):
    pass


class PsBackendTests(_PsBackend, _ShellPaneBase):
    """What only the macOS backend can get wrong (t2048)."""

    # --- argv boundaries ---------------------------------------------------

    def test_ps_a_prompt_argument_never_invents_a_model(self):
        """`ps -o args=` would re-split this into `-m gpt-5.4`."""
        rollout = self.write_codex(self.A, self.root)
        self.write_proc(600, argv=("/usr/bin/codex", "explain -m gpt-5.4"),
                        fds=[rollout])
        self.assertEqual(self.observe(600), (self.A, str(rollout), "", ""))
        self.assertEqual(agent_sessions.codex_process_model(600), (True, ""))

    def test_ps_an_argv0_with_a_space_is_still_codex(self):
        rollout = self.write_codex(self.A, self.root)
        self.write_proc(600, argv=("/Users/me/my apps/codex", "-m", "gpt-5.4"),
                        fds=[rollout])
        self.assertEqual(self.observe(600), (self.A, str(rollout), "gpt-5.4", ""))

    def test_ps_parse_procargs2_on_a_real_buffer(self):
        self.assertEqual(agent_sessions._parse_procargs2(REAL_PROCARGS2),
                         ["/usr/bin/perl", "-e", "sleep 20", "explain -m gpt-5.4"])

    def test_ps_parse_procargs2_fails_closed(self):
        for raw in (None, b"", b"\x04\x00", REAL_PROCARGS2[:-1],
                    REAL_PROCARGS2[:30],
                    (9).to_bytes(4, sys.byteorder) + REAL_PROCARGS2[4:],
                    (0).to_bytes(4, sys.byteorder) + REAL_PROCARGS2[4:],
                    REAL_PROCARGS2[:4] + b"/usr/bin/perl"):
            with self.subTest(raw=raw):
                self.assertIsNone(agent_sessions._parse_procargs2(raw))

    def test_ps_unreadable_procargs_is_not_evidence(self):
        rollout = self.write_codex(self.A, self.root)
        self.write_proc(600, argv=None, fds=[rollout])
        self.assertEqual(self.observe(600)[3], agent_sessions.MISS_NO_PROCESS)

    # --- probe failures are "could not look" ---------------------------------

    def test_ps_no_lsof_answer_is_not_evidence(self):
        self.foreground_codex_pane()
        fake = agent_sessions._run_probe
        agent_sessions._run_probe = (
            lambda cmd, env=None: None if cmd[0] == "lsof" else fake(cmd, env))
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)

    def test_ps_no_ps_a_answer_on_the_shell_route_is_not_evidence(self):
        self.foreground_codex_pane()
        fake = agent_sessions._run_probe
        agent_sessions._run_probe = (
            lambda cmd, env=None: None if cmd[:2] == ["ps", "-A"] else fake(cmd, env))
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)

    def test_ps_a_pid_missing_from_ps_a_has_no_children_list(self):
        self.foreground_codex_pane()
        self.assertIsNone(agent_sessions._ps_children(4242))
        self.assertEqual(agent_sessions._ps_children(self.SHELL), [501])

    def test_ps_lsof_without_its_pid_line_is_no_answer(self):
        agent_sessions._run_probe = lambda cmd, env=None: "fcwd\nn/\n"
        self.assertIsNone(agent_sessions._lsof_open_files(600))

    def test_ps_lsof_pseudo_entries_are_not_descriptors(self):
        """A rollout named only as `cwd` / `txt` is not an open descriptor."""
        agent_sessions._run_probe = lambda cmd, env=None: (
            "p600\nfcwd\nn/a/rollout-x.jsonl\nftxt\nn/usr/bin/codex\n"
            "f7\nn/tmp/plain\n")
        self.assertEqual(agent_sessions._lsof_open_files(600),
                         [("/tmp/plain", "/tmp/plain")])

    def test_ps_a_suspend_during_the_lsof_read_yields_no_process(self):
        self.foreground_codex_pane()
        fired = self._wrap("_lsof_open_files",
                           after=lambda: self.suspend_all(501))
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)
        self.assertTrue(fired)

    def test_ps_a_child_gone_during_the_lsof_read_is_not_a_disproof(self):
        import shutil
        self.foreground_codex_pane()
        fired = self._wrap(
            "_lsof_open_files",
            after=lambda: shutil.rmtree(self.home / "proc" / "501"))
        self.assertEqual(self.observe()[3], agent_sessions.MISS_NO_PROCESS)
        self.assertTrue(fired)

    # --- lsof name escaping ------------------------------------------------

    def _escape_pairs(self):
        return json.loads(LSOF_FIXTURE.read_text())["pairs"]

    def test_ps_the_fake_renders_names_exactly_as_captured(self):
        """Anchors the fake to reality: otherwise it could emit raw names and
        hide every escaping bug."""
        for pair in self._escape_pairs():
            with self.subTest(name=pair["name"]):
                self.assertEqual(lsof_render(pair["name"]), pair["lsof"])

    def test_ps_captured_names_decode_back_or_are_uncertain(self):
        pairs = self._escape_pairs()
        self.assertTrue(any("\\" in p["lsof"] for p in pairs))
        for pair in pairs:
            with self.subTest(name=pair["name"]):
                decoded = agent_sessions._decode_lsof_name(pair["lsof"])
                if "^" in pair["lsof"]:
                    # `\x01` and a literal `^A` render identically.
                    self.assertIsNone(decoded)
                else:
                    self.assertEqual(decoded, pair["name"])

    def test_ps_malformed_escapes_are_uncertain(self):
        for raw in ("a\\", "a\\q", "a\\x4", "a\\xzz"):
            with self.subTest(raw=raw):
                self.assertIsNone(agent_sessions._decode_lsof_name(raw))

    def _codex_home_at(self, dirname):
        rollout = self.write_codex(self.A, self.root)
        moved = self.home / dirname / rollout.name
        moved.parent.mkdir(parents=True)
        rollout.rename(moved)
        self.write_proc(600, fds=[moved])
        return moved

    def test_ps_a_non_ascii_codex_home_resolves(self):
        rollout = self._codex_home_at("café")
        self.assertEqual(self.observe(600),
                         (self.A, str(rollout), "gpt-5.6-terra", ""))

    def test_ps_an_escaped_newline_in_the_path_resolves(self):
        rollout = self._codex_home_at("a\nb")
        self.assertEqual(self.observe(600)[0], self.A)

    def test_ps_an_ambiguous_caret_name_is_not_a_disproof(self):
        """Skipping it would leave no candidate -> `MISS_NO_MATCH`, which
        clears a stored id."""
        self._codex_home_at("c\x01x")
        self.assertEqual(self.observe(600)[3], agent_sessions.MISS_NO_PROCESS)

    def test_ps_a_rollout_gone_after_the_lsof_read_is_not_a_disproof(self):
        rollout = self._codex_home_at("plain")
        fired = self._wrap("_lsof_open_files", after=rollout.unlink)
        self.assertEqual(self.observe(600)[3], agent_sessions.MISS_NO_PROCESS)
        self.assertTrue(fired)

    def test_ps_lsof_runs_under_the_c_locale(self):
        rollout = self._codex_home_at("plain")
        self.observe(600)
        self.assertTrue(any(c[0] == "lsof" for c in self.probe_calls))


class PsProbeContractTests(unittest.TestCase):
    """Which root goes to `ps` / `lsof` (t2048). Linux must never get there."""

    def _with_platform(self, value):
        real = agent_sessions._PS_PROBE_PLATFORM
        agent_sessions._PS_PROBE_PLATFORM = value
        self.addCleanup(setattr, agent_sessions, "_PS_PROBE_PLATFORM", real)

    def test_only_the_real_proc_root_on_darwin(self):
        self._with_platform(True)
        self.assertTrue(agent_sessions._ps_probe("/proc"))
        self.assertFalse(agent_sessions._ps_probe("/tmp/fake/proc"))

    def test_never_off_darwin(self):
        self._with_platform(False)
        for root in ("/proc", "/tmp/fake/proc"):
            with self.subTest(root=root):
                self.assertFalse(agent_sessions._ps_probe(root))

    def test_the_platform_flag_reflects_this_host(self):
        self.assertEqual(agent_sessions._PS_PROBE_PLATFORM,
                         sys.platform == "darwin")

    def test_run_probe_reports_no_answer_not_an_empty_one(self):
        self.assertIsNone(agent_sessions._run_probe(
            ["/nonexistent/t2048-no-such-binary"]))
        self.assertIsNone(agent_sessions._run_probe(["false"]))
        self.assertEqual(agent_sessions._run_probe(["echo", "x"]), "x\n")

    def test_run_probe_times_out_to_no_answer(self):
        real = agent_sessions._PROBE_TIMEOUT_S
        agent_sessions._PROBE_TIMEOUT_S = 0.2
        self.addCleanup(setattr, agent_sessions, "_PROBE_TIMEOUT_S", real)
        self.assertIsNone(agent_sessions._run_probe(["sleep", "5"]))


class UnknownModelNoteTests(unittest.TestCase):
    def test_only_a_well_formed_agent_string_suppresses_the_note(self):
        for value in ("", None, "not-an-agent-string", "claudecode/"):
            with self.subTest(value=value):
                self.assertEqual(agent_sessions.unknown_model_note(value),
                                 agent_sessions.UNKNOWN_MODEL_NOTE)
        self.assertEqual(agent_sessions.unknown_model_note("claudecode/opus5"), "")


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
