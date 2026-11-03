#!/usr/bin/env python3
"""Offline tests for the t2179 shadow `>q` experiment harness.

Everything runs against a synthetic private store and fake `claude` / `codex`
binaries on PATH. No real CLI is ever invoked, nothing touches a real tmux
server, and no real aitasks_go content is used.

    python3 tests/test_shadow_q_harness.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SQ = REPO / "aidocs" / "benchmarks" / "shadow_q"
sys.path.insert(0, str(SQ))

import qspan  # noqa: E402
import validate as V  # noqa: E402
import store as S  # noqa: E402
import check_public as CP  # noqa: E402
import harness as H  # noqa: E402
import judge as J  # noqa: E402

E = V.Event

FAKE_CLI = r'''#!/usr/bin/env python3
import json, os, subprocess, sys, time, uuid
from pathlib import Path
name = Path(sys.argv[0]).name
argv = sys.argv[1:]
state = Path(os.environ["FAKE_STATE"]); state.mkdir(parents=True, exist_ok=True)
mode = os.environ.get("FAKE_MODE_" + name.upper(), "good")
cnt_f = state / f"{name}.count"
n = int(cnt_f.read_text()) + 1 if cnt_f.exists() else 1
cnt_f.write_text(str(n))
with (state / f"{name}.argv.jsonl").open("a") as fh:
    fh.write(json.dumps(argv) + "\n")
def out(o):
    print(json.dumps(o), flush=True)
def run(cmd):
    p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
    return p.stdout, p.returncode
GREETING = "Hello. I can help with `>e` explain, `>q` decide, `>t` task, `>pc` challenge; `>f` refetches."
ANSWER = "The decision is X. Option 1 does A (benefit, cost). Option 2 does B (benefit, cost). I suggest 1. You type it yourself."
judge = ("--tools" in argv) or ("--skip-git-repo-check" in argv)
if judge:
    prompt = sys.stdin.read()
    low = "PADDING-MARKER" in prompt
    if mode == "judge_bad_json":
        body = "not json at all"
    elif mode == "judge_out_of_range":
        body = json.dumps({"options": [{"option": "1", "what_it_does": 999, "benefit": -10, "cost": 2}],
                           "factual_correctness": 3, "decision_explained": 3, "recommendation_reasoning": 3,
                           "unsupported_claims": 3, "readability": 3, "advisory_only": True, "could_choose": 3,
                           "failure_flag": False, "rationale": "fake"})
    else:
        sc = 1 if low else 3
        body = json.dumps({"options": [{"option": "1", "what_it_does": sc, "benefit": sc, "cost": sc},
                                       {"option": "2", "what_it_does": sc, "benefit": sc, "cost": sc}],
                           "factual_correctness": 3, "decision_explained": sc, "recommendation_reasoning": sc,
                           "unsupported_claims": 3, "readability": 3, "advisory_only": True, "could_choose": sc,
                           "failure_flag": low, "rationale": "fake"})
    if name == "claude":
        out({"type": "result", "result": body, "total_cost_usd": 0.01})
    else:
        out({"type": "thread.started", "thread_id": str(uuid.uuid4())})
        out({"type": "item.completed", "item": {"id": "m", "type": "agent_message", "text": body}})
        out({"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 0, "output_tokens": 10}})
    sys.exit(0)
if mode == "hang":
    time.sleep(120); sys.exit(0)
if mode == "fail_once" and n == 1:
    print("fatal: transient", file=sys.stderr); sys.exit(1)
if mode == "fail_always":
    print("fatal: broken", file=sys.stderr); sys.exit(1)
resume = "--resume" in argv or (len(argv) > 1 and argv[1] == "resume")
cwd = Path.cwd()
cost = 10.0 if mode == "costly" else 0.1
if name == "claude":
    sid = argv[argv.index("--resume") + 1] if "--resume" in argv else str(uuid.uuid4())
    out({"type": "system", "subtype": "init", "session_id": sid,
         "model": "" if mode == "no_model" else "claude-fake-1", "cwd": str(cwd)})
    calls = []
    if mode == "loop":
        for i in range(30):
            out({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": f"l{i}", "name": "Bash",
                 "input": {"command": "./.aitask-scripts/aitask_skill_resolve_profile.sh shadow"}}]}})
            time.sleep(0.05)
        time.sleep(30); sys.exit(0)
    def tool(i, name_, inp, output=None, err=False):
        out({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": i, "name": name_, "input": inp}]}})
        if output is None and name_ == "Bash":
            output, rc = run(inp["command"]); err = rc != 0
        out({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": i,
             "content": output or "", "is_error": err}]}})
    denials = []
    if not resume:
        if mode == "capture_first":
            tool("c0", "Bash", {"command": "./.aitask-scripts/aitask_shadow_capture.sh"})
        tool("t1", "Bash", {"command": "./.aitask-scripts/aitask_skill_resolve_profile.sh shadow"})
        tool("t2", "Bash", {"command": "./.aitask-scripts/aitask_skill_render.sh aitask-shadow --profile fast --agent claude"})
        if mode != "no_read":
            fp = cwd / ".claude/skills/aitask-shadow-fast-/SKILL.md"
            body = "".join(f"{i:6}\t{ln}\n" for i, ln in enumerate(fp.read_text().splitlines(), start=1))
            tool("t3", "Read", {"file_path": str(fp)}, output=body)
        out({"type": "assistant", "message": {"content": [{"type": "text", "text": GREETING}]}})
        tool("t4", "Bash", {"command": "./.aitask-scripts/aitask_shadow_capture.sh"})
        tool("t5", "Bash", {"command": "./.aitask-scripts/aitask_shadow_capture.sh --phase 60_2"})
        result = GREETING
    else:
        if mode == "deny":
            out({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "d1", "name": "Bash",
                 "input": {"command": "./.aitask-scripts/aitask_shadow_capture.sh"}}]}})
            out({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "d1",
                 "content": "Permission denied", "is_error": True}]}})
            denials.append({"tool_name": "Bash", "tool_use_id": "d1",
                            "tool_input": {"command": "./.aitask-scripts/aitask_shadow_capture.sh"}})
        elif mode == "mismatch":
            tool("q1", "Bash", {"command": "./.aitask-scripts/aitask_shadow_capture.sh"}, output="garbage screen")
        elif mode != "no_capture":
            tool("q1", "Bash", {"command": "./.aitask-scripts/aitask_shadow_capture.sh"})
        if mode not in ("no_capture", "deny"):
            tool("q2", "Bash", {"command": "./.aitask-scripts/aitask_shadow_capture.sh --phase 60_2"})
        result = "" if mode == "no_answer" else ANSWER
    out({"type": "result", "subtype": "success", "is_error": False, "result": result, "session_id": sid,
         "total_cost_usd": cost, "usage": {"input_tokens": 1000, "output_tokens": 100},
         "modelUsage": {"claude-fake-1": {}}, "permission_denials": denials})
    sys.exit(0)
# codex
if not resume:
    tid = str(uuid.uuid4())
    sess = Path(os.environ["AIT_SHADOW_Q_CODEX_SESSIONS"]) / "2026" / "11" / "03"
    sess.mkdir(parents=True, exist_ok=True)
    if mode != "no_model":
        with (sess / f"rollout-2026-11-03T00-00-00-{tid}.jsonl").open("w") as fh:
            fh.write(json.dumps({"type": "session_meta", "payload": {"cli_version": "0.0-fake",
                                 "creator_account_id": "ACCOUNT-SECRET-123"}}) + "\n")
            fh.write(json.dumps({"type": "turn_context", "payload": {"model": "gpt-fake", "effort": "high"}}) + "\n")
else:
    tid = argv[argv.index("--json") + 1] if False else [a for a in argv if len(a) == 36 and a.count("-") == 4][0]
    cwd = Path.cwd()
out({"type": "thread.started", "thread_id": tid})
out({"type": "turn.started"})
k = [0]
def sh(cmd, output=None):
    k[0] += 1
    i = f"item_{k[0]}"
    out({"type": "item.started", "item": {"id": i, "type": "command_execution", "command": f"bash -lc '{cmd}'",
         "aggregated_output": "", "exit_code": None, "status": "in_progress"}})
    rc = 0
    if output is None:
        output, rc = run(cmd)
    out({"type": "item.completed", "item": {"id": i, "type": "command_execution", "command": f"bash -lc '{cmd}'",
         "aggregated_output": output, "exit_code": rc, "status": "completed" if rc == 0 else "failed"}})
if not resume:
    sh("./.aitask-scripts/aitask_skill_resolve_profile.sh shadow")
    sh("./.aitask-scripts/aitask_skill_render.sh aitask-shadow --profile fast --agent codex")
    if mode != "no_read":
        sh("sed -n 1,250p .agents/skills/aitask-shadow-fast-codex-/SKILL.md")
        sh("sed -n 250,400p .agents/skills/aitask-shadow-fast-codex-/SKILL.md")
    out({"type": "item.completed", "item": {"id": "m1", "type": "agent_message", "text": GREETING}})
    sh("./.aitask-scripts/aitask_shadow_capture.sh")
else:
    if mode != "no_capture":
        sh("./.aitask-scripts/aitask_shadow_capture.sh")
        sh("./.aitask-scripts/aitask_shadow_capture.sh --phase 60_2")
    out({"type": "item.completed", "item": {"id": "m2", "type": "agent_message", "text": ANSWER}})
out({"type": "turn.completed", "usage": {"input_tokens": 50000 if mode == "costly" else 1000,
     "cached_input_tokens": 0, "output_tokens": 100}})
'''


def write_store(root: Path) -> Path:
    st = root / "store"
    (st / "instructions").mkdir(parents=True)
    (st / "instructions" / "CLAUDE.md").write_text("# Synthetic project instructions\nKeep answers brief.\n")
    (st / "instructions" / "AGENTS.md").write_text("# Synthetic project instructions\nKeep answers brief.\n")
    (st / "instructions" / "docs").mkdir()
    (st / "instructions" / "docs" / "overview.md").write_text("Synthetic overview the instructions point at.\n")
    for agent, d in (("claude", "other-skill"), ("codex", "other-skill")):
        p = st / "skill_listing" / agent / d / "SKILL.md"
        p.parent.mkdir(parents=True)
        p.write_text("---\nname: other-skill\ndescription: A synthetic neighbour skill.\n---\nBody.\n")
    for sc in H.ALL_SCENARIOS:
        f = st / "fixtures" / sc
        (f / "task" / "_aitasks" / "t60").mkdir(parents=True)
        (f / "task" / "_aitasks" / "t60" / "t60_2_synthetic.md").write_text("---\nstatus: Implementing\n---\nSynthetic task body.\n")
        (f / "screen_1.txt").write_text(f"SCREEN {sc}: the followed agent asks a synthetic question with two options.\n"
                                        + "x" * 80 + "\n")
        (f / "phase.txt").write_text("PHASE:PLAN|WAITING:WAITING|SOURCE:native-prompt|CONSULTED:native-prompt|"
                                     "RECORDING:unknown|RESOLUTION:scoped|DETAIL:synthetic\n")
        (f / "context.txt").write_text("TASK_FILE:aitasks/t60/t60_2_synthetic.md\nPLAN_FILE:NOT_FOUND\n")
        (f / "reference.md").write_text("Synthetic reference: a private fact about zebra-quokka adapters lives here.\n")
        (f / "controls").mkdir()
        (f / "controls" / "shallow.md").write_text("PADDING-MARKER recommend option 1 with lots of restated narration.\n")
        (f / "controls" / "adequate.md").write_text("Explains both options.\n")
    (st / "leak_terms.txt").write_text("# terms\nzebraQuokkaAdapter\n")
    return st


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="sq_test_"))
        cls.store = write_store(cls.tmp)
        cls.bin = cls.tmp / "bin"
        cls.bin.mkdir()
        for name in ("claude", "codex"):
            p = cls.bin / name
            p.write_text(FAKE_CLI)
            p.chmod(0o755)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.case = Path(tempfile.mkdtemp(prefix="case_", dir=self.tmp))
        self.env_backup = dict(os.environ)
        os.environ["PATH"] = f"{self.bin}{os.pathsep}{os.environ['PATH']}"
        os.environ["FAKE_STATE"] = str(self.case / "state")
        os.environ["AIT_SHADOW_Q_SANDBOX_ROOT"] = str(self.case / "sbx")
        os.environ["AIT_SHADOW_Q_CODEX_SESSIONS"] = str(self.case / "codex_sessions")
        os.environ["AIT_SHADOW_Q_STORE"] = str(self.store)
        for k in list(os.environ):
            if k.startswith("FAKE_MODE_"):
                del os.environ[k]
        self.pub_backup = H.RUNS_PUBLIC
        H.RUNS_PUBLIC = self.case / "public_runs"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env_backup)
        H.RUNS_PUBLIC = self.pub_backup

    def experiment(self, batch="b", cap=80, cost=15.0, tokens=2_000_000, reserve=0, **lim):
        limits = H.load_limits()
        limits.update({"subject_turn_timeout_s": 20, "judge_call_timeout_s": 20, "kill_grace_s": 1})
        limits.update(lim)
        budget = H.Budget(cap, cost, tokens, reserve)
        agents = {"claude": {"agent_string": "claudecode/fake", "cli_id": "claude-fake-1", "dry_run_line": "x"},
                  "codex": {"agent_string": "codex/fake", "cli_id": "gpt-fake", "dry_run_line": "y"}}
        env_record = {"claude_version": "fake", "codex_version": "fake", "reasoning": {}, "codex_memories": "false"}
        return H.Experiment(batch, self.store, limits, budget, agents=agents, env_record=env_record,
                            store_commit="deadbeef")

    def assertProcessesGone(self, pid_file, within=3.0):
        pids = [int(x) for x in pid_file.read_text().split()]
        end = time.monotonic() + within
        alive = pids
        while time.monotonic() < end:
            alive = []
            for pid in pids:
                try:
                    st = Path(f"/proc/{pid}/stat").read_text().split()[2]
                except OSError:
                    continue
                if st != "Z":  # a zombie is dead, merely not yet reaped by init
                    alive.append(pid)
            if not alive:
                return
            time.sleep(0.05)
        self.fail(f"processes still alive: {alive}")

    def public_rows(self, batch, name):
        p = H.RUNS_PUBLIC / batch / name
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


# ---------------------------------------------------------------- freezing
class TestSpanAndVariants(unittest.TestCase):
    def test_each_variant_changes_only_the_span(self):
        for agent in ("claude", "codex"):
            base = (H.FROZEN / agent / "render" / "SKILL.md").read_text()
            for v in H.VARIANTS:
                out = H.build_variant(agent, v)
                qspan.assert_only_span_changed(base, out)
                self.assertEqual(qspan.extract_q_bullet(out), H.variant_bullet(v))
            self.assertEqual(H.build_variant(agent, "v1_baseline"), base)

    def test_occurs_once_violation_fails(self):
        base = (H.FROZEN / "claude" / "render" / "SKILL.md").read_text()
        doubled = base + "\n" + qspan.extract_q_bullet(base) + "\n"
        with self.assertRaises(qspan.SpanError):
            qspan.find_q_span(doubled)
        with self.assertRaises(qspan.SpanError):
            qspan.find_q_span(base.replace("- `>q`", "- `>Q`"))

    def test_change_outside_span_is_refused(self):
        base = (H.FROZEN / "claude" / "render" / "SKILL.md").read_text()
        bad = base.replace("## Guardrail", "## Guardrails")
        with self.assertRaises(qspan.SpanError):
            qspan.assert_only_span_changed(base, bad)

    def test_mutant_occurs_once_goes_red(self):
        """Mutant: weaken the occurs-once check; the duplicate test must then fail."""
        src = (SQ / "qspan.py").read_text()
        mutated = src.replace("if len(starts) != 1:", "if len(starts) < 1:")
        self.assertNotEqual(src, mutated)
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "qspan_mutant.py").write_text(mutated)
            spec = importlib.util.spec_from_file_location("qspan_mutant", tmp / "qspan_mutant.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            base = (H.FROZEN / "claude" / "render" / "SKILL.md").read_text()
            doubled = base + "\n" + mod.extract_q_bullet(base) + "\n"
            with self.assertRaises(AssertionError):
                with self.assertRaises(mod.SpanError):
                    mod.find_q_span(doubled)
        finally:
            shutil.rmtree(tmp)

    def test_minimal_render_keeps_bullet_and_guardrail(self):
        m = H.build_minimal("codex", "v3_explicit_semantics")
        self.assertIn(H.variant_bullet("v3_explicit_semantics"), m)
        self.assertIn("## Guardrail", m)
        self.assertIn("## Step 1", m)
        self.assertNotIn("## Step 0", m)
        self.assertNotIn("## Step 2", m)

    def test_freeze_record_matches_files(self):
        rec = H.load_freeze()
        for agent, a in rec["agents"].items():
            for rel, digest in a["files"].items():
                self.assertEqual(S.sha256_file(H.FROZEN / agent / rel), digest, rel)
        self.assertEqual(S.sha256_file(H.VARIANTS_DIR / "v1_baseline.md"), rec["v1_baseline_sha256"])


# ---------------------------------------------------------------- sandbox
class TestSandbox(Base):
    def test_ancestor_check_refuses_instruction_parents(self):
        for marker in ("CLAUDE.md", ".claude"):
            parent = self.case / f"p_{marker.strip('.')}"
            parent.mkdir()
            if marker.startswith("."):
                (parent / marker / "skills").mkdir(parents=True)
                (parent / marker / "skills" / "SKILL.md").write_text("x")
            else:
                (parent / marker).write_text("x")
            with self.assertRaises(H.SandboxError):
                H.build_sandbox(parent / "a" / "sandbox", "claude", "v1_baseline", "fresh",
                                ["file_selection"], self.store)

    def test_empty_ancestor_dirs_are_flagged_not_refused(self):
        parent = self.case / "p_empty"
        (parent / ".agents").mkdir(parents=True)
        (parent / ".codex").mkdir()
        found = H.check_ancestors(parent / "a" / "sandbox")
        # Other ancestors (e.g. a transient empty /tmp/.agents left by a Codex run) may be
        # reported too; this test owns only the fixture parent's entries.
        mine = sorted(Path(f).name for f in found if Path(f).parent == parent.resolve())
        self.assertEqual(mine, [".agents", ".codex"])
        (parent / ".agents" / "skills").mkdir()
        (parent / ".agents" / "skills" / "SKILL.md").write_text("x")
        with self.assertRaises(H.SandboxError):
            H.check_ancestors(parent / "a" / "sandbox")

    def test_resume_reruns_only_never_launched_cells(self):
        os.environ["FAKE_MODE_CODEX"] = "good"
        exp = self.experiment("rs")
        good = H.Cell("fresh", "codex", "v1_baseline", ["file_selection"])
        bad = H.Cell("fresh", "codex", "v2_concise_intent", ["file_selection"])
        exp.run_session(good, 0)
        exp.sessions_sink.append({"batch": "rs", "run_id": bad.cell_id + "-a1-x", "outcome": "infra_failure:setup_failed"})
        self.assertEqual([c.cell_id for c in H.pending_cells("rs", [good, bad])], [bad.cell_id])

    def test_layout_matches_each_stub_dispatch_path(self):
        for agent in ("claude", "codex"):
            sbx = H.build_sandbox(self.case / "sbx" / agent / "sandbox", agent, "v2_concise_intent", "fresh",
                                  ["file_selection"], self.store)
            stub = (sbx.root / H.AGENT_DIRS[agent]["stub"]).read_text()
            dispatch = H.AGENT_DIRS[agent]["render"].replace("-fast-", "-<profile>-")
            self.assertIn(dispatch + "/SKILL.md", stub)
            self.assertEqual(sbx.dispatched, sbx.root / H.AGENT_DIRS[agent]["render"] / "SKILL.md")
            self.assertIn(H.variant_bullet("v2_concise_intent"), sbx.dispatched.read_text())
            other = H.AGENT_DIRS["codex" if agent == "claude" else "claude"]["render"]
            self.assertFalse((sbx.root / other).exists())
            names = {p.name for p in sbx.root.rglob("*")}
            self.assertFalse({"reference.md", "shallow.md", "adequate.md"} & names)
            self.assertTrue((sbx.root / "CLAUDE.md").exists())
            self.assertTrue((sbx.root / "docs" / "overview.md").exists())
            self.assertTrue((sbx.root / "aitasks/t60/t60_2_synthetic.md").exists())

    def test_minimal_condition_has_no_instructions_or_listing(self):
        sbx = H.build_sandbox(self.case / "sbx" / "m" / "sandbox", "claude", "v1_baseline", "minimal",
                              ["file_selection"], self.store)
        self.assertFalse((sbx.root / "CLAUDE.md").exists())
        self.assertFalse((sbx.root / ".claude/skills/other-skill").exists())

    def test_subject_env_has_no_tmux(self):
        os.environ["TMUX"] = "/tmp/tmux-1/default,1,0"
        os.environ["TMUX_PANE"] = "%1"
        os.environ["CLAUDE_EFFORT"] = "max"
        os.environ["HERDR_ENV"] = "1"
        env, stripped = H.subject_env()
        for k in ("TMUX", "TMUX_PANE", "CLAUDE_EFFORT", "HERDR_ENV"):
            self.assertNotIn(k, env)
            self.assertIn(k, stripped)
        self.assertEqual(list(Path(env["TMUX_TMPDIR"]).iterdir()), [])

    def test_allowlist_covers_every_replay_helper(self):
        helpers = H.replay_helpers_for_allowlist()
        self.assertTrue(set(helpers) <= set(V.REPLAY_HELPERS), helpers)
        for h in ("aitask_skill_resolve_profile.sh", "aitask_skill_render.sh", "aitask_shadow_capture.sh",
                  "aitask_shadow_context.sh", "aitask_explain_context.sh"):
            self.assertIn(h, helpers)
        tools = H.claude_allowed_tools(Path("/x"))
        for h in helpers:
            self.assertIn(f"Bash(./.aitask-scripts/{h}:*)", tools)

    def test_stubs_write_nothing_in_a_read_only_copy(self):
        sbx = H.build_sandbox(self.case / "sbx" / "ro" / "sandbox", "codex", "v1_baseline", "fresh",
                              ["file_selection"], self.store)
        ro = self.case / "ro_copy"
        shutil.copytree(sbx.root, ro)
        for p in [ro, *ro.rglob("*")]:
            mode = p.stat().st_mode
            p.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        try:
            expected = sbx.expected_for(1)
            for helper, form, args in H.STUB_FORMS:
                p = subprocess.run([f"./.aitask-scripts/{helper}", *args], cwd=ro, capture_output=True, text=True,
                                   input=H.STDIN_PROBE if form == "stdin" else None)
                self.assertEqual(p.returncode, 0, (helper, form, p.stderr))
                want = "bold line\n" if form == "stdin" else expected[(helper, form)]
                self.assertEqual(p.stdout, want, (helper, form))
        finally:
            for p in [ro, *ro.rglob("*")]:
                p.chmod(p.stat().st_mode | stat.S_IWUSR)

    def test_preflight_refuses_a_wrapper_that_lets_writes_through(self):
        sbx = H.build_sandbox(self.case / "sbx" / "pf" / "sandbox", "codex", "v1_baseline", "fresh",
                              ["file_selection"], self.store)
        res = H.preflight(sbx, ["env"])  # "env" runs the command unsandboxed
        neg = [r for r in res if r["helper"] == "negative_control"]
        self.assertEqual(len(neg), 1)
        self.assertFalse(neg[0]["ok"])
        self.assertTrue(all(r["ok"] for r in res if r["helper"] != "negative_control"))

    def test_preflight_wrapper_missing_is_reported(self):
        os.environ["PATH"] = "/usr/bin:/bin"
        self.assertIsNone(H.codex_sandbox_wrapper())

    def test_manifest_refuses_files_git_does_not_track(self):
        st = self.case / "gitstore"
        shutil.copytree(self.store, st)
        subprocess.run(["git", "init", "-q", str(st)], check=True)
        (st / ".gitignore").write_text("aitasks\n")
        (st / "fixtures" / "file_selection" / "task" / "aitasks").mkdir()
        (st / "fixtures" / "file_selection" / "task" / "aitasks" / "x.md").write_text("ignored\n")
        subprocess.run(["git", "-C", str(st), "add", "-A"], check=True)
        files = S.build_manifest_files(st)
        self.assertEqual(S.untracked_files(st, files), ["fixtures/file_selection/task/aitasks/x.md"])

    def test_manifest_mismatch_refuses(self):
        mf = {"files": S.build_manifest_files(self.store)}
        self.assertEqual(S.check_manifest(self.store, mf), [])
        target = self.store / "fixtures" / "file_selection" / "screen_1.txt"
        orig = target.read_text()
        try:
            target.write_text(orig + "changed\n")
            self.assertIn("changed:fixtures/file_selection/screen_1.txt", S.check_manifest(self.store, mf))
        finally:
            target.write_text(orig)


# ---------------------------------------------------------------- public / private
class TestPublicPrivate(Base):
    def test_public_sink_rejects_non_whitelisted_data(self):
        sink = S.PublicSink(self.case / "s.jsonl", "trial")
        sink.append({"run_id": "r", "outcome": "valid", "flags": {"x": True}})
        with self.assertRaises(S.LeakError):
            sink.append({"answer_text": "anything"})
        with self.assertRaises(S.LeakError):
            sink.append({"run_id": "y" * 400})
        with self.assertRaises(S.LeakError):
            sink.append({"cell": {"secret": "x"}})
        with self.assertRaises(S.LeakError):
            sink.append({"flags": {"nested": ["a"]}})
        self.assertEqual(len((self.case / "s.jsonl").read_text().splitlines()), 1)

    def test_private_sink_cannot_escape_the_store(self):
        with self.assertRaises(S.LeakError):
            S.PrivateSink(self.store).path("../outside.txt")

    def test_check_public_flags_planted_lines_and_terms(self):
        planted = "Synthetic reference: a private fact about zebra-quokka adapters lives here."
        public = {"aidocs/x/report.md": f"intro\n{planted}\nend\n"}
        hits = CP.scan(public, self.store, known_public=set())
        self.assertTrue(any(":shared_line:" in h for h in hits), hits)
        self.assertEqual(CP.scan({"a.md": "nothing private here at all, just a long public sentence.\n"},
                                 self.store, known_public=set()), [])
        self.assertTrue(CP.scan({"a.md": "uses zebraQuokkaAdapter here\n"}, self.store, known_public=set()))
        self.assertEqual(CP.scan({"a.md": "uses zebraQuokkaAdapterX here\n"}, self.store, known_public=set()), [])
        # A line that is also known-public is not a leak.
        self.assertEqual(CP.scan(public, self.store, known_public={CP.normalise(planted)}), [])

    def test_identifier_only_lines_are_not_leaks_but_prose_is(self):
        (self.store / "ids.json").write_text(json.dumps(
            {"trial_id": "fresh-claude-v1_baseline-file_selection-r1-a1-103145-3fe8-t2",
             "note": "a private sentence long enough to count as a leak if published"}, indent=2))
        try:
            pub = {"s.json": '  "trial_id": "fresh-claude-v1_baseline-file_selection-r1-a1-103145-3fe8-t2",\n'}
            self.assertEqual(CP.scan(pub, self.store, known_public=set()), [])
            pub2 = {"s.md": "a private sentence long enough to count as a leak if published\n"}
            self.assertTrue(CP.scan(pub2, self.store, known_public=set()))
        finally:
            (self.store / "ids.json").unlink()

    def test_new_frozen_file_cannot_certify_private_text(self):
        planted = "Synthetic reference: a private fact about zebra-quokka adapters lives here."
        repo = self.case / "repo"
        (repo / "seed").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "seed" / "aitasks_agent_instructions.seed.md").write_text("A committed public line that is long enough.\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-qm", "x"], check=True)
        # A working-tree-only frozen file carrying the private line must not exempt it.
        frozen = repo / "aidocs" / "benchmarks" / "shadow_q" / "frozen"
        frozen.mkdir(parents=True)
        (frozen / "NEW.md").write_text(planted + "\n")
        kp = CP.known_public_lines(repo)
        self.assertNotIn(CP.normalise(planted), kp)
        self.assertIn(CP.normalise("A committed public line that is long enough."), kp)
        hits = CP.scan({"aidocs/benchmarks/shadow_q/frozen/NEW.md": planted + "\n"}, self.store, repo=repo)
        self.assertTrue(any(":shared_line:" in h for h in hits), hits)

    def test_skill_file_reads_in_streams_are_not_private(self):
        run = self.store / "runs" / "t2" / "r-claude-1"
        run.mkdir(parents=True)
        skill_line = "This line came from a public skill file that the subject read."
        answer_line = "This answer line quotes the private screen in a long sentence."
        rows = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "a", "name": "Read",
                  "input": {"file_path": "/s/.claude/skills/aitask-shadow-fast-/SKILL.md"}}]}},
                {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "a", "content": skill_line}]}},
                {"type": "result", "result": answer_line}]
        (run / "turn1.stdout.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        try:
            self.assertEqual(CP.scan({"p.md": skill_line + "\n"}, self.store, known_public=set()), [])
            self.assertTrue(CP.scan({"p.md": answer_line + "\n"}, self.store, known_public=set()))
        finally:
            shutil.rmtree(self.store / "runs")

    def test_check_public_decodes_jsonl_streams(self):
        run = self.store / "runs" / "t" / "r1"
        run.mkdir(parents=True)
        secret = "The subject quoted a private line that is long enough to count here."
        (run / "turn1.stdout.jsonl").write_text(json.dumps({"type": "x", "text": "a\n" + secret}) + "\n")
        try:
            hits = CP.scan({"p.md": secret + "\n"}, self.store, known_public=set())
            self.assertTrue(hits)
        finally:
            shutil.rmtree(self.store / "runs")


# ---------------------------------------------------------------- validator
Q_LINES = ["- `>q` — **Help me decide** synthetic bullet", "1. Capture the screen again first."]
BULLET_TEXT = "\n".join(f"   {281 + i}\t{ln}" for i, ln in enumerate(Q_LINES))


def spec_for(agent="claude", q_turns=(2,), expected=None, nlines=400, span=(281, 300), **kw):
    kw.setdefault("q_lines", Q_LINES)
    return V.SessionSpec(agent, "fresh", list(q_turns), span, nlines, True, expected or {}, **kw)


SCREEN = "SCREEN line one of the replay screen\n" + "y" * 600 + "\nlast line of the screen\n"
PHASE = "PHASE:PLAN|WAITING:WAITING|SOURCE:native-prompt\n"
EXP = {("aitask_shadow_capture.sh", "noarg"): SCREEN, ("aitask_shadow_capture.sh", "phase"): PHASE,
       ("aitask_skill_resolve_profile.sh", "default"): "fast\n"}
GREET = E("text", text="I can do `>e`, `>q`, `>t` and `>pc`.")


def read_full(agent="claude", output=BULLET_TEXT, exit_code=0, is_error=False):
    if agent == "claude":
        return E("tool", name="Read", tool_id="r", input={"file_path": "/s/.claude/skills/aitask-shadow-fast-/SKILL.md"},
                 output=output, exit_code=exit_code, is_error=is_error)
    return E("tool", name="shell", command="bash -lc 'cat .agents/skills/aitask-shadow-fast-codex-/SKILL.md'",
             output=output, exit_code=exit_code, is_error=is_error)


def cap(args="", out=SCREEN, rc=0):
    return E("tool", name="Bash", command=f"./.aitask-scripts/aitask_shadow_capture.sh {args}".strip(),
             output=out, exit_code=rc)


def q_turn(*events, index=2):
    return V.Turn(index, [*events, E("final", text="An answer.")], 0, "")


class TestValidator(unittest.TestCase):
    def classify(self, turns, spec):
        return V.classify_session(turns, spec)

    def test_valid(self):
        t1 = V.Turn(1, [read_full(), GREET], 0, "")
        t2 = q_turn(cap(), cap("--phase 60_2", PHASE))
        r = self.classify([t1, t2], spec_for(expected={2: EXP}))
        self.assertEqual(r["trials"][0]["outcome"], "valid")

    def test_variant_not_read(self):
        t1 = V.Turn(1, [GREET], 0, "")
        r = self.classify([t1, q_turn(cap(), cap("--phase", PHASE))], spec_for(expected={2: EXP}))
        self.assertEqual(r["trials"][0]["outcome"], "subject_noncompliance:variant_not_loaded")

    def test_ranged_read_that_misses_the_span(self):
        ev = E("tool", name="shell", exit_code=0, output="head part",
               command="bash -lc \"sed -n '1,200p' .agents/skills/aitask-shadow-fast-codex-/SKILL.md\"")
        ev2 = E("tool", name="shell", exit_code=0, output=BULLET_TEXT,
                command="bash -lc \"sed -n '290,397p' .agents/skills/aitask-shadow-fast-codex-/SKILL.md\"")
        t1 = V.Turn(1, [ev, ev2, GREET], 0, "")
        sp = spec_for("codex", expected={2: EXP})
        self.assertEqual(V.variant_load([t1], sp), "not_loaded")
        ev3 = E("tool", name="shell", exit_code=0, output=BULLET_TEXT,
                command="bash -lc \"sed -n '200,290p' .agents/skills/aitask-shadow-fast-codex-/SKILL.md\"")
        self.assertEqual(V.variant_load([V.Turn(1, [ev, ev3, ev2], 0, "")], sp), "loaded")

    def test_claude_read_offset_limit_and_skill_tool(self):
        sp = spec_for()
        part = E("tool", name="Read", exit_code=0, output="first part",
                 input={"file_path": "/s/.claude/skills/aitask-shadow-fast-/SKILL.md", "offset": 1, "limit": 250})
        self.assertEqual(V.variant_load([V.Turn(1, [part], 0, "")], sp), "not_loaded")
        rest = E("tool", name="Read", exit_code=0, output=BULLET_TEXT,
                 input={"file_path": "/s/.claude/skills/aitask-shadow-fast-/SKILL.md", "offset": 251, "limit": 200})
        self.assertEqual(V.variant_load([V.Turn(1, [part, rest], 0, "")], sp), "loaded")
        sk = E("tool", name="Skill", input={"skill": "aitask-shadow-fast-"}, exit_code=0, output="Launching skill")
        self.assertEqual(V.variant_load([V.Turn(1, [sk], 0, "")], sp), "uncertain")  # content not seen
        inj = E("injected", text="\n".join(Q_LINES))
        self.assertEqual(V.variant_load([V.Turn(1, [sk, inj], 0, "")], sp), "loaded")

    def test_failed_variant_read_never_counts(self):
        sp = spec_for(expected={2: EXP})
        bad = read_full(output="Permission denied", exit_code=1, is_error=True)
        t2 = q_turn(cap(), cap("--phase", PHASE))
        r = self.classify([V.Turn(1, [bad, GREET], 0, ""), t2], sp)
        self.assertEqual(r["trials"][0]["outcome"], "subject_noncompliance:variant_not_loaded")
        unanswered = read_full(output="", exit_code=None)
        self.assertEqual(V.variant_load([V.Turn(1, [unanswered], 0, "")], sp), "not_loaded")

    def test_covering_read_that_did_not_return_the_bullet_is_uncertain(self):
        sp = spec_for(expected={2: EXP})
        truncated = read_full(output="... [output truncated] ...")
        r = self.classify([V.Turn(1, [truncated, GREET], 0, ""), q_turn(cap(), cap("--phase", PHASE))], sp)
        self.assertEqual(r["trials"][0]["outcome"], "uncertain_load")

    def test_partial_capture_delivery_is_not_a_valid_trial(self):
        t1 = V.Turn(1, [read_full(), GREET], 0, "")
        piped = E("tool", name="Bash", command="./.aitask-scripts/aitask_shadow_capture.sh | head -1",
                  output=SCREEN.splitlines()[0], exit_code=0)
        r = self.classify([t1, q_turn(piped, cap("--phase", PHASE))], spec_for(expected={2: EXP}))
        self.assertEqual(r["trials"][0]["outcome"], "subject_noncompliance:capture_not_delivered")
        head_only = cap(out=SCREEN[:300])
        r = self.classify([t1, q_turn(head_only, cap("--phase", PHASE))], spec_for(expected={2: EXP}))
        self.assertEqual(r["trials"][0]["outcome"], "uncertain_delivery")
        both = q_turn(piped, cap(), cap("--phase", PHASE))
        self.assertEqual(self.classify([t1, both], spec_for(expected={2: EXP}))["trials"][0]["outcome"], "valid")

    def test_no_capture_in_q_turn(self):
        t1 = V.Turn(1, [read_full(), GREET, cap(), cap("--phase", PHASE)], 0, "")
        r = self.classify([t1, q_turn()], spec_for(expected={1: EXP, 2: EXP}))
        self.assertEqual(r["trials"][0]["outcome"], "subject_noncompliance:no_fresh_capture")

    def test_capture_only_in_turn_one_does_not_satisfy_rule_two(self):
        t1 = V.Turn(1, [read_full(), GREET, cap(), cap("--phase", PHASE)], 0, "")
        t2 = q_turn(cap("--phase", PHASE))
        r = self.classify([t1, t2], spec_for(expected={1: EXP, 2: EXP}))
        self.assertEqual(r["trials"][0]["outcome"], "subject_noncompliance:no_fresh_capture")

    def test_permission_denied_on_a_helper_is_infra(self):
        t1 = V.Turn(1, [read_full(), GREET], 0, "")
        denied = E("tool", name="Bash", tool_id="d", command="./.aitask-scripts/aitask_shadow_capture.sh",
                   output="denied", is_error=True, exit_code=1)
        den = E("denial", name="Bash", tool_id="d", command="./.aitask-scripts/aitask_shadow_capture.sh")
        r = self.classify([t1, q_turn(denied, den)], spec_for(expected={2: EXP}))
        self.assertEqual(r["trials"][0]["outcome"], "infra_failure:permission_denied")

    def test_unparseable_read_is_uncertain(self):
        odd = E("tool", name="shell", exit_code=0, output=BULLET_TEXT,
                command="bash -lc 'python3 -c \"print(open(\\\".agents/skills/aitask-shadow-fast-codex-/SKILL.md\\\").read())\"'")
        t1 = V.Turn(1, [odd, GREET], 0, "")
        r = self.classify([t1, q_turn(cap(), cap("--phase", PHASE))], spec_for("codex", expected={2: EXP}))
        self.assertEqual(r["trials"][0]["outcome"], "uncertain_load")

    def test_output_mismatch_is_infra(self):
        t1 = V.Turn(1, [read_full(), GREET], 0, "")
        t2 = q_turn(cap(out="totally different"), cap("--phase", PHASE))
        r = self.classify([t1, t2], spec_for(expected={2: EXP}))
        self.assertEqual(r["trials"][0]["outcome"], "infra_failure:stub_output_mismatch")

    def test_match_kinds(self):
        self.assertEqual(V.match_output(SCREEN, "prefix\n" + SCREEN, False), "full")
        trunc = SCREEN[:520] + "\n[... truncated ...]\n" + SCREEN[-520:]
        self.assertEqual(V.match_output(SCREEN, trunc, False), "head_tail")
        self.assertEqual(V.match_output(SCREEN, "line 3 only", True), "transformed")
        self.assertEqual(V.match_output(SCREEN, "nope", False), "mismatch")

    def test_bash_lc_wrapper_is_attributed(self):
        calls, _ = V.helper_calls("/bin/bash -lc './.aitask-scripts/aitask_shadow_capture.sh --phase 60_2'")
        self.assertEqual([(c.helper, c.form) for c in calls], [("aitask_shadow_capture.sh", "phase")])
        calls, others = V.helper_calls("bash -lc './.aitask-scripts/aitask_shadow_capture.sh | head -5; "
                                       "./.aitask-scripts/aitask_lock.sh --check 1'")
        self.assertTrue(calls[0].piped)
        self.assertEqual(others, ["aitask_lock.sh"])

    def test_tmux_is_an_advisory_violation(self):
        t1 = V.Turn(1, [read_full(), GREET], 0, "")
        t2 = q_turn(cap(), cap("--phase", PHASE), E("tool", name="Bash", command="tmux send-keys -t %9999 1 Enter"))
        r = self.classify([t1, t2], spec_for(expected={2: EXP}))
        self.assertEqual(r["trials"][0]["outcome"], "subject_noncompliance:advisory_violation")

    def test_compound_helper_command_is_allowed_and_attributed(self):
        tools = H.claude_allowed_tools(Path("/x"))
        self.assertIn("Bash(echo:*)", tools)
        self.assertNotIn("Bash(rm:*)", tools)
        calls, _ = V.helper_calls('./.aitask-scripts/aitask_shadow_capture.sh; echo "EXIT:$?"')
        self.assertEqual([(c.helper, c.form, c.piped) for c in calls], [("aitask_shadow_capture.sh", "noarg", False)])
        self.assertEqual(V.match_output(SCREEN, SCREEN + "EXIT:0\n", False), "full")

    def test_outside_path_is_flagged(self):
        self.assertTrue(V.reaches_outside("cat /home/u/Work/x/aidocs/shadow_q_store/fixtures/a/reference.md"))
        self.assertFalse(V.reaches_outside("cat ./aitasks/t60/t60_2.md"))
        self.assertFalse(V.reaches_outside("/usr/bin/bash -lc 'cat aidocs/some_project/overview.md'"))

    def test_web_tool_use_is_counted(self):
        raw = "\n".join(json.dumps(o) for o in [
            {"type": "item.completed", "item": {"id": "w", "type": "web_search", "query": "go list"}},
            {"type": "item.completed", "item": {"id": "m", "type": "agent_message", "text": "answer"}}])
        t1 = V.Turn(1, [read_full(), GREET], 0, "")
        t2 = V.Turn(2, [cap(), cap("--phase", PHASE), *V.parse_codex(raw)], 0, "")
        r = V.classify_session([t1, t2], spec_for("codex", expected={2: EXP}))
        self.assertEqual(r["trials"][0]["flags"]["web_tools"], 1)

    def test_greeting_order(self):
        ok = V.Turn(1, [read_full(), GREET, cap()], 0, "")
        self.assertFalse(V.capture_before_greeting(ok))
        bad = V.Turn(1, [read_full(), cap(), GREET], 0, "")
        self.assertTrue(V.capture_before_greeting(bad))
        preamble_only = V.Turn(1, [E("text", text="Resolving the profile."), cap(), GREET], 0, "")
        self.assertTrue(V.capture_before_greeting(preamble_only))

    def test_greeting_order_both_trace_formats(self):
        claude_raw = "\n".join(json.dumps(o) for o in [
            {"type": "assistant", "message": {"content": [{"type": "text", "text": GREET.text}]}},
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "a", "name": "Bash",
                                                           "input": {"command": "./.aitask-scripts/aitask_shadow_capture.sh"}}]}},
        ])
        self.assertFalse(V.capture_before_greeting(V.Turn(1, V.parse_claude(claude_raw))))
        codex_raw = "\n".join(json.dumps(o) for o in [
            {"type": "item.started", "item": {"id": "1", "type": "command_execution",
                                              "command": "bash -lc ./.aitask-scripts/aitask_shadow_capture.sh"}},
            {"type": "item.completed", "item": {"id": "1", "type": "command_execution", "exit_code": 0,
                                                "command": "bash -lc ./.aitask-scripts/aitask_shadow_capture.sh",
                                                "aggregated_output": "x", "status": "completed"}},
            {"type": "item.completed", "item": {"id": "m", "type": "agent_message", "text": GREET.text}},
        ])
        self.assertTrue(V.capture_before_greeting(V.Turn(1, V.parse_codex(codex_raw))))

    def test_limit_timeouts_split_by_activity(self):
        t1 = V.Turn(1, [read_full(), GREET], 0, "")
        hung = V.Turn(2, [], None, "limit_timeout")
        r = self.classify([t1, hung], spec_for(expected={2: EXP}))
        self.assertEqual(r["trials"][0]["outcome"], "infra_failure:limit_timeout")
        busy = V.Turn(2, [cap(), E("text", text="thinking")], None, "limit_timeout")
        r = self.classify([t1, busy], spec_for(expected={2: EXP}))
        self.assertEqual(r["trials"][0]["outcome"], "subject_noncompliance:limit_timeout")

    def test_summary_denominators(self):
        trials = [{"outcome": "valid", "trial_id": "a"}, {"outcome": "valid", "trial_id": "b"},
                  {"outcome": "infra_failure:x"}, {"outcome": "uncertain_load"},
                  {"outcome": "uncertain_delivery"}, {"outcome": "subject_noncompliance:no_answer"},
                  {"outcome": "not_run:pilot_stopped:claude_cost"}]
        s = V.summarise(trials)
        self.assertEqual(s["denominator"], 3)
        self.assertAlmostEqual(s["compliance_rate"], 2 / 3)
        self.assertAlmostEqual(s["compliance_sensitivity"], 2 / 6)
        self.assertEqual(s["conditional_quality_n"], 2)
        self.assertNotIn("overall_success", s)  # never claimed without judgments

    def test_overall_success_needs_adequate_calibrated_judgments(self):
        j = lambda judge, ff, cc, cal=True: {"judge": judge, "failure_flag": ff, "could_choose": cc, "calibrated": cal}
        trials = [{"outcome": "valid", "trial_id": t} for t in "abcde"] + [{"outcome": "subject_noncompliance:x"}]
        judgments = {
            "a": [j("claude", False, 3), j("codex", False, 2)],      # adequate
            "b": [j("claude", False, 3), j("codex", True, 3)],       # one flag -> inadequate
            "c": [j("claude", False, 2), j("codex", False, 1)],      # mean 1.5 < 2 -> inadequate
            "d": [j("claude", False, 3), j("codex", True, 0, False)],  # uncalibrated judge ignored -> adequate
            "e": [j("claude", False, 3, False)],                     # no calibrated judgment -> unknown
        }
        s = V.summarise(trials, judgments)
        self.assertEqual((s["adequate"], s["adequacy_unknown"]), (2, 1))
        self.assertAlmostEqual(s["overall_success"], 2 / 6)
        self.assertAlmostEqual(s["compliance_rate"], 5 / 6)


# ---------------------------------------------------------------- runner with fake CLIs
class TestRunner(Base):
    def test_good_sessions_both_agents(self):
        exp = self.experiment()
        for agent in ("claude", "codex"):
            res = exp.run_session(H.Cell("fresh", agent, "v1_baseline", ["file_selection"]), 0)
            self.assertEqual([t["outcome"] for t in res["trials"]], ["valid"], res)
            self.assertEqual(res["session"]["reported_model"], "claude-fake-1" if agent == "claude" else "gpt-fake")
        sessions = (H.RUNS_PUBLIC / "b" / "sessions.jsonl").read_text()
        self.assertNotIn("ACCOUNT-SECRET-123", sessions)
        self.assertNotIn("ACCOUNT-SECRET-123", json.dumps(exp.env_record))
        self.assertEqual(self.public_rows("b", "sessions.jsonl")[1]["model_source"], "codex_rollout_turn_context")

    def test_missing_model_is_infra(self):
        os.environ["FAKE_MODE_CODEX"] = "no_model"
        res = self.experiment().run_session(H.Cell("fresh", "codex", "v1_baseline", ["file_selection"]), 0)
        self.assertEqual(res["trials"][0]["outcome"], "infra_failure:model_unverified")

    def test_capture_before_greeting_is_flagged_only(self):
        os.environ["FAKE_MODE_CLAUDE"] = "capture_first"
        res = self.experiment().run_session(H.Cell("smoke", "claude", "v1_baseline", ["file_selection"]), 0)
        ok, stops, notes = H.smoke_verdict(res)
        self.assertTrue(ok, stops)
        self.assertIn("capture_before_greeting", notes)
        os.environ["FAKE_MODE_CLAUDE"] = "good"
        res = self.experiment().run_session(H.Cell("smoke", "claude", "v1_baseline", ["file_selection"]), 0)
        ok, stops, notes = H.smoke_verdict(res)
        self.assertTrue(ok, stops)
        self.assertNotIn("capture_before_greeting", notes)

    def test_smoke_stops_when_the_variant_is_not_read(self):
        os.environ["FAKE_MODE_CODEX"] = "no_read"
        res = self.experiment().run_session(H.Cell("smoke", "codex", "v1_baseline", ["file_selection"]), 0)
        ok, stops, _ = H.smoke_verdict(res)
        self.assertFalse(ok)
        self.assertTrue(any(s.startswith("variant_load") for s in stops))

    def test_mismatch_and_denial_classes(self):
        os.environ["FAKE_MODE_CLAUDE"] = "mismatch"
        res = self.experiment("m").run_session(H.Cell("fresh", "claude", "v1_baseline", ["file_selection"]), 0)
        self.assertEqual(res["trials"][0]["outcome"], "infra_failure:stub_output_mismatch")
        os.environ["FAKE_MODE_CLAUDE"] = "deny"
        res = self.experiment("d").run_session(H.Cell("fresh", "claude", "v1_baseline", ["file_selection"]), 0)
        self.assertEqual(res["trials"][0]["outcome"], "infra_failure:permission_denied")

    def test_looping_fake_is_killed_for_tool_calls(self):
        os.environ["FAKE_MODE_CLAUDE"] = "loop"
        t0 = time.monotonic()
        res = self.experiment().run_session(H.Cell("fresh", "claude", "v1_baseline", ["file_selection"]), 0)
        self.assertLess(time.monotonic() - t0, 15)
        rows = self.public_rows("b", "invocations.jsonl")
        self.assertEqual(rows[0]["outcome"], "limit_tool_calls")
        self.assertTrue(res["trials"][0]["outcome"].startswith(("subject_noncompliance", "infra_failure")))

    def test_hanging_fake_times_out_and_its_group_is_gone(self):
        os.environ["FAKE_MODE_CODEX"] = "hang"
        exp = self.experiment(subject_turn_timeout_s=2)
        sbx = self.case / "hang_sbx"
        sbx.mkdir()
        rr = H.run_cli(["codex", "exec", "--json", "hang"], sbx, dict(os.environ), "codex", 2, 15,
                       self.case / "h.out", self.case / "h.err", 1)
        self.assertEqual(rr.killed, "limit_timeout")
        out = subprocess.run(["pgrep", "-f", str(self.bin / "codex")], capture_output=True, text=True).stdout
        self.assertEqual(out.strip(), "")
        res = exp.run_session(H.Cell("fresh", "codex", "v1_baseline", ["file_selection"]), 0)
        self.assertEqual(res["trials"][0]["outcome"], "infra_failure:limit_timeout")
        # A limit hit is never retried.
        self.assertEqual(int((Path(os.environ["FAKE_STATE"]) / "codex.count").read_text()), 2)

    def test_pre_output_failure_retried_exactly_once(self):
        os.environ["FAKE_MODE_CLAUDE"] = "fail_once"
        exp = self.experiment()
        res = exp.run_session(H.Cell("fresh", "claude", "v1_baseline", ["file_selection"]), 0)
        self.assertEqual(res["trials"][0]["outcome"], "valid")
        sessions = self.public_rows("b", "sessions.jsonl")
        self.assertEqual([s["outcome"] for s in sessions], ["retried", "has_valid"])
        self.assertEqual([s["attempt"] for s in sessions], [1, 2])
        trials = self.public_rows("b", "trials.jsonl")
        self.assertEqual(len(trials), 1, "a retry is never an extra sample")

    def test_persistent_failure_is_not_retried_twice(self):
        os.environ["FAKE_MODE_CLAUDE"] = "fail_always"
        res = self.experiment().run_session(H.Cell("fresh", "claude", "v1_baseline", ["file_selection"]), 0)
        self.assertEqual(int((Path(os.environ["FAKE_STATE"]) / "claude.count").read_text()), 2)
        self.assertEqual(res["trials"][0]["outcome"], "infra_failure:launch_error")

    def test_completed_answer_is_never_retried(self):
        os.environ["FAKE_MODE_CLAUDE"] = "no_answer"
        res = self.experiment().run_session(H.Cell("fresh", "claude", "v1_baseline", ["file_selection"]), 0)
        self.assertEqual(res["trials"][0]["outcome"], "subject_noncompliance:no_answer")
        self.assertEqual(int((Path(os.environ["FAKE_STATE"]) / "claude.count").read_text()), 2)

    def test_cost_threshold_lets_in_flight_finish_then_stops(self):
        os.environ["FAKE_MODE_CLAUDE"] = "costly"
        exp = self.experiment(cost=15.0)
        exp.run_session(H.Cell("fresh", "claude", "v1_baseline", ["file_selection"]), 0)
        res = exp.run_session(H.Cell("fresh", "claude", "v2_concise_intent", ["file_selection"]), 1)
        self.assertEqual(res["trials"][0]["outcome"], "not_run:pilot_stopped:claude_cost")
        self.assertEqual(int((Path(os.environ["FAKE_STATE"]) / "claude.count").read_text()), 2)
        snap = exp.budget.snapshot()
        self.assertEqual(snap["claude_cost_usd"], 20.0)  # the in-flight turn finished: overrun recorded

    def test_invocation_ceiling_never_exceeded(self):
        exp = self.experiment(cap=3)
        for i in range(3):
            exp.run_session(H.Cell("fresh", "codex", "v1_baseline", ["file_selection"]), i)
        self.assertEqual(int((Path(os.environ["FAKE_STATE"]) / "codex.count").read_text()), 3)
        self.assertEqual(exp.budget.used, 3)
        outcomes = [t["outcome"] for t in self.public_rows("b", "trials.jsonl")]
        self.assertIn("not_run:pilot_stopped:invocation_cap", outcomes)

    def test_budget_recovery_cannot_reset_the_cap(self):
        j = self.case / "journal.jsonl"
        b = H.Budget(80, 15.0, 2_000_000, journal=j, batch="x")
        for _ in range(80):
            self.assertEqual(b.acquire("subject", "claude"), "")
            b.add_usage("claude", 0.01, None)
        state = self.case / "state.json"
        state.write_text(json.dumps({"invocations": 78, "claude_cost_usd": 0.78, "codex_tokens": 0}))
        b2 = H.Budget(80, 15.0, 2_000_000, journal=j, batch="x")
        b2.recover(j, None, state)
        self.assertEqual(b2.used, 80)
        self.assertEqual(b2.acquire("subject", "claude"), "invocation_cap")

    def test_interrupted_call_is_charged_the_conservative_bound(self):
        j = self.case / "journal2.jsonl"
        b = H.Budget(80, 15.0, 2_000_000, journal=j, batch="x", unreported_claude_usd=2.0,
                     unreported_codex_tokens=200_000)
        b.acquire("subject", "claude")      # launched, never finished
        b.acquire("subject", "codex")
        b.add_usage("codex", None, 1000)
        b.acquire("subject", "codex")       # launched, never finished
        b2 = H.Budget(80, 15.0, 2_000_000, journal=j, batch="x", unreported_claude_usd=2.0,
                      unreported_codex_tokens=200_000)
        b2.recover(j)
        self.assertEqual(b2.used, 3)
        self.assertEqual(b2.claude_cost, 2.0)
        self.assertEqual(b2.codex_tokens, 1000 + 200_000)
        b2.add_usage("claude", None, None)  # finished, but reported nothing
        self.assertEqual(b2.claude_cost, 4.0)

    def test_budget_migration_counts_history_and_pending_together(self):
        pub = self.case / "mig"
        pub.mkdir()
        inv = pub / "invocations.jsonl"
        inv.write_text("".join(json.dumps({"agent": "claude", "usage": {"cost_usd": 0.1}}) + "\n" for _ in range(79)))
        state = pub / "budget_state.json"
        state.write_text(json.dumps({"invocations": 79, "claude_cost_usd": 7.9, "codex_tokens": 0}))
        j = pub / "budget_journal.jsonl"
        b = H.Budget(80, 15.0, 2_000_000, journal=j, batch="m", unreported_claude_usd=2.0)
        b.recover(j, inv, state)
        self.assertEqual(b.used, 79)
        self.assertEqual(b.acquire("subject", "claude"), "")   # seq 80, then interrupted before usage
        b2 = H.Budget(80, 15.0, 2_000_000, journal=j, batch="m", unreported_claude_usd=2.0)
        b2.recover(j, inv, state)
        self.assertEqual(b2.used, 80)
        self.assertEqual(b2.acquire("subject", "codex"), "invocation_cap")
        self.assertAlmostEqual(b2.claude_cost, 7.9 + 2.0)       # history + pending, additively
        events = [json.loads(x)["event"] for x in j.read_text().splitlines()]
        self.assertEqual(events, ["baseline", "reserve"])

    def test_completed_calls_are_not_double_counted(self):
        j = self.case / "dc.jsonl"
        b = H.Budget(80, 15.0, 2_000_000, journal=j, batch="d")
        b.recover(j)
        for _ in range(3):
            b.acquire("subject", "claude")
            b.add_usage("claude", 1.0, None)
        b2 = H.Budget(80, 15.0, 2_000_000, journal=j, batch="d")
        b2.recover(j)
        self.assertEqual((b2.used, b2.claude_cost), (3, 3.0))

    def test_any_threshold_stops_every_launch(self):
        b = H.Budget(80, 1.0, 2_000_000)
        b.acquire("subject", "claude")
        b.add_usage("claude", 1.5, None)
        for agent, purpose in (("codex", "subject"), ("claude", "answer_judge"), ("codex", "control_judge")):
            self.assertEqual(b.acquire(purpose, agent), "claude_cost")
        b = H.Budget(80, 15.0, 100)
        b.acquire("subject", "codex")
        b.add_usage("codex", None, 500)
        self.assertEqual(b.acquire("subject", "claude"), "codex_tokens")

    def test_every_codex_tool_kind_counts_once_toward_the_limit(self):
        seen = set()
        start = json.dumps({"type": "item.started", "item": {"id": "w1", "type": "web_search"}})
        done = json.dumps({"type": "item.completed", "item": {"id": "w1", "type": "web_search"}})
        self.assertEqual(H._count_tool_start("codex", start, seen), 1)
        self.assertEqual(H._count_tool_start("codex", done, seen), 0)   # same item: once
        msg = json.dumps({"type": "item.completed", "item": {"id": "m", "type": "agent_message", "text": "x"}})
        self.assertEqual(H._count_tool_start("codex", msg, seen), 0)
        script = self.case / "websearch.py"
        lines = [json.dumps({"type": "item.started", "item": {"id": f"w{i}", "type": "web_search"}}) for i in range(10)]
        lines += [json.dumps({"type": "item.started", "item": {"id": f"c{i}", "type": "command_execution",
                                                               "command": "ls"}}) for i in range(10)]
        script.write_text("import sys, time\n" + "".join(f"print({l!r}, flush=True)\n" for l in lines)
                          + "time.sleep(30)\n")
        rr = H.run_cli([sys.executable, str(script)], self.case, dict(os.environ), "codex", 20, 15,
                       self.case / "w.out", self.case / "w.err", 1)
        self.assertEqual(rr.killed, "limit_tool_calls")
        self.assertGreater(rr.tool_calls, 15)

    def test_child_that_closes_stdout_is_still_timed_out(self):
        script = self.case / "closer.sh"
        pids = self.case / "closer.pids"
        script.write_text(f"#!/usr/bin/env bash\nexec 1>&-\nsleep 30 &\necho $$ $! > {pids}\nwait\n")
        script.chmod(0o755)
        t0 = time.monotonic()
        rr = H.run_cli([str(script)], self.case, dict(os.environ), "codex", 0.5, None,
                       self.case / "c.out", self.case / "c.err", 1)
        self.assertEqual(rr.killed, "limit_timeout")
        self.assertLess(time.monotonic() - t0, 5)
        self.assertProcessesGone(pids)

    def test_no_busy_wait_after_stdout_eof(self):
        script = self.case / "eof_then_sleep.sh"
        script.write_text("#!/usr/bin/env bash\nexec 1>&-\nsleep 1\n")
        script.chmod(0o755)
        c0 = time.process_time()
        rr = H.run_cli([str(script)], self.case, dict(os.environ), "codex", 10, None,
                       self.case / "b.out", self.case / "b.err", 1)
        self.assertEqual(rr.killed, "")
        self.assertLess(time.process_time() - c0, 0.3, "harness CPU while waiting for the child")

    def test_leftover_children_are_killed_after_the_leader_exits(self):
        script = self.case / "forker.sh"
        pids = self.case / "forker.pids"
        script.write_text(f"#!/usr/bin/env bash\nsleep 30 >/dev/null 2>&1 &\necho $! > {pids}\necho done\n")
        script.chmod(0o755)
        rr = H.run_cli([str(script)], self.case, dict(os.environ), "codex", 10, None,
                       self.case / "f.out", self.case / "f.err", 1)
        self.assertEqual(rr.killed, "")
        self.assertProcessesGone(pids)

    def test_reclassify_reproduces_recorded_outcomes(self):
        exp = self.experiment("rc")
        exp.run_session(H.Cell("fresh", "claude", "v1_baseline", ["file_selection"]), 0)
        exp.run_session(H.Cell("fresh", "codex", "v3_explicit_semantics", ["file_selection"]), 1)
        rows = H.reclassify_batch("rc", self.store)
        self.assertEqual([r["reclassified"] for r in rows], ["valid", "valid"])
        self.assertFalse(any(r["changed"] for r in rows))

    def test_circuit_breaker_opens_after_three(self):
        os.environ["FAKE_MODE_CODEX"] = "no_capture"
        exp = self.experiment()
        for i in range(4):
            exp.run_session(H.Cell("fresh", "codex", "v1_baseline", ["file_selection"], rep=i + 1), i)
        outcomes = [t["outcome"] for t in self.public_rows("b", "trials.jsonl")]
        self.assertEqual(outcomes.count("subject_noncompliance:no_fresh_capture"), 3)
        self.assertEqual(outcomes[-1], "not_run:circuit_open")

    def test_repeated_condition_records(self):
        exp = self.experiment()
        res = exp.run_session(H.Cell("repeated", "codex", "v1_baseline", list(H.LATIN["BCA"]), order="BCA"), 0)
        self.assertEqual([t["outcome"] for t in res["trials"]], ["valid"] * 3)
        rows = self.public_rows("b", "trials.jsonl")
        self.assertEqual([r["turn_index"] for r in rows], [2, 3, 4])
        self.assertEqual([r["position"] for r in rows], [1, 2, 3])
        self.assertEqual([r["scenario"] for r in rows], list(H.LATIN["BCA"]))


# ---------------------------------------------------------------- judging, plan, matrix
class TestJudgingAndPlan(Base):
    def test_blinding_strips_agent_labels(self):
        text, n = J.blind("As Claude Code (claude-opus-5-5) I think; Codex/gpt-6.1-sol differs. OpenAI too.")
        for word in ("Claude", "claude-opus", "Codex", "gpt-6", "OpenAI"):
            self.assertNotIn(word, text)
        self.assertGreaterEqual(n, 4)

    def _answers(self, exp, n=2):
        answers = []
        for i in range(n):
            p = Path("runs") / exp.batch / f"r{i}" / "turn2.final.txt"
            exp.private.write_text(p, f"answer {i} from Claude about the decision")
            answers.append({"trial_id": f"t{i}", "scenario": "file_selection", "agent": "claude",
                            "variant": "v1_baseline", "condition": "fresh", "answer_path": str(p)})
        return answers

    def test_controls_judged_first_and_calibrated(self):
        exp = self.experiment("j", reserve=12)
        exp.control_scenarios = ["file_selection"]
        res = J.judge_batch(exp, self._answers(exp))
        self.assertTrue(res["calibration"]["file_selection|claude"])
        self.assertTrue(res["calibration"]["file_selection|codex"])
        rows = self.public_rows("j", "scores.jsonl")
        firsts = [r for r in rows if r.get("outcome") == "ok"][:4]
        self.assertTrue(all(r["control"] for r in firsts))
        self.assertTrue(all("claude" not in json.dumps(r["scores"]).lower() for r in rows if "scores" in r))

    def test_judge_prompt_carries_the_task_file_under_its_sandbox_path(self):
        ctx = J.task_context(self.store, "file_selection")
        self.assertIn("--- aitasks/t60/t60_2_synthetic.md ---", ctx)
        self.assertNotIn("_aitasks", ctx)
        p = J.build_prompt("b1", "ans", "ref", "scr", ctx)
        self.assertIn("Synthetic task body.", p)
        self.assertNotIn("{task}", p)

    def test_uncalibrated_judge_detected(self):
        a = {"composite": 5.0}
        b = {"composite": 4.0}
        self.assertFalse(J.calibrated(a, b))
        self.assertTrue(J.calibrated(b, a))
        self.assertFalse(J.calibrated(None, a))

    def test_parse_failure_is_reasked_once(self):
        os.environ["FAKE_MODE_CLAUDE"] = "judge_bad_json"
        exp = self.experiment("pj")
        s = J.judge_one(exp, "claude", "answer_judge", "a1", "prompt", "file_selection")
        self.assertIsNone(s)
        self.assertEqual(int((Path(os.environ["FAKE_STATE"]) / "claude.count").read_text()), 2)

    def test_out_of_range_option_scores_are_rejected_and_reasked(self):
        base = {"factual_correctness": 3, "decision_explained": 3, "recommendation_reasoning": 3,
                "unsupported_claims": 3, "readability": 3, "advisory_only": True, "could_choose": 3,
                "failure_flag": False}
        ok = {**base, "options": [{"option": "1", "what_it_does": 3, "benefit": 2, "cost": 0}]}
        self.assertTrue(J.valid_judgment(ok))
        for bad in (999, -10, float("nan"), float("inf")):
            obj = {**base, "options": [{"option": "1", "what_it_does": bad, "benefit": 2, "cost": 2}]}
            self.assertFalse(J.valid_judgment(obj), bad)
        os.environ["FAKE_MODE_CLAUDE"] = "judge_out_of_range"
        exp = self.experiment("oor")
        self.assertIsNone(J.judge_one(exp, "claude", "answer_judge", "a1", "prompt", "file_selection"))
        self.assertEqual(int((Path(os.environ["FAKE_STATE"]) / "claude.count").read_text()), 2)

    def test_cap_drops_answer_judgments_before_controls(self):
        exp = self.experiment("cap", cap=4, reserve=4)
        exp.control_scenarios = ["file_selection"]
        res = J.judge_batch(exp, self._answers(exp, 1))
        self.assertTrue(res["calibration"]["file_selection|claude"])
        rows = self.public_rows("cap", "scores.jsonl")
        self.assertTrue(any(r.get("outcome") == "not_run:pilot_stopped:invocation_cap" and not r.get("control")
                            for r in rows))
        self.assertEqual(exp.budget.used, 4)

    def test_plan_pilot_totals(self):
        p = H.plan_pilot()
        by = {i["item"]: i["invocations"] for i in p["items"]}
        self.assertEqual(by, {"stub_preflight": 0, "startup_smoke": 2, "fresh_sessions": 16,
                              "repeated_sessions": 8, "minimal_sessions": 4, "answer_judging": 32,
                              "calibration_controls": 12})
        self.assertEqual(p["planned_total"], 74)
        self.assertEqual(p["headroom"], 6)
        self.assertEqual(p["sessions"], 12)
        self.assertEqual(p["answers"], 16)

    def test_matrix_expansion_and_seed_stable_order(self):
        mx = json.loads((SQ / "matrix.json").read_text())
        cells = H.expand_matrix(mx)
        a = [c.cell_id for c in H.seeded_order(cells, 7)]
        b = [c.cell_id for c in H.seeded_order(cells, 7)]
        self.assertEqual(a, b)
        self.assertNotEqual(a, [c.cell_id for c in H.seeded_order(cells, 8)])
        rep = [c for c in cells if c.condition == "repeated"]
        for agent in ("claude", "codex"):
            for v in {c.variant for c in rep}:
                orders = [c.scenarios for c in rep if c.agent == agent and c.variant == v]
                for pos in range(3):
                    self.assertEqual(sorted(o[pos] for o in orders), sorted(H.AUQ_SCENARIOS))

    def test_latin_squares_balanced(self):
        for pos in range(3):
            self.assertEqual(sorted(H.LATIN[o][pos] for o in H.LATIN), sorted(H.AUQ_SCENARIOS))


if __name__ == "__main__":
    unittest.main(verbosity=1)
