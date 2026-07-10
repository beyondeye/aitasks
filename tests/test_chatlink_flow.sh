#!/usr/bin/env bash
# test_chatlink_flow.sh — end-to-end bug-report flow tests (t1120_6).
#
# Covers the t1120_6 verification contract against MockChatAdapter +
# FakeLauncher (no live platform, no docker):
#   - payload_guard: fail-closed validation (allowlists, sizes, extra keys,
#     control-char detect-and-reject incl. bidi controls)
#   - task_create: spy-script argv/stdin/Finalized parsing + a REAL
#     aitask_create.sh --batch --commit integration run in a fixture repo
#     (offline: local-only aitask-ids counter; push failure non-fatal)
#   - env passthrough: config names → SandboxSpec.env_allowlist (+ negative
#     control: unlisted gateway env never leaks)
#   - flow pump + handlers: question posting, dedup, supersession no-ops,
#     completion sink (done/✅/summary/handle-kill/dir-removal), fail-closed
#     rejection (❌ + audit + nothing created), completion-vs-death routing
#     in both orders, multi-session custom_id routing, pagination re-render,
#     free-text modal round-trip, reactions vocabulary per transition
#   - run_daemon e2e round trip + crash-restart-reconcile over the same store
# Run: bash tests/test_chatlink_flow.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))

from chat import (
    Actor, ActorType, ConversationKind, ConversationRef, IdentityClaims,
    Interaction, InteractionType, MockChatAdapter, User,
)
from chat.model import MessageRef
import chatlink.daemon as daemon_mod
import chatlink.flow as flow_mod
from chatlink.config import ChatlinkConfig, load_config
from chatlink.daemon import ActionExecutor, _handle_agent_death, run_daemon
from chatlink.intake import (
    GatewayPipeline, STATUS_AWAITING, STATUS_CREATED, STATUS_FAILED,
    STATUS_WORKING,
)
from chatlink.payload_guard import PayloadRejected, validate_payload
from chatlink.relay import (
    Answer, Question, SessionDir, TaskPayload, assign_option_values,
    build_custom_id,
)
from chatlink.render import RenderRejected
from chatlink.sessions_store import SessionsStore
from chatlink.spawn_seam import FakeLauncher
from chatlink.task_create import (
    CreatedTask, TaskCreateError, build_description, create_task_from_payload,
)

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")


class AuditSpy:
    def __init__(self):
        self.lines = []
    def _rec(self, level, msg, *args):
        self.lines.append((level, (msg % args) if args else msg))
    def info(self, msg, *a): self._rec("info", msg, *a)
    def warning(self, msg, *a): self._rec("warning", msg, *a)
    def error(self, msg, *a): self._rec("error", msg, *a)
    def has(self, level, needle):
        return any(lv == level and needle in m for lv, m in self.lines)


def _git(path, *args):
    subprocess.run(["git", "-C", str(path), "-c", "user.email=t@t",
                    "-c", "user.name=t", *args],
                   check=True, capture_output=True)


def mk_fixture_repo(path):
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    (path / "code.txt").write_text("committed\n")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "base")
    return path


def mk_metadata(dirpath, *, task_types=("bug", "feature"),
                labels=("ui", "backend")):
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "task_types.txt").write_text("\n".join(task_types) + "\n")
    (dirpath / "labels.txt").write_text("\n".join(labels) + "\n")
    return dirpath


def mk_spy_script(dirpath, *, rc=0, out=None):
    """A create-script spy: records argv + stdin, prints a Finalized line."""
    dirpath.mkdir(parents=True, exist_ok=True)
    script = dirpath / "create_spy.sh"
    output = out if out is not None else \
        r"Finalized: aitasks/t99_spy_task.md (ID: t99)"
    script.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$@\" > '{dirpath}/argv.txt'\n"
        f"cat > '{dirpath}/stdin.txt'\n"
        f"echo run >> '{dirpath}/count.txt'\n"
        f"echo '{output}'\n"
        f"exit {rc}\n")
    script.chmod(0o755)
    return script


def spy_invocations(dirpath):
    try:
        return len((dirpath / "count.txt").read_text().splitlines())
    except OSError:
        return 0


def payload_dict(sid, **over):
    d = {"session_id": sid, "name": "spy_task", "title": "Crash on save",
         "priority": "high", "effort": "low", "issue_type": "bug",
         "labels": ["ui"], "description": "It crashes.\nSteps: save."}
    d.update(over)
    return d


def make_question(sid, seq=1, *, options=("A", "B"), allow_free_text=False):
    opts = assign_option_values([(o, "") for o in options]) if options else []
    return Question(id=f"q-{sid}-{seq}", seq=seq, session_id=sid,
                    text=f"Question {seq}?", options=opts,
                    allow_free_text=allow_free_text)


def select_interaction(sid, seq, value, actor, conversation, iid="i1"):
    return Interaction(
        id=iid, type=InteractionType.SELECT, actor=actor,
        conversation=conversation,
        custom_id=build_custom_id(sid, seq, "select"),
        values={"values": [value]},
    )


async def reactions_of(adapter, ref_dict):
    msg_ref = MessageRef(
        conversation=ConversationRef.from_dict(ref_dict["conversation"]),
        message_id=ref_dict["message_id"])
    return sorted(r.emoji for r in await adapter.fetch_reactions(msg_ref))


async def thread_texts(adapter, thread_dict):
    msgs = await adapter.fetch_history(ConversationRef.from_dict(thread_dict))
    return [m.text for m in msgs]


async def wait_until(cond, timeout=8.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if cond():
            return True
        await asyncio.sleep(0.02)
    return False


class Env:
    """Mock platform + store + pipeline + executor (flow-ready)."""

    def __init__(self, tmp, *, launcher=None, repo_root=None, environ=None,
                 env_passthrough=(), create_script=None, push_argv=("true",)):
        self.adapter = MockChatAdapter(native_ephemeral=True)
        self.tmp = Path(tmp)
        self.relay_root = self.tmp / "relay"
        self.store = SessionsStore(self.tmp / "sessions")
        self.audit = AuditSpy()
        self.launcher = launcher if launcher is not None else FakeLauncher()
        self.repo_root = repo_root
        self.environ = environ
        self.env_passthrough = list(env_passthrough)
        self.create_script = create_script
        self.push_argv = push_argv

    async def start(self, *, allowed=("U1", "U3")):
        self.chan = await self.adapter.create_conversation(
            ConversationKind.CHANNEL, name="bugs")
        self.config = ChatlinkConfig(
            intake_channel=self.chan.ref.to_dict(),
            allowed_user_ids=list(allowed),
            deny_message_mode="ephemeral",
            max_concurrent_sandboxes=8,
            sandbox_env_passthrough=self.env_passthrough,
        )
        self.pipeline = GatewayPipeline(
            adapter=self.adapter, config=self.config, store=self.store,
            launcher=self.launcher, relay_root=self.relay_root,
            audit=self.audit, repo_root=self.repo_root,
            environ=self.environ, create_script=self.create_script,
            push_argv=self.push_argv)
        self.executor = ActionExecutor(
            store=self.store, relay_root=self.relay_root,
            pipeline=self.pipeline, audit=self.audit)
        self.queue = asyncio.Queue()

        async def _pump():
            async for ev in self.adapter.subscribe():
                await self.queue.put(ev)

        self.pump_task = asyncio.create_task(_pump())
        await asyncio.sleep(0)
        return self

    def user(self, uid="U1", *, member=True):
        self.adapter.register_user(User(id=uid, display_name=uid))
        actor = Actor(id=uid, type=ActorType.USER, display_name=uid)
        self.adapter.set_identity_claims(
            self.chan.ref, IdentityClaims(user_id=uid, is_channel_member=member))
        return actor

    async def drain(self):
        while True:
            for _ in range(5):
                await asyncio.sleep(0)
            if self.queue.empty():
                await asyncio.sleep(0.02)
                if self.queue.empty():
                    return
            event = await self.queue.get()
            await self.pipeline.handle_event(event)

    async def intake(self, actor, text="it crashes"):
        msg = self.adapter.inject_message(self.chan.ref, text, actor)
        await self.drain()
        return msg

    async def flow(self, ev):
        await flow_mod.handle_flow_event(
            ev, pipeline=self.pipeline, store=self.store,
            relay_root=self.relay_root, executor=self.executor,
            audit=self.audit)

    def record(self, sid):
        return self.store.load(sid)

    def sid(self, idx=0):
        return self.store.list_ids()[idx]


async def main():
    tmp_base = Path(tempfile.mkdtemp(prefix="chatlink-flow-test-"))
    fixture = mk_fixture_repo(tmp_base / "fixture-repo")
    metadata = mk_metadata(fixture / "aitasks" / "metadata")

    # ================= payload_guard =====================================
    ok = validate_payload(payload_dict("s0000001"), metadata)
    check("payload_guard: valid payload → typed TaskPayload",
          isinstance(ok, TaskPayload) and ok.issue_type == "bug")
    for label, mut in [
        ("missing", None),
        ("bad issue_type", payload_dict("s0000001", issue_type="exploit")),
        ("label not allowlisted", payload_dict("s0000001", labels=["evil"])),
        ("oversize description",
         payload_dict("s0000001", description="x" * (64 * 1024 + 1))),
        ("extra keys", {**payload_dict("s0000001"), "assigned_to": "root"}),
        ("control char in title",
         payload_dict("s0000001", title="bad\x07title")),
        ("bidi control in title",
         payload_dict("s0000001", title="bad‮title")),
        ("zero-width in title",
         payload_dict("s0000001", title="bad​title")),
        ("control char in description",
         payload_dict("s0000001", description="bad\x00desc")),
    ]:
        try:
            validate_payload(mut, metadata)
            raise AssertionError(f"FAIL: payload_guard accepted {label}")
        except PayloadRejected:
            pass
    check("payload_guard: rejects all malformed variants fail-closed", True)
    ok2 = validate_payload(
        payload_dict("s0000001", description="line1\nline2\ttabbed"),
        metadata)
    check("payload_guard: \\n and \\t allowed in description",
          "\n" in ok2.description)

    # ================= task_create (spy) =================================
    spy_dir = tmp_base / "spy1"
    spy = mk_spy_script(spy_dir)
    audit1 = AuditSpy()
    vp = TaskPayload.from_dict(payload_dict("s0000001"))
    created = create_task_from_payload(
        vp, repo_root=fixture, initiator_tag="U1", audit=audit1,
        create_script=spy, push_argv=("true",))
    argv = (spy_dir / "argv.txt").read_text().splitlines()
    stdin_doc = (spy_dir / "stdin.txt").read_text()
    check("task_create: parses Finalized line into CreatedTask",
          created == CreatedTask(task_id="t99",
                                 path="aitasks/t99_spy_task.md"))
    check("task_create: exact argv (batch, commit, desc via stdin)",
          argv == ["--batch", "--commit", "--name", "spy_task",
                   "--priority", "high", "--effort", "low", "--type", "bug",
                   "--desc-file", "-", "--labels", "ui"])
    check("task_create: stdin doc = title heading + body + provenance",
          stdin_doc.startswith("## Crash on save\n")
          and "It crashes." in stdin_doc
          and "s0000001" in stdin_doc and "U1" in stdin_doc)
    # failure shapes
    bad_rc = mk_spy_script(tmp_base / "spy_rc", rc=3)
    try:
        create_task_from_payload(vp, repo_root=fixture, initiator_tag="U1",
                                 audit=AuditSpy(), create_script=bad_rc,
                                 push_argv=("true",))
        raise AssertionError("FAIL: nonzero create rc accepted")
    except TaskCreateError:
        pass
    bad_out = mk_spy_script(tmp_base / "spy_out", out="Created nothing")
    try:
        create_task_from_payload(vp, repo_root=fixture, initiator_tag="U1",
                                 audit=AuditSpy(), create_script=bad_out,
                                 push_argv=("true",))
        raise AssertionError("FAIL: unparseable create output accepted")
    except TaskCreateError:
        pass
    check("task_create: nonzero rc / unparseable output → TaskCreateError",
          True)

    # ================= task_create (REAL script, fixture repo) ===========
    audit_real = AuditSpy()
    vp_real = TaskPayload.from_dict(payload_dict(
        "s0000001", name="chatlink_real_created", title="Real create"))
    created_real = create_task_from_payload(
        vp_real, repo_root=fixture, initiator_tag="U1", audit=audit_real,
        create_script=root / ".aitask-scripts" / "aitask_create.sh")
    task_file = fixture / created_real.path
    check("real create: task file exists in fixture repo",
          task_file.exists()
          and "chatlink_real_created" in task_file.name)
    body = task_file.read_text()
    check("real create: frontmatter + description landed",
          "priority: high" in body and "issue_type: bug" in body
          and "## Real create" in body and "It crashes." in body)
    log = subprocess.run(["git", "-C", str(fixture), "log", "--oneline"],
                         capture_output=True, text=True).stdout
    check("real create: commit landed (ait: Add task)",
          "ait: Add task" in log)
    check("real create: push failure (no ait) audited + non-fatal",
          audit_real.has("warning", "push failed"))

    # ================= config: sandbox_env_passthrough ===================
    cfg_file = tmp_base / "cfg.yaml"
    cfg_file.write_text(
        "intake_channel: {provider: mock, workspace_id: W1, "
        "conversation_id: C1}\n"
        "sandbox_env_passthrough: [GOOD_KEY, bad-name, 123, ANOTHER_OK]\n")
    cfg = load_config(cfg_file)
    check("config: env passthrough keeps valid names, drops invalid",
          cfg.sandbox_env_passthrough == ["GOOD_KEY", "ANOTHER_OK"])
    cfg_file.write_text(
        "intake_channel: {provider: mock, workspace_id: W1, "
        "conversation_id: C1}\n"
        "sandbox_env_passthrough: not-a-list\n")
    check("config: non-list env passthrough degrades to []",
          load_config(cfg_file).sandbox_env_passthrough == [])

    # ================= env passthrough → SandboxSpec =====================
    env1 = await Env(
        tmp_base / "e1", repo_root=fixture,
        environ={"FOO_KEY": "secret", "BOT_TOKEN_X": "never"},
        env_passthrough=["FOO_KEY", "MISSING_KEY"]).start()
    u1 = env1.user("U1")
    bug_msg = await env1.intake(u1)
    check("env passthrough: configured+present name reaches the spec",
          env1.launcher.launched[0].env_allowlist == {"FOO_KEY": "secret"})
    check("env passthrough: missing name audited as skipped",
          env1.audit.has("warning", "MISSING_KEY not set"))
    check("env passthrough: unlisted gateway env never leaks (negative)",
          "BOT_TOKEN_X" not in env1.launcher.launched[0].env_allowlist)
    sid1 = env1.sid()
    rec1 = env1.record(sid1)
    check("intake accept → ⏳ status reaction",
          await reactions_of(env1.adapter, rec1.bug_report_message) == ["⏳"])
    check("intake retains the launch handle",
          sid1 in env1.pipeline.handles
          and env1.pipeline.handles[sid1].alive())

    # ================= pump scan + question posting ======================
    session1 = SessionDir(env1.relay_root / sid1)
    q1 = make_question(sid1, 1)
    session1.write_question(q1)
    events = flow_mod.scan_flow_events(env1.store, env1.relay_root)
    check("scan: pending unposted question → question_ready",
          events == [flow_mod.FlowEvent(flow_mod.QUESTION_READY, sid1, seq=1)])
    await env1.flow(events[0])
    rec1 = env1.record(sid1)
    check("question_ready: posted (marker + asking state)",
          "1" in rec1.question_messages and rec1.state == "asking")
    check("question posted → ❓ status reaction",
          await reactions_of(env1.adapter, rec1.bug_report_message) == ["❓"])
    n_msgs = len(await thread_texts(env1.adapter, rec1.thread))
    await env1.flow(events[0])  # duplicate event → no-op re-check
    check("duplicate question_ready → single post (supersession)",
          len(await thread_texts(env1.adapter, rec1.thread)) == n_msgs)
    check("scan: posted question not re-emitted",
          flow_mod.scan_flow_events(env1.store, env1.relay_root) == [])

    # answer via select → back to ⏳
    thread_ref = ConversationRef.from_dict(rec1.thread)
    inter = select_interaction(sid1, 1, q1.options[0].value, u1, thread_ref)
    env1.adapter.inject_interaction(inter)
    await env1.drain()
    check("answer recorded → ⏳ status reaction",
          await reactions_of(env1.adapter, rec1.bug_report_message) == ["⏳"]
          and session1.read_answer(1) is not None)

    # ================= free-text modal round trip ========================
    q2 = make_question(sid1, 2, allow_free_text=True)
    session1.write_question(q2)
    await env1.flow(flow_mod.FlowEvent(flow_mod.QUESTION_READY, sid1, seq=2))
    ft = Interaction(id="ft1", type=InteractionType.BUTTON, actor=u1,
                     conversation=thread_ref,
                     custom_id=build_custom_id(sid1, 2, "freetext"))
    env1.adapter.inject_interaction(ft)
    await env1.drain()
    check("free-text button → modal opened immediately",
          len(env1.adapter.opened_modals) == 1)
    field_id = build_custom_id(sid1, 2, "ftfield")
    ms = Interaction(id="ms1", type=InteractionType.MODAL_SUBMIT, actor=u1,
                     conversation=thread_ref,
                     custom_id=build_custom_id(sid1, 2, "modal"),
                     values={field_id: "here is my free text"})
    env1.adapter.inject_interaction(ms)
    await env1.drain()
    ans2 = session1.read_answer(2)
    check("modal submit → free_text answer in spool",
          ans2 is not None and ans2.free_text == "here is my free text")

    # ================= non-initiator negative control ====================
    q3 = make_question(sid1, 3)
    session1.write_question(q3)
    await env1.flow(flow_mod.FlowEvent(flow_mod.QUESTION_READY, sid1, seq=3))
    u9 = env1.user("U9")
    foreign = select_interaction(sid1, 3, q3.options[0].value, u9,
                                 thread_ref, iid="i9")
    env1.adapter.inject_interaction(foreign)
    await env1.drain()
    check("non-initiator interaction rejected, question stays pending",
          env1.audit.has("info", "denied reason=not_initiator")
          and session1.read_answer(3) is None)
    # answer it so the session can complete cleanly below
    env1.adapter.inject_interaction(
        select_interaction(sid1, 3, q3.options[0].value, u1, thread_ref,
                           iid="i10"))
    await env1.drain()

    # ================= completion (valid payload) ========================
    spy2_dir = tmp_base / "spy2"
    env1.pipeline.create_script = mk_spy_script(spy2_dir)
    session1.write_payload(payload_dict(sid1))
    events = flow_mod.scan_flow_events(env1.store, env1.relay_root)
    check("scan: payload present → payload_ready (supersedes questions)",
          events == [flow_mod.FlowEvent(flow_mod.PAYLOAD_READY, sid1)])
    handle1 = env1.pipeline.handles[sid1]
    await env1.flow(events[0])
    rec1 = env1.record(sid1)
    texts = await thread_texts(env1.adapter, rec1.thread)
    check("completion: state done + summary posted (id + title)",
          rec1.state == "done"
          and any("t99" in t and "Crash on save" in t for t in texts))
    check("completion: ✅ status reaction",
          await reactions_of(env1.adapter, rec1.bug_report_message) == ["✅"])
    check("completion: create spy invoked once",
          spy_invocations(spy2_dir) == 1)
    check("completion: handle killed + popped",
          not handle1.alive() and sid1 not in env1.pipeline.handles)
    check("completion: relay dir removed",
          not (env1.relay_root / sid1).exists())
    # death signal arriving AFTER completion → supersession no-op
    await _handle_agent_death(sid1, store=env1.store,
                              relay_root=env1.relay_root,
                              pipeline=env1.pipeline, executor=env1.executor,
                              audit=env1.audit)
    check("death after completion → no-op (state stays done)",
          env1.record(sid1).state == "done")
    # flow event after terminal → no-op
    await env1.flow(flow_mod.FlowEvent(flow_mod.PAYLOAD_READY, sid1))
    check("flow event after terminal state → no-op",
          env1.record(sid1).state == "done")

    # ================= completion (invalid payload, fail-closed) =========
    env2 = await Env(tmp_base / "e2", repo_root=fixture).start()
    spy3_dir = tmp_base / "spy3"
    env2.pipeline.create_script = mk_spy_script(spy3_dir)
    u2 = env2.user("U1")
    await env2.intake(u2)
    sid2 = env2.sid()
    session2 = SessionDir(env2.relay_root / sid2)
    session2.write_payload(payload_dict(sid2, issue_type="exploit"))
    await env2.flow(flow_mod.FlowEvent(flow_mod.PAYLOAD_READY, sid2))
    rec2 = env2.record(sid2)
    texts2 = await thread_texts(env2.adapter, rec2.thread)
    check("invalid payload: failed + ❌ + reason in thread",
          rec2.state == "failed"
          and any("failed" in t and "issue_type" in t for t in texts2)
          and await reactions_of(env2.adapter, rec2.bug_report_message)
          == ["❌"])
    check("invalid payload: audited, nothing created (spy never invoked)",
          env2.audit.has("error", "failed: issue_type")
          and spy_invocations(spy3_dir) == 0)
    check("invalid payload: relay dir removed",
          not (env2.relay_root / sid2).exists())

    # ================= death WITH payload → completion routing ===========
    env3 = await Env(tmp_base / "e3", repo_root=fixture).start()
    spy4_dir = tmp_base / "spy4"
    env3.pipeline.create_script = mk_spy_script(spy4_dir)
    u3 = env3.user("U1")
    await env3.intake(u3)
    sid3 = env3.sid()
    SessionDir(env3.relay_root / sid3).write_payload(payload_dict(sid3))
    await _handle_agent_death(sid3, store=env3.store,
                              relay_root=env3.relay_root,
                              pipeline=env3.pipeline, executor=env3.executor,
                              audit=env3.audit)
    check("death with payload present → completion, not failure",
          env3.record(sid3).state == "done"
          and spy_invocations(spy4_dir) == 1)

    # death WITHOUT payload stays fail-closed
    env4 = await Env(tmp_base / "e4", repo_root=fixture).start()
    u4 = env4.user("U1")
    await env4.intake(u4)
    sid4 = env4.sid()
    SessionDir(env4.relay_root / sid4).write_question(make_question(sid4, 1))
    await _handle_agent_death(sid4, store=env4.store,
                              relay_root=env4.relay_root,
                              pipeline=env4.pipeline, executor=env4.executor,
                              audit=env4.audit)
    rec4 = env4.record(sid4)
    check("death without payload → fail-closed (cancelled answer + ❌)",
          rec4.state == "failed"
          and await reactions_of(env4.adapter, rec4.bug_report_message)
          == ["❌"])

    # ================= multi-session custom_id routing ===================
    env5 = await Env(tmp_base / "e5", repo_root=fixture).start()
    ua = env5.user("U1")
    ub = env5.user("U3")
    await env5.intake(ua, text="bug A")
    await env5.intake(ub, text="bug B")
    sa, sb = env5.store.list_ids()
    ra, rb = env5.record(sa), env5.record(sb)
    if ra.initiator_id != "U1":
        sa, sb, ra, rb = sb, sa, rb, ra
    sess_a, sess_b = (SessionDir(env5.relay_root / sa),
                      SessionDir(env5.relay_root / sb))
    qa, qb = make_question(sa, 1), make_question(sb, 1)
    sess_a.write_question(qa)
    sess_b.write_question(qb)
    for ev in flow_mod.scan_flow_events(env5.store, env5.relay_root):
        await env5.flow(ev)
    # answer session B only, by its custom_id — session A untouched
    env5.adapter.inject_interaction(select_interaction(
        sb, 1, qb.options[1].value, ub,
        ConversationRef.from_dict(rb.thread), iid="ib"))
    await env5.drain()
    check("two sessions in flight: answers route by custom_id session_id",
          sess_b.read_answer(1) is not None
          and sess_a.read_answer(1) is None)
    check("no cross-talk: session A still pending, session B answered",
          env5.record(sa).state == "asking"
          and env5.record(sb).state == "working")

    # ================= pagination re-render ==============================
    env6 = await Env(tmp_base / "e6", repo_root=fixture).start()
    u6 = env6.user("U1")
    await env6.intake(u6)
    sid6 = env6.sid()
    q30 = make_question(sid6, 1, options=tuple(f"opt{i}" for i in range(30)))
    SessionDir(env6.relay_root / sid6).write_question(q30)
    await env6.flow(flow_mod.FlowEvent(flow_mod.QUESTION_READY, sid6, seq=1))
    rec6 = env6.record(sid6)
    qmsg_ref = rec6.question_messages["1"]
    msg_ref6 = MessageRef(
        conversation=ConversationRef.from_dict(qmsg_ref["conversation"]),
        message_id=qmsg_ref["message_id"])
    before6 = (await env6.adapter.fetch_message(msg_ref6)) \
        .metadata.get("components")
    nav = Interaction(id="pg", type=InteractionType.BUTTON, actor=u6,
                      conversation=ConversationRef.from_dict(rec6.thread),
                      custom_id=build_custom_id(sid6, 1, "pg1"))
    env6.adapter.inject_interaction(nav)
    await env6.drain()
    after6 = await env6.adapter.fetch_message(msg_ref6)
    check("pagination: page nav re-renders the question message in place",
          after6.edited
          and after6.metadata.get("components") != before6)

    # ================= unrenderable question → cancelled + note ==========
    env7 = await Env(tmp_base / "e7", repo_root=fixture).start()
    u7 = env7.user("U1")
    await env7.intake(u7)
    sid7 = env7.sid()
    sess7 = SessionDir(env7.relay_root / sid7)
    sess7.write_question(make_question(sid7, 1))
    async def _reject(record, question):
        raise RenderRejected("too_weird")
    env7.pipeline.post_question = _reject
    await env7.flow(flow_mod.FlowEvent(flow_mod.QUESTION_READY, sid7, seq=1))
    ans7 = sess7.read_answer(1)
    check("unrenderable question → cancelled answer (agent unblocked)",
          ans7 is not None and ans7.status == "cancelled")

    # ================= pump: bounded queue + fail-safe scan ==============
    env8 = await Env(tmp_base / "e8", repo_root=fixture).start()
    u8a, u8b = env8.user("U1"), env8.user("U3")
    await env8.intake(u8a, text="bug 1")
    await env8.intake(u8b, text="bug 2")
    for sid in env8.store.list_ids():
        SessionDir(env8.relay_root / sid).write_question(
            make_question(sid, 1))
    flow_q8: asyncio.Queue = asyncio.Queue(maxsize=1)
    stop8 = asyncio.Event()
    pump8 = asyncio.create_task(flow_mod.run_flow_pump(
        store=env8.store, relay_root=env8.relay_root, flow_q=flow_q8,
        stop=stop8, audit=env8.audit, interval_s=0.01))
    check("pump: bounded queue overflow → drop + audit (level-triggered)",
          await wait_until(
              lambda: env8.audit.has("warning", "flow queue full"))
          and flow_q8.qsize() == 1)
    # scan exception: audited, pump survives to the next tick
    real_list = env8.store.list_records
    def boom():
        raise RuntimeError("boom")
    env8.store.list_records = boom
    check("pump: scan exception audited, never fatal",
          await wait_until(lambda: env8.audit.has("error", "boom"))
          and not pump8.done())
    env8.store.list_records = real_list
    stop8.set()
    await asyncio.wait_for(pump8, timeout=5)

    # ================= run_daemon full e2e round trip ====================
    tmpd = tmp_base / "daemon-e2e"
    adapter = MockChatAdapter(native_ephemeral=True)
    chan = await adapter.create_conversation(ConversationKind.CHANNEL,
                                             name="bugs")
    store_d = SessionsStore(tmpd / "sessions")
    relay_d = tmpd / "relay"
    launcher_d = FakeLauncher()
    audit_d = AuditSpy()
    spy5_dir = tmp_base / "spy5"
    config_d = ChatlinkConfig(
        intake_channel=chan.ref.to_dict(), allowed_user_ids=["U1"],
        deny_message_mode="ephemeral", max_concurrent_sandboxes=8)
    stop = asyncio.Event()
    daemon_task = asyncio.create_task(run_daemon(
        adapter=adapter, config=config_d, store=store_d, launcher=launcher_d,
        relay_root=relay_d, audit=audit_d, stop=stop, repo_root=fixture,
        create_script=mk_spy_script(spy5_dir), push_argv=("true",),
        flow_scan_interval_s=0.05))
    adapter.register_user(User(id="U1", display_name="U1"))
    actor_d = Actor(id="U1", type=ActorType.USER, display_name="U1")
    adapter.set_identity_claims(
        chan.ref, IdentityClaims(user_id="U1", is_channel_member=True))
    await asyncio.sleep(0.1)  # let reconciliation + subscribe settle
    adapter.inject_message(chan.ref, "daemon e2e bug", actor_d)
    check("daemon e2e: authorized message → spawn",
          await wait_until(lambda: len(launcher_d.launched) == 1))
    sid_d = store_d.list_ids()[0]
    sess_d = SessionDir(relay_d / sid_d)
    # unauthorized user: ignored/denial, no second spawn (negative control)
    adapter.register_user(User(id="U8", display_name="U8"))
    intruder = Actor(id="U8", type=ActorType.USER, display_name="U8")
    adapter.set_identity_claims(
        chan.ref, IdentityClaims(user_id="U8", is_channel_member=True))
    adapter.inject_message(chan.ref, "let me in", intruder)
    await asyncio.sleep(0.2)
    check("daemon e2e: unauthorized message → no spawn (negative control)",
          len(launcher_d.launched) == 1)
    # agent asks; pump posts; user answers
    q_d = make_question(sid_d, 1)
    sess_d.write_question(q_d)
    check("daemon e2e: pump posts the question (marker persisted)",
          await wait_until(
              lambda: "1" in (store_d.load(sid_d).question_messages)))
    rec_d = store_d.load(sid_d)
    adapter.inject_interaction(select_interaction(
        sid_d, 1, q_d.options[0].value, actor_d,
        ConversationRef.from_dict(rec_d.thread), iid="de1"))
    check("daemon e2e: select answer lands in the spool",
          await wait_until(lambda: sess_d.read_answer(1) is not None))
    # agent finishes with a payload; pump completes the session
    sess_d.write_payload(payload_dict(sid_d))
    check("daemon e2e: payload → session done (task created via spy)",
          await wait_until(lambda: store_d.load(sid_d).state == "done")
          and spy_invocations(spy5_dir) == 1)
    rec_d = store_d.load(sid_d)
    check("daemon e2e: ✅ reaction + thread summary",
          await reactions_of(adapter, rec_d.bug_report_message) == ["✅"]
          and any("t99" in t
                  for t in await thread_texts(adapter, rec_d.thread)))
    stop.set()
    adapter.simulate_disconnect()
    await asyncio.wait_for(daemon_task, timeout=5)
    check("daemon e2e: daemon stops cleanly (pump task cancelled)",
          daemon_task.done() and daemon_task.result() == 0)

    # ================= crash-restart-reconcile ===========================
    tmpc = tmp_base / "daemon-crash"
    adapter_c = MockChatAdapter(native_ephemeral=True)
    chan_c = await adapter_c.create_conversation(ConversationKind.CHANNEL,
                                                 name="bugs")
    store_c = SessionsStore(tmpc / "sessions")
    relay_c = tmpc / "relay"
    launcher_c = FakeLauncher()
    config_c = ChatlinkConfig(
        intake_channel=chan_c.ref.to_dict(), allowed_user_ids=["U1"],
        deny_message_mode="ephemeral", max_concurrent_sandboxes=8)
    stop_c = asyncio.Event()
    audit_c1 = AuditSpy()
    task_c = asyncio.create_task(run_daemon(
        adapter=adapter_c, config=config_c, store=store_c,
        launcher=launcher_c, relay_root=relay_c, audit=audit_c1, stop=stop_c,
        repo_root=fixture, flow_scan_interval_s=0.05))
    adapter_c.register_user(User(id="U1", display_name="U1"))
    actor_c = Actor(id="U1", type=ActorType.USER, display_name="U1")
    adapter_c.set_identity_claims(
        chan_c.ref, IdentityClaims(user_id="U1", is_channel_member=True))
    await asyncio.sleep(0.1)
    adapter_c.inject_message(chan_c.ref, "crash-test bug", actor_c)
    assert await wait_until(lambda: len(launcher_c.launched) == 1)
    sid_c = store_c.list_ids()[0]
    sess_c = SessionDir(relay_c / sid_c)
    q_c = make_question(sid_c, 1)
    sess_c.write_question(q_c)
    assert await wait_until(
        lambda: "1" in store_c.load(sid_c).question_messages)
    # CRASH mid-question: kill the daemon task without any cleanup
    task_c.cancel()
    try:
        await task_c
    except asyncio.CancelledError:
        pass
    check("crash: session left mid-question (asking, unanswered)",
          store_c.load(sid_c).state == "asking"
          and sess_c.read_answer(1) is None)
    # RESTART over the same store; the agent is gone (no live sessions)
    stop_c2 = asyncio.Event()
    audit_c2 = AuditSpy()
    launcher_c2 = FakeLauncher(live_session_ids=set())
    task_c2 = asyncio.create_task(run_daemon(
        adapter=adapter_c, config=config_c, store=store_c,
        launcher=launcher_c2, relay_root=relay_c, audit=audit_c2,
        stop=stop_c2, repo_root=fixture, flow_scan_interval_s=0.05))
    check("restart: reap_orphans consulted (reaped)",
          await wait_until(lambda: len(launcher_c2.reap_calls) == 1))
    check("restart: session reconciled fail-closed (failed + ❌)",
          await wait_until(lambda: store_c.load(sid_c).state == "failed"))
    rec_c = store_c.load(sid_c)
    check("restart: cancelled answer written for the pending question",
          not (relay_c / sid_c).exists()
          or (sess_c.read_answer(1) is not None
              and sess_c.read_answer(1).status == "cancelled"))
    check("restart: ❌ reaction on the bug-report message",
          await reactions_of(adapter_c, rec_c.bug_report_message) == ["❌"])
    stop_c2.set()
    adapter_c.simulate_disconnect()
    await asyncio.wait_for(task_c2, timeout=5)

    print(f"\nPASS: {PASS}, FAIL: 0")


asyncio.run(main())
PYEOF

echo
echo "PASS: test_chatlink_flow.sh"
