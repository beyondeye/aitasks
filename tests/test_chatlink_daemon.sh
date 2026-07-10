#!/usr/bin/env bash
# test_chatlink_daemon.sh — gateway daemon core tests (t1120_3).
#
# Part 1 (Python, MockChatAdapter — no live-platform calls): sessions store,
# pure reconcile planners, executor phase discipline (+ failure injection),
# intake pipeline (per-reason denials, ceilings incl. restart survival,
# pinned failure table), the minimal interaction path driven through the
# REAL subscribe path (ordering spy: write_answer → record save → disable),
# disconnect negative controls, startup/reconnect reconciliation, the
# no-Textual import contract, and serve()'s zero-side-effect refuse paths.
# Part 2 (shell): `ait chatlink` dispatcher/launcher routing.
# Run: bash tests/test_chatlink_daemon.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

# ---- Part 1: Python (stdlib + MockChatAdapter only) ------------------------
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))

# A1. No-Textual contract FIRST (before anything else can pull modules in).
import chatlink.daemon as daemon_mod
assert "textual" not in sys.modules, "FAIL: chatlink.daemon must not load textual"
print("ok - import chatlink.daemon does not load textual")

from chat import (
    Actor, ActorType, ChatError, ConversationKind, ConversationRef,
    DeliveryFailed, EventType, IdentityClaims, Interaction, InteractionType,
    MockChatAdapter, User,
)
import chatlink.intake as intake_mod
import chatlink.reconcile as rc
from chatlink.config import ChatlinkConfig
from chatlink.intake import (
    GatewayPipeline, REASON_CEILING_SANDBOXES, REASON_CEILING_USER_RATE,
)
from chatlink.relay import (
    Answer, Question, SessionDir, assign_option_values, build_custom_id,
    create_session_dir,
)
from chatlink.sessions_store import (
    SessionRecord, SessionsStore, conversation_key, message_ref_dict,
)
from chatlink import paths as cl_paths
from chatlink.spawn_seam import FakeLauncher, LaunchError, NullLauncher

#: Tiny committed fixture repo for workspace copies (set in main()) —
#: intake archives HEAD per session; the real checkout would be slow.
FIXTURE_REPO = None

def _mk_fixture_repo(path):
    path.mkdir(parents=True)
    def g(*args):
        subprocess.run(["git", "-C", str(path), "-c", "user.email=t@t",
                        "-c", "user.name=t", *args],
                       check=True, capture_output=True)
    g("init", "-q")
    (path / "code.txt").write_text("committed\n")
    g("add", ".")
    g("commit", "-q", "-m", "base")
    return path

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")


class AuditSpy:
    """Records (level, formatted message) — the daemon's audit contract."""
    def __init__(self):
        self.lines = []
    def _rec(self, level, msg, *args):
        self.lines.append((level, (msg % args) if args else msg))
    def info(self, msg, *a): self._rec("info", msg, *a)
    def warning(self, msg, *a): self._rec("warning", msg, *a)
    def error(self, msg, *a): self._rec("error", msg, *a)
    def has(self, level, needle):
        return any(lv == level and needle in m for lv, m in self.lines)


class FakeClock:
    def __init__(self, t=1000.0): self.t = t
    def __call__(self): return self.t


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


class Env:
    """One test environment: mock platform + store + pipeline."""

    def __init__(self, tmp, *, deny_mode="ignore", max_sandboxes=4,
                 rate_per_hour=10, launcher=None, native_ephemeral=True,
                 dm_enabled=True, repo_root=None, death_signal=None):
        self.repo_root = repo_root
        self.death_signal = death_signal
        self.adapter = MockChatAdapter(native_ephemeral=native_ephemeral,
                                       dm_enabled=dm_enabled)
        self.clock = FakeClock()
        self.tmp = Path(tmp)
        self.relay_root = self.tmp / "relay"
        self.store = SessionsStore(self.tmp / "sessions", clock=self.clock)
        self.audit = AuditSpy()
        self.launcher = launcher if launcher is not None else FakeLauncher()
        self.chan = None
        self.config = None
        self.pipeline = None
        self.deny_mode = deny_mode
        self.max_sandboxes = max_sandboxes
        self.rate = rate_per_hour

    async def start(self):
        self.chan = await self.adapter.create_conversation(
            ConversationKind.CHANNEL, name="bugs")
        self.config = ChatlinkConfig(
            intake_channel=self.chan.ref.to_dict(),
            allowed_user_ids=["U1"],
            deny_message_mode=self.deny_mode,
            max_concurrent_sandboxes=self.max_sandboxes,
            intake_rate_per_user_per_hour=self.rate,
        )
        self.pipeline = GatewayPipeline(
            adapter=self.adapter, config=self.config, store=self.store,
            launcher=self.launcher, relay_root=self.relay_root,
            audit=self.audit, clock=self.clock,
            repo_root=self.repo_root or FIXTURE_REPO,
            death_signal=self.death_signal)
        # Persistent background pump: the subscriber registers when the
        # pump task starts iterating (async generators start lazily — the
        # test_chat_mock.sh prime-in-task pattern); events are buffered in
        # our own queue so a drain timeout never cancels the generator.
        self.queue = asyncio.Queue()

        async def _pump():
            async for ev in self.adapter.subscribe():
                await self.queue.put(ev)

        self.pump_task = asyncio.create_task(_pump())
        await asyncio.sleep(0)
        return self

    def user(self, uid="U1", *, member=True, allowed_claims=True):
        self.adapter.register_user(User(id=uid, display_name=uid))
        actor = Actor(id=uid, type=ActorType.USER, display_name=uid)
        if allowed_claims:
            self.adapter.set_identity_claims(
                self.chan.ref,
                IdentityClaims(user_id=uid, is_channel_member=member))
        return actor

    async def drain(self):
        """REAL event path: feed every queued event through the pipeline,
        strictly sequentially (the daemon's execution shape). Handlers may
        emit further events (thread creation, bot posts) — loop until the
        stream is quiet."""
        while True:
            for _ in range(5):
                await asyncio.sleep(0)  # let the pump task run
            if self.queue.empty():
                await asyncio.sleep(0.02)  # let to_thread work settle
                if self.queue.empty():
                    return
            event = await self.queue.get()
            await self.pipeline.handle_event(event)

    async def intake(self, actor, text="it crashes"):
        msg = self.adapter.inject_message(self.chan.ref, text, actor)
        await self.drain()
        return msg


async def main():
    global FIXTURE_REPO
    tmp_base = Path(tempfile.mkdtemp(prefix="chatlink-daemon-test-"))
    FIXTURE_REPO = _mk_fixture_repo(tmp_base / "fixture-repo")

    # ================= sessions_store ==================================
    t = tmp_base / "store"
    clock = FakeClock(5000.0)
    store = SessionsStore(t / "sessions", clock=clock)
    rec = store.new_record("sabc001", "U1",
                           thread={"provider": "mock", "workspace_id": "W1",
                                   "conversation_id": "C1", "thread_id": "t1",
                                   "metadata": {}})
    check("new_record is spawning + clock-stamped",
          rec.state == "spawning" and rec.created_at == 5000.0)
    store.save(rec)
    loaded = store.load("sabc001")
    check("record round-trips", loaded == rec)
    check("dir is 0700", (t / "sessions").stat().st_mode & 0o777 == 0o700)
    check("record file is 0600",
          store.record_path("sabc001").stat().st_mode & 0o777 == 0o600)

    # tmp files ignored; corrupt records fail closed
    (t / "sessions" / "sxx.json.123.tmp").write_text("{}")
    (t / "sessions" / "sbad001.json").write_text("{not json")
    ids = store.list_ids()
    check("list_ids skips *.tmp, includes corrupt", ids == ["sabc001", "sbad001"])
    records, corrupt = store.list_records()
    check("corrupt record reported, not loaded",
          corrupt == ["sbad001"] and [r.session_id for r in records] == ["sabc001"])
    check("corrupt counts as occupied (fail-closed)",
          store.count_nonterminal() == 2)

    # ceilings derive from persisted records; restart-proof
    clock.t = 5100.0
    check("recent-by-initiator counts inside window",
          store.count_recent_by_initiator("U1", 3600) == 1)
    restarted = SessionsStore(t / "sessions", clock=clock)
    check("rate input survives restart (fresh store instance)",
          restarted.count_recent_by_initiator("U1", 3600) == 1)
    clock.t = 5000.0 + 7200.0
    check("recent-by-initiator expires outside window",
          store.count_recent_by_initiator("U1", 3600) == 0)

    # watch cursors: persisted, not a session id
    store.save_watch_cursor({"provider": "mock", "workspace_id": "W1",
                             "conversation_id": "C1", "thread_id": None,
                             "metadata": {}}, "m42")
    check("watch cursor round-trips",
          list(store.load_watch_cursors().values())[0]["message_id"] == "m42")
    check("watch_cursors.json is not a session id",
          "watch_cursors" not in store.list_ids())

    # outcomes + terminal
    rec.set_outcome(3, {"status": "answered"})
    check("has_outcome after set_outcome", rec.has_outcome(3))
    rec.state = "done"
    check("terminal detection", rec.is_terminal)

    # ================= reconcile planners ===============================
    def mkrec(sid, state, *, qmsgs=None, bug=None):
        return SessionRecord(session_id=sid, initiator_id="U1", state=state,
                             thread={"provider": "mock", "workspace_id": "W1",
                                     "conversation_id": "C1", "thread_id": "t9",
                                     "metadata": {}},
                             bug_report_message=bug,
                             question_messages=qmsgs or {})

    bug_ref = message_ref_dict({"provider": "mock", "workspace_id": "W1",
                                "conversation_id": "C1", "thread_id": None,
                                "metadata": {}}, "m1")
    qmsg = message_ref_dict({"provider": "mock", "workspace_id": "W1",
                             "conversation_id": "C1", "thread_id": "t9",
                             "metadata": {}}, "m2")

    # dead session with a pending question: full fail-closed cascade
    dead = mkrec("sdead01", "asking", qmsgs={"1": qmsg}, bug=bug_ref)
    scans = {"sdead01": rc.SpoolScan("sdead01", pending_seqs=(1,))}
    acts = rc.plan_startup_actions([dead], [], set(), scans)
    kinds = [a.kind for a in acts]
    check("dead session: cancel + disable + fail + react + remove",
          kinds == [rc.WRITE_CANCELLED_ANSWER, rc.DISABLE_COMPONENTS,
                    rc.MARK_FAILED, rc.REACT_FAILED, rc.REMOVE_RELAY_DIR])
    check("phase tags: persistence < platform < removal",
          [a.phase for a in rc.order_for_execution(acts)] == sorted(
              a.phase for a in acts))

    # live session untouched; terminal session only cleaned up
    live = mkrec("slive01", "working")
    term = mkrec("sdone01", "done")
    acts = rc.plan_startup_actions(
        [live, term], [], {"slive01"},
        {"slive01": rc.SpoolScan("slive01"), "sdone01": rc.SpoolScan("sdone01")})
    check("live session gets no actions",
          not [a for a in acts if a.session_id == "slive01"])
    check("terminal session: stale dir removed only",
          [a.kind for a in acts if a.session_id == "sdone01"]
          == [rc.REMOVE_RELAY_DIR])

    # corrupt record: fail-closed tombstone; orphan dir: hygiene + removal
    acts = rc.plan_startup_actions(
        [], ["shalf01"], set(),
        {"shalf01": rc.SpoolScan("shalf01", pending_seqs=(2,)),
         "sorph01": rc.SpoolScan("sorph01", pending_seqs=(1,))})
    half = [a.kind for a in acts if a.session_id == "shalf01"]
    orph = [a.kind for a in acts if a.session_id == "sorph01"]
    check("corrupt record: cancel + mark failed + remove",
          half == [rc.WRITE_CANCELLED_ANSWER, rc.MARK_FAILED,
                   rc.REMOVE_RELAY_DIR])
    check("orphan dir: cancel + remove (no record to fail)",
          orph == [rc.WRITE_CANCELLED_ANSWER, rc.REMOVE_RELAY_DIR])

    # spool-heal: answer present in spool, outcome absent in record
    asking = mkrec("sheal01", "working")
    scans = {"sheal01": rc.SpoolScan(
        "sheal01", answers={1: {"status": "answered", "id": "q", "seq": 1,
                                "values": ["o0"], "free_text": None,
                                "answered_by": "U1"}})}
    acts = rc.plan_startup_actions([asking], [], {"sheal01"}, scans)
    check("spool-heal planned for missing record outcome",
          [a.kind for a in acts] == [rc.HEAL_OUTCOME])

    # mid-life agent death planner (t1120_5): same fail-closed cascade as
    # the startup branch, [] on terminal/absent record (stale-signal no-op)
    dying = mkrec("sdie01", "asking", qmsgs={"1": qmsg}, bug=bug_ref)
    scan_die = rc.SpoolScan("sdie01", pending_seqs=(1,))
    acts = rc.plan_agent_death_actions(dying, scan_die)
    check("agent death: cancel + disable + fail + react + remove",
          [a.kind for a in acts]
          == [rc.WRITE_CANCELLED_ANSWER, rc.DISABLE_COMPONENTS,
              rc.MARK_FAILED, rc.REACT_FAILED, rc.REMOVE_RELAY_DIR])
    check("agent death actions carry the agent_died reason",
          [a for a in acts if a.kind == rc.MARK_FAILED][0]
          .payload["reason"] == rc.FAIL_REASON_AGENT_DIED)
    check("terminal record: death signal is a no-op",
          rc.plan_agent_death_actions(mkrec("sdie02", "done"),
                                      scan_die) == [])
    check("absent record: death signal is a no-op",
          rc.plan_agent_death_actions(None, scan_die) == [])
    healed_die = mkrec("sdie03", "working")
    acts = rc.plan_agent_death_actions(
        healed_die,
        rc.SpoolScan("sdie03", answers={1: {"status": "answered", "id": "q",
                                            "seq": 1, "values": ["o0"],
                                            "free_text": None,
                                            "answered_by": "U1"}}))
    check("agent death heals spool outcomes before failing",
          [a.kind for a in acts][:2] == [rc.HEAL_OUTCOME, rc.MARK_FAILED])

    # reconnect: missed messages recovered, self/bot filtered, re-prompt
    fetched = [
        {"conversation": {"provider": "mock", "workspace_id": "W1",
                          "conversation_id": "C1", "thread_id": None},
         "message_id": "m5", "author_is_self": False, "author_is_bot": False},
        {"conversation": {"provider": "mock", "workspace_id": "W1",
                          "conversation_id": "C1", "thread_id": None},
         "message_id": "m6", "author_is_self": True, "author_is_bot": True},
    ]
    pend = mkrec("spend01", "asking")
    acts = rc.plan_reconnect_actions(
        [pend], fetched, {"spend01": rc.SpoolScan("spend01", pending_seqs=(1,))})
    kinds = [a.kind for a in acts]
    check("reconnect: process human msg, skip self/bot, advance cursor, re-prompt",
          kinds.count(rc.PROCESS_MESSAGE) == 1
          and rc.ADVANCE_CURSOR in kinds and rc.REPOST_QUESTION in kinds)
    # Handle-then-advance PER MESSAGE: m5 is processed before ITS cursor
    # advance; the self/bot m6 advances without processing.
    glb = [a for a in acts if a.kind in (rc.PROCESS_MESSAGE, rc.ADVANCE_CURSOR)]
    check("per-message handle-then-advance ordering",
          [a.kind for a in glb] == [rc.PROCESS_MESSAGE, rc.ADVANCE_CURSOR,
                                    rc.ADVANCE_CURSOR]
          and glb[0].payload["message"]["message_id"] == "m5"
          and glb[1].payload["message_id"] == "m5"
          and glb[2].payload["message_id"] == "m6")

    # ================= intake pipeline (real event path) =================
    def sig_sentinel(session_id):  # the daemon-supplied death signal seam
        pass
    env = await Env(tmp_base / "e1", death_signal=sig_sentinel).start()
    u1 = env.user("U1")
    await env.intake(u1)
    check("authorized intake creates one session",
          len(env.store.list_ids()) == 1)
    sid = env.store.list_ids()[0]
    rec = env.store.load(sid)
    check("record persisted with initiator + thread + spawning",
          rec.initiator_id == "U1" and rec.thread is not None
          and rec.state == "spawning")
    check("relay session dir minted", (env.relay_root / sid).is_dir())
    spec0 = env.launcher.launched[0]
    check("launcher received the spec with clamped limits",
          spec0.session_id == sid
          and spec0.limits["wall_clock_s"] == 1800)
    ws_dir = cl_paths.workspaces_root_beside(env.relay_root) / sid
    check("spec carries the per-session workspace copy (committed HEAD)",
          spec0.workspace_copy_path == str(ws_dir)
          and (ws_dir / "code.txt").read_text() == "committed\n")
    check("spec carries workspace_id + the daemon death signal",
          spec0.workspace_id == env.chan.ref.workspace_id
          and spec0.on_death is sig_sentinel)
    check("env allowlist stays empty until t1120_6 sources the LLM key",
          spec0.env_allowlist == {})
    check("bug report written into the spool before launch",
          (env.relay_root / sid / "bug_report.md").read_text()
          == "it crashes")
    check("intake accepted audited", env.audit.has("info", "intake accepted"))

    # thread really exists on the platform
    thread_ref = ConversationRef.from_dict(rec.thread)
    conv = await env.adapter.fetch_conversation(thread_ref)
    check("thread exists on the platform", conv.kind is ConversationKind.THREAD)

    # self/bot echo dropped silently
    bot = Actor(id="B9", type=ActorType.BOT, display_name="otherbot")
    env.adapter.inject_message(env.chan.ref, "bot noise", bot)
    await env.drain()
    selfa = Actor(id="B0", type=ActorType.BOT, display_name="me", is_self=True)
    env.adapter.inject_message(env.chan.ref, "own echo", selfa)
    await env.drain()
    check("self/bot echoes dropped (no new sessions)",
          len(env.store.list_ids()) == 1)

    # unauthorized: deny + audit; ignore mode posts nothing
    u2 = env.user("U2")
    sends_before = len(env.adapter.ephemeral_messages)
    await env.intake(u2)
    check("unauthorized denied with policy reason",
          env.audit.has("info", "denied reason=user_not_allowed"))
    check("deny_message_mode=ignore posts no ephemeral",
          len(env.adapter.ephemeral_messages) == sends_before)
    check("unauthorized creates nothing", len(env.store.list_ids()) == 1)

    # ephemeral deny mode delivers privately
    env2 = await Env(tmp_base / "e2", deny_mode="ephemeral").start()
    ua = env2.user("U9")  # not in allowlist
    await env2.intake(ua)
    check("ephemeral denial delivered privately",
          len(env2.adapter.ephemeral_messages) == 1)

    # DeliveryFailed: audited, swallowed, never public
    env3 = await Env(tmp_base / "e3", deny_mode="ephemeral",
                     native_ephemeral=False, dm_enabled=False).start()
    ub = env3.user("U9")
    public_posts = []
    real_send = env3.adapter.send_message
    async def spy_send(*a, **kw):
        public_posts.append(a)
        return await real_send(*a, **kw)
    env3.adapter.send_message = spy_send
    await env3.intake(ub)
    check("DeliveryFailed swallowed + audited",
          env3.audit.has("info", "ephemeral delivery failed"))
    check("denial NEVER posted publicly", public_posts == [])

    # ceilings: sandbox bound and same-user rate race (sequential dispatch)
    env4 = await Env(tmp_base / "e4", rate_per_hour=1).start()
    uc = env4.user("U1")
    env4.adapter.inject_message(env4.chan.ref, "bug one", uc)
    env4.adapter.inject_message(env4.chan.ref, "bug two", uc)
    await env4.drain()  # back-to-back at the ceiling boundary
    check("same-user race: exactly one session (serialized check-then-write)",
          len(env4.store.list_ids()) == 1)
    check("second denied with rate-ceiling reason",
          env4.audit.has("info", f"denied reason={REASON_CEILING_USER_RATE}"))

    env5 = await Env(tmp_base / "e5", max_sandboxes=1).start()
    ud = env5.user("U1")
    await env5.intake(ud)
    await env5.intake(ud)
    check("concurrent-sandbox ceiling enforced",
          len(env5.store.list_ids()) == 1
          and env5.audit.has("info", f"denied reason={REASON_CEILING_SANDBOXES}"))

    # ---- intake failure points (pinned step table) ----
    # (a) thread creation fails → nothing persisted
    env6 = await Env(tmp_base / "e6").start()
    ue = env6.user("U1")
    async def boom_thread(*a, **kw):
        raise ChatError("thread refused")
    env6.adapter.create_conversation = boom_thread
    await env6.intake(ue)
    check("thread failure: nothing persisted, audited",
          env6.store.list_ids() == [] and not env6.relay_root.exists()
          and env6.audit.has("error", "step=create_thread"))

    # (c) record persist fails → relay dir cleaned up best-effort
    env7 = await Env(tmp_base / "e7").start()
    uf = env7.user("U1")
    def boom_save(record):
        raise OSError("disk full")
    env7.store.save = boom_save
    await env7.intake(uf)
    check("persist failure: relay dir removed, audited",
          list(env7.relay_root.iterdir()) == []
          and env7.audit.has("error", "step=persist_record"))

    # (d) launch fails → terminal failed persisted BEFORE platform cleanup
    env8 = await Env(tmp_base / "e8",
                     launcher=FakeLauncher(fail_with=LaunchError("no docker"))).start()
    ug = env8.user("U1")
    order = []
    real_save8 = env8.store.save
    def spy_save8(record):
        order.append(("save", record.state))
        real_save8(record)
    env8.store.save = spy_save8
    real_send8 = env8.adapter.send_message
    async def spy_send8(*a, **kw):
        order.append(("platform", None))
        return await real_send8(*a, **kw)
    env8.adapter.send_message = spy_send8
    await env8.intake(ug)
    sid8 = env8.store.list_ids()[0]
    check("launch failure: session persisted failed",
          env8.store.load(sid8).state == "failed")
    check("terminal persistence precedes platform cleanup (spy order)",
          ("save", "failed") in order
          and order.index(("save", "failed")) < order.index(("platform", None)))
    check("NullLauncher refuses honestly",
          isinstance(NullLauncher().reap_orphans("W1"), list))

    # (d) workspace-copy failure shares the launch fail path (t1120_5):
    # record failed BEFORE the thread note, launcher never invoked, no
    # leftover copy dir — a copy failure can never park a non-terminal
    # session until the next startup reconciliation.
    envW = await Env(tmp_base / "eW",
                     repo_root=tmp_base / "not-a-repo").start()
    uW = envW.user("U1")
    orderW = []
    real_saveW = envW.store.save
    def spy_saveW(record):
        orderW.append(("save", record.state))
        real_saveW(record)
    envW.store.save = spy_saveW
    real_sendW = envW.adapter.send_message
    async def spy_sendW(*a, **kw):
        orderW.append(("platform", None))
        return await real_sendW(*a, **kw)
    envW.adapter.send_message = spy_sendW
    await envW.intake(uW)
    sidW = envW.store.list_ids()[0]
    check("copy failure: session persisted failed",
          envW.store.load(sidW).state == "failed")
    check("copy failure: launcher never invoked (spy)",
          envW.launcher.launched == [])
    check("copy failure: no leftover workspace copy dir",
          not (cl_paths.workspaces_root_beside(envW.relay_root)
               / sidW).exists())
    check("copy failure: terminal persistence precedes the thread note",
          ("save", "failed") in orderW
          and orderW.index(("save", "failed"))
          < orderW.index(("platform", None)))
    check("copy failure audited as step=launch",
          envW.audit.has("error", "step=launch"))

    # ================= minimal interaction path ==========================
    env9 = await Env(tmp_base / "e9").start()
    uh = env9.user("U1")
    await env9.intake(uh)
    sid9 = env9.store.list_ids()[0]
    rec9 = env9.store.load(sid9)
    session9 = SessionDir(env9.relay_root / sid9)
    q = make_question(sid9, 1)
    session9.write_question(q)
    await env9.pipeline.post_question(rec9, q)
    rec9 = env9.store.load(sid9)
    check("post_question records the question message ref + asking state",
          "1" in rec9.question_messages and rec9.state == "asking")

    # ordering spy: write_answer FIRST, then record save, then disable
    order9 = []
    real_write = SessionDir.write_answer
    def spy_write(self, a, **kw):
        order9.append("write_answer")
        return real_write(self, a, **kw)
    SessionDir.write_answer = spy_write
    intake_mod.SessionDir.write_answer = spy_write
    real_save9 = env9.store.save
    def spy_save9(record):
        order9.append("record_save")
        real_save9(record)
    env9.store.save = spy_save9
    real_edit9 = env9.adapter.edit_message
    async def spy_edit9(*a, **kw):
        order9.append("disable")
        return await real_edit9(*a, **kw)
    env9.adapter.edit_message = spy_edit9

    value = q.options[0].value
    inter = select_interaction(sid9, 1, value, uh,
                               ConversationRef.from_dict(rec9.thread))
    env9.adapter.inject_interaction(inter)
    await env9.drain()  # REAL path: subscribe → handler
    SessionDir.write_answer = real_write

    ans = session9.read_answer(1)
    check("select answer published to spool with option value",
          ans is not None and ans.values == [value]
          and ans.answered_by == "U1")
    rec9 = env9.store.load(sid9)
    check("record outcome mirrored + state working",
          rec9.has_outcome(1) and rec9.state == "working")
    check("ordering: write_answer → record save → disable",
          order9 == ["write_answer", "record_save", "disable"])

    # repeat interaction: stale (write returns False), record untouched
    before = json.dumps(env9.store.load(sid9).to_dict(), sort_keys=True)
    stale = select_interaction(sid9, 1, value, uh,
                               ConversationRef.from_dict(rec9.thread), iid="i2")
    env9.adapter.inject_interaction(stale)
    await env9.drain()
    check("repeat interaction → stale, ephemeral 'expired', record untouched",
          env9.audit.has("info", "repeat interaction")
          and json.dumps(env9.store.load(sid9).to_dict(), sort_keys=True) == before
          and any("expired" in m.text for m in env9.adapter.ephemeral_messages))

    # non-initiator answer attempt: denied, question stays pending
    q2 = make_question(sid9, 2)
    session9.write_question(q2)
    rec9 = env9.store.load(sid9)
    await env9.pipeline.post_question(rec9, q2)
    u2h = env9.user("U2")
    foreign = select_interaction(sid9, 2, q2.options[0].value, u2h,
                                 ConversationRef.from_dict(rec9.thread), iid="i3")
    env9.adapter.inject_interaction(foreign)
    await env9.drain()
    check("non-initiator denied (fail-closed), question stays pending",
          env9.audit.has("info", "denied reason=not_initiator")
          and session9.read_answer(2) is None)

    # free-text trigger → open_modal immediately (contract 5; t1120_6);
    # page nav for a question with no stored message ref → 'expired'
    # ephemeral, never a crash (full pagination e2e: test_chatlink_flow.sh)
    q3 = make_question(sid9, 3, allow_free_text=True)
    session9.write_question(q3)
    ft = Interaction(id="i4", type=InteractionType.BUTTON, actor=uh,
                     conversation=ConversationRef.from_dict(rec9.thread),
                     custom_id=build_custom_id(sid9, 3, "freetext"))
    env9.adapter.inject_interaction(ft)
    await env9.drain()
    check("free-text trigger → modal opened, no answer written",
          len(env9.adapter.opened_modals) == 1
          and session9.read_answer(3) is None)
    pg = Interaction(id="i5", type=InteractionType.BUTTON, actor=uh,
                     conversation=ConversationRef.from_dict(rec9.thread),
                     custom_id=build_custom_id(sid9, 3, "pg1"))
    env9.adapter.inject_interaction(pg)
    await env9.drain()
    check("page nav without posted message ref → expired, no crash",
          session9.read_answer(3) is None
          and any("expired" in m.text for m in env9.adapter.ephemeral_messages))

    # unknown custom_id / unknown session / absent question
    junk = Interaction(id="i6", type=InteractionType.BUTTON, actor=uh,
                       conversation=env9.chan.ref, custom_id="not:ours")
    env9.adapter.inject_interaction(junk)
    await env9.drain()
    check("unknown custom_id ignored + audited",
          env9.audit.has("info", "unknown custom_id"))
    ghost = select_interaction("sghost1", 1, "o0", uh, env9.chan.ref, iid="i7")
    env9.adapter.inject_interaction(ghost)
    await env9.drain()
    check("unknown session ignored + audited",
          env9.audit.has("info", "unknown session"))
    absent = select_interaction(sid9, 9, "o0", uh,
                                ConversationRef.from_dict(rec9.thread), iid="i8")
    env9.adapter.inject_interaction(absent)
    await env9.drain()
    check("interaction for absent question → 'expired'",
          env9.audit.has("info", "absent question"))

    # ================= executor (phase discipline + failure injection) ====
    envA = await Env(tmp_base / "eA").start()
    uA = envA.user("U1")
    await envA.intake(uA)
    sidA = envA.store.list_ids()[0]
    sessA = SessionDir(envA.relay_root / sidA)
    qA = make_question(sidA, 1)
    sessA.write_question(qA)
    recA = envA.store.load(sidA)
    await envA.pipeline.post_question(recA, qA)

    # phase order spy on a fresh executor pass (agent died: launcher reports
    # nothing live)
    orderA = []
    real_saveA = envA.store.save
    def spy_saveA(record):
        orderA.append(("p1", record.state))
        real_saveA(record)
    envA.store.save = spy_saveA
    real_editA = envA.adapter.edit_message
    async def spy_editA(*a, **kw):
        orderA.append(("p2", "edit"))
        return await real_editA(*a, **kw)
    envA.adapter.edit_message = spy_editA
    import chatlink.daemon as dm
    real_rm = dm.ActionExecutor._remove_relay_dir
    def spy_rm(self, sid):
        orderA.append(("p3", sid))
        real_rm(self, sid)
    dm.ActionExecutor._remove_relay_dir = spy_rm

    await dm.run_startup_reconciliation(
        store=envA.store, relay_root=envA.relay_root,
        launcher=FakeLauncher(), workspace_id="W1",
        pipeline=envA.pipeline, audit=envA.audit)
    dm.ActionExecutor._remove_relay_dir = real_rm

    check("startup: dead session failed, cancelled answer, dir removed",
          envA.store.load(sidA).state == "failed"
          and not (envA.relay_root / sidA).exists())
    check("workspace copy removed alongside the relay dir (phase 3)",
          not (cl_paths.workspaces_root_beside(envA.relay_root)
               / sidA).exists())
    phases = [p for p, _ in orderA]
    check("executor phase order: all p1 before p2 before p3",
          phases == sorted(phases))
    # cancelled answer was durably written before removal (spool hygiene)
    check("cancelled answer audited",
          envA.audit.has("info", "cancelled answer written"))

    # idempotent re-run: clean no-op
    lines_before = len(envA.audit.lines)
    await dm.run_startup_reconciliation(
        store=envA.store, relay_root=envA.relay_root,
        launcher=FakeLauncher(), workspace_id="W1",
        pipeline=envA.pipeline, audit=envA.audit)
    check("re-run after completion is a no-op (no new failure lines)",
          not any(lv == "error" for lv, _ in envA.audit.lines[lines_before:]))

    # failure injection: phase-1 write fails → dir kept, no platform calls
    envB = await Env(tmp_base / "eB").start()
    uB = envB.user("U1")
    await envB.intake(uB)
    sidB = envB.store.list_ids()[0]
    platform_calls = []
    real_editB = envB.adapter.edit_message
    async def spy_editB(*a, **kw):
        platform_calls.append("edit")
        return await real_editB(*a, **kw)
    envB.adapter.edit_message = spy_editB
    real_reactB = envB.adapter.add_reaction
    async def spy_reactB(*a, **kw):
        platform_calls.append("react")
        return await real_reactB(*a, **kw)
    envB.adapter.add_reaction = spy_reactB
    def boom_saveB(record):
        raise OSError("read-only fs")
    envB.store.save = boom_saveB
    await dm.run_startup_reconciliation(
        store=envB.store, relay_root=envB.relay_root,
        launcher=FakeLauncher(), workspace_id="W1",
        pipeline=envB.pipeline, audit=envB.audit)
    check("phase-1 failure: relay dir NOT removed",
          (envB.relay_root / sidB).is_dir())
    check("phase-1 failure: platform cleanup skipped", platform_calls == [])
    check("phase-1 failure audited",
          envB.audit.has("error", "phase1")
          and envB.audit.has("warning", "keeping relay dir"))
    # recovery: restore the store, re-run → converges
    envB.store.save = SessionsStore(envB.tmp / "sessions",
                                    clock=envB.clock).save
    await dm.run_startup_reconciliation(
        store=envB.store, relay_root=envB.relay_root,
        launcher=FakeLauncher(), workspace_id="W1",
        pipeline=envB.pipeline, audit=envB.audit)
    check("after recovery the executor converges (failed + dir removed)",
          envB.store.load(sidB).state == "failed"
          and not (envB.relay_root / sidB).exists())

    # corrupt record resolved fail-closed via tombstone
    envC = await Env(tmp_base / "eC").start()
    (envC.tmp / "sessions").mkdir(parents=True)
    (envC.tmp / "sessions" / "shalf99.json").write_text("{broken")
    await dm.run_startup_reconciliation(
        store=envC.store, relay_root=envC.relay_root,
        launcher=FakeLauncher(), workspace_id="W1",
        pipeline=envC.pipeline, audit=envC.audit)
    tomb = envC.store.load("shalf99")
    check("half-created session resolved to failed tombstone (never resumed)",
          tomb is not None and tomb.state == "failed")

    # spool-heal executes: record outcome healed FROM the spool
    envD = await Env(tmp_base / "eD").start()
    uD = envD.user("U1")
    await envD.intake(uD)
    sidD = envD.store.list_ids()[0]
    sessD = SessionDir(envD.relay_root / sidD)
    qD = make_question(sidD, 1)
    sessD.write_question(qD)
    ansD = Answer(id=qD.id, seq=1, status="answered",
                  values=[qD.options[0].value], answered_by="U1")
    sessD.write_answer(ansD)
    recD = envD.store.load(sidD)
    check("pre-heal: no record outcome", not recD.has_outcome(1))
    await dm.run_startup_reconciliation(
        store=envD.store, relay_root=envD.relay_root,
        launcher=FakeLauncher(live_session_ids={sidD}), workspace_id="W1",
        pipeline=envD.pipeline, audit=envD.audit)
    check("spool-heal: record outcome healed from answer file",
          envD.store.load(sidD).has_outcome(1))

    # ================= disconnect negative controls =======================
    envE = await Env(tmp_base / "eE").start()
    uE = envE.user("U1")
    msg1 = envE.adapter.inject_message(envE.chan.ref, "first bug", uE)
    await envE.drain()
    envE.store.save_watch_cursor(msg1.ref.conversation.to_dict(),
                                 msg1.ref.message_id)
    sidE = envE.store.list_ids()[0]
    # pending question posted before the drop
    sessE = SessionDir(envE.relay_root / sidE)
    qE = make_question(sidE, 1)
    sessE.write_question(qE)
    recE = envE.store.load(sidE)
    await envE.pipeline.post_question(recE, qE)

    envE.adapter.simulate_disconnect()
    await asyncio.wait_for(envE.pump_task, 0.5)
    check("simulate_disconnect ends the subscribe stream",
          envE.pump_task.done())

    # a message lands while disconnected — recover via history diff
    envE.adapter.inject_message(envE.chan.ref, "missed bug", uE)
    posts_before = len(envE.adapter.ephemeral_messages)
    sessions_before = len(envE.store.list_ids())
    await dm.run_reconnect_reconciliation(
        store=envE.store, relay_root=envE.relay_root,
        intake_ref=envE.chan.ref, pipeline=envE.pipeline, audit=envE.audit)
    check("missed message recovered via history diff (new session)",
          len(envE.store.list_ids()) == sessions_before + 1)
    # the pending question was re-prompted (no replay assumed)
    thread_msgs = await envE.adapter.fetch_history(
        ConversationRef.from_dict(recE.thread), limit=100)
    reposts = [m for m in thread_msgs if qE.text in m.text]
    check("missed interaction window → question re-posted (never replayed)",
          len(reposts) >= 2)

    # cursor-loss negative control: a recovery failure that ESCAPES the
    # handler stops the global chain — the cursor is NOT advanced past the
    # unhandled message (next reconnect re-fetches; never silently skipped)
    envG = await Env(tmp_base / "eG").start()
    uG = envG.user("U1")
    msgG = envG.adapter.inject_message(envG.chan.ref, "will be missed", uG)
    await envG.drain()  # first session handled live
    class BoomPipeline:
        adapter = envG.adapter
        async def handle_event(self, event):
            raise RuntimeError("recovery blew up")
    execG = dm.ActionExecutor(store=envG.store, relay_root=envG.relay_root,
                              pipeline=BoomPipeline(), audit=envG.audit)
    fetchedG = [{"conversation": envG.chan.ref.to_dict(),
                 "message_id": "m99", "author_is_self": False,
                 "author_is_bot": False, "raw": msgG}]
    actsG = rc.plan_reconnect_actions([], fetchedG, {})
    await execG.execute(actsG)
    check("recovery failure: chain stopped, cursor NOT advanced",
          envG.store.load_watch_cursors() == {}
          and envG.audit.has("error", "reconnect recovery"))

    # I/O-failure resilience: OSError from the spool write is audited and
    # swallowed — the daemon stays alive, state left for reconciliation
    envH = await Env(tmp_base / "eH").start()
    uH = envH.user("U1")
    await envH.intake(uH)
    sidH = envH.store.list_ids()[0]
    sessH = SessionDir(envH.relay_root / sidH)
    qH = make_question(sidH, 1)
    sessH.write_question(qH)
    recH = envH.store.load(sidH)
    await envH.pipeline.post_question(recH, qH)
    real_writeH = SessionDir.write_answer
    def boom_writeH(self, a, **kw):
        raise OSError("disk full")
    SessionDir.write_answer = boom_writeH
    interH = select_interaction(sidH, 1, qH.options[0].value, uH,
                                ConversationRef.from_dict(recH.thread),
                                iid="iH")
    envH.adapter.inject_interaction(interH)
    await envH.drain()  # must not raise — the daemon must survive
    SessionDir.write_answer = real_writeH
    check("OSError in spool write: audited, daemon survives, no answer",
          envH.audit.has("error", "handler error: OSError")
          and sessH.read_answer(1) is None)

    # ---- no-cursor policy: baseline + first-disconnect recovery ----
    # (a) channel with pre-startup history: baseline = newest old message;
    # disconnect-before-any-live-message still recovers downtime messages,
    # and the OLD message is never slurped as an intake candidate.
    envI = await Env(tmp_base / "eI").start()
    uI = envI.user("U1")
    envI.adapter.inject_message(envI.chan.ref, "ancient report", uI)
    await dm.ensure_watch_baseline(store=envI.store, adapter=envI.adapter,
                                   intake_ref=envI.chan.ref, audit=envI.audit)
    check("baseline established at newest pre-startup message",
          list(envI.store.load_watch_cursors().values())[0]["message_id"]
          is not None)
    envI.adapter.inject_message(envI.chan.ref, "downtime bug", uI)
    await dm.run_reconnect_reconciliation(
        store=envI.store, relay_root=envI.relay_root,
        intake_ref=envI.chan.ref, pipeline=envI.pipeline, audit=envI.audit)
    check("downtime message recovered; pre-startup message NOT slurped",
          len(envI.store.list_ids()) == 1)

    # (b) empty channel at startup ⇒ explicit marker; bounded no-after fetch
    envJ = await Env(tmp_base / "eJ").start()
    uJ = envJ.user("U1")
    await dm.ensure_watch_baseline(store=envJ.store, adapter=envJ.adapter,
                                   intake_ref=envJ.chan.ref, audit=envJ.audit)
    check("empty channel persists a None baseline marker",
          list(envJ.store.load_watch_cursors().values())[0]["message_id"]
          is None)
    envJ.adapter.inject_message(envJ.chan.ref, "first-ever bug", uJ)
    await dm.run_reconnect_reconciliation(
        store=envJ.store, relay_root=envJ.relay_root,
        intake_ref=envJ.chan.ref, pipeline=envJ.pipeline, audit=envJ.audit)
    check("marker baseline: downtime message recovered via bounded fetch",
          len(envJ.store.list_ids()) == 1)

    # (c) no baseline at all (startup fetch failed): recovery is skipped
    # fail-safe (audited), and the baseline is re-established for the NEXT
    # disconnect — old history is never processed fail-open.
    envK = await Env(tmp_base / "eK").start()
    uK = envK.user("U1")
    envK.adapter.inject_message(envK.chan.ref, "ambiguous downtime msg", uK)
    await dm.run_reconnect_reconciliation(
        store=envK.store, relay_root=envK.relay_root,
        intake_ref=envK.chan.ref, pipeline=envK.pipeline, audit=envK.audit)
    check("no baseline: recovery skipped fail-safe + audited",
          envK.store.list_ids() == []
          and envK.audit.has("warning", "no watch baseline"))
    check("baseline re-established for the next disconnect",
          envK.store.load_watch_cursors() != {})

    # (d) baseline SAVE failure (disk-full): audited, never raises — the
    # daemon can still start / reconnect recovery cannot escape.
    envL = await Env(tmp_base / "eL").start()
    def boom_baseline(conversation, message_id):
        raise OSError("read-only fs")
    envL.store.save_watch_cursor = boom_baseline
    await dm.ensure_watch_baseline(store=envL.store, adapter=envL.adapter,
                                   intake_ref=envL.chan.ref, audit=envL.audit)
    check("baseline save failure: audited + swallowed (fail-safe)",
          envL.audit.has("warning", "watch baseline save failed")
          and envL.store.load_watch_cursors() == {})

    # (e) malformed spool files are untrusted on-disk state: they must not
    # abort the scan (and with it daemon startup) — the bad seq is
    # excluded, the rest of the session still reconciles.
    envM = await Env(tmp_base / "eM").start()
    uM = envM.user("U1")
    await envM.intake(uM)
    sidM = envM.store.list_ids()[0]
    sessM = SessionDir(envM.relay_root / sidM)
    sessM.write_question(make_question(sidM, 1))       # healthy pending
    (envM.relay_root / sidM / "answer-2.json").write_text("{corrupt")
    (envM.relay_root / sidM / "question-2.json").write_text(
        json.dumps(make_question(sidM, 2).to_dict()))
    await dm.run_startup_reconciliation(
        store=envM.store, relay_root=envM.relay_root,
        launcher=FakeLauncher(), workspace_id="W1",
        pipeline=envM.pipeline, audit=envM.audit)
    check("malformed spool file: startup completes, bad seq excluded",
          envM.audit.has("warning", "malformed spool file")
          and envM.store.load(sidM).state == "failed"
          # healthy seq 1 was cancelled (phase 1) before the dir removal
          # (phase 3); the malformed seq 2 was excluded (no cancel audit).
          and envM.audit.has("info", "cancelled answer written s=%s seq=1"
                             % sidM)
          and not envM.audit.has("info", "cancelled answer written s=%s seq=2"
                                 % sidM)
          and not (envM.relay_root / sidM).exists())

    # ================= production argv resolution (t1120_5) ==============
    # The full agent command comes from the engine-owned dry-run — parsed
    # from the %q-quoted DRY_RUN line, never hand-assembled.
    dry_line = ("noise\nDRY_RUN: env BASH_DEFAULT_TIMEOUT_MS=630000 claude "
                "--model claude-x --print /aitask-explorechat "
                "--allowedTools Bash\\,Read\\,Write\n")
    check("parse_dry_run_argv undoes %q quoting into the argv tuple",
          dm.parse_dry_run_argv(dry_line)
          == ("env", "BASH_DEFAULT_TIMEOUT_MS=630000", "claude", "--model",
              "claude-x", "--print", "/aitask-explorechat",
              "--allowedTools", "Bash,Read,Write"))
    check("parse_dry_run_argv returns () when no DRY_RUN line",
          dm.parse_dry_run_argv("ERROR: nope\n") == ())

    # ================= merged event/death stream (t1120_5) ===============
    # ONE sequential consumer over adapter events + death signals: a death
    # signalled while an item is in flight is dispatched only after it —
    # in order, never concurrently.
    async def two_events():
        yield "E1"
        yield "E2"
    qM = asyncio.Queue()
    seq_order = []
    async for kind, item in dm._merged_events(two_events(), qM):
        seq_order.append((kind, item))
        if item == "E1":
            # arrives while E1 is "being handled" by this consumer
            qM.put_nowait("sMid")
        if len(seq_order) == 3:
            break
    check("death mid-event dispatched AFTER the in-flight event, in order",
          seq_order == [("event", "E1"), ("death", "sMid"), ("event", "E2")])

    # death-before-anything is yielded first; stream end terminates cleanly
    qM2 = asyncio.Queue()
    qM2.put_nowait("sFirst")
    async def one_event():
        yield "E1"
    got = [pair async for pair in dm._merged_events(one_event(), qM2)]
    check("queued death yielded before the stream item; stream end returns",
          got == [("death", "sFirst"), ("event", "E1")])

    # disconnect boundary: an unconsumed death signal survives the merged
    # loop's close and drains when the next merged loop resumes
    qM3 = asyncio.Queue()
    async def endless():
        yield "E1"
        await asyncio.Event().wait()  # never yields again
    merged3 = dm._merged_events(endless(), qM3)
    first = await merged3.__anext__()
    qM3.put_nowait("sLate")
    await asyncio.sleep(0)  # let the queue-get task retrieve it
    await merged3.aclose()
    check("unconsumed death requeued on merged-loop close (never dropped)",
          first == ("event", "E1") and qM3.qsize() == 1)
    qM4_events = [pair async for pair in dm._merged_events(one_event(), qM3)]
    check("requeued death drains when the merged loop resumes",
          ("death", "sLate") in qM4_events)

    # ================= run_daemon end-to-end ==============================
    envF = await Env(tmp_base / "eF").start()
    uF = envF.user("U1")
    stop = asyncio.Event()
    prod_argv = ("env", "BASH_DEFAULT_TIMEOUT_MS=630000", "claude",
                 "--print", "/aitask-explorechat")
    task = asyncio.create_task(dm.run_daemon(
        adapter=envF.adapter, config=envF.config, store=envF.store,
        launcher=envF.launcher, relay_root=envF.relay_root,
        audit=envF.audit, stop=stop, repo_root=FIXTURE_REPO,
        agent_argv=prod_argv))
    await asyncio.sleep(0.05)  # let it subscribe
    envF.adapter.inject_message(envF.chan.ref, "daemon-path bug", uF)
    for _ in range(100):
        if envF.store.list_ids():
            break
        await asyncio.sleep(0.02)
    check("run_daemon consumes the real stream (session created)",
          len(envF.store.list_ids()) == 1)
    check("run_daemon advanced the watch cursor",
          envF.store.load_watch_cursors() != {})
    # cursor-save OSError must not stop the daemon (same resilience class
    # as the handler boundary): the event is handled, the failure audited,
    # and the loop keeps consuming.
    def boom_cursor(conversation, message_id):
        raise OSError("read-only fs")
    envF.store.save_watch_cursor = boom_cursor
    envF.adapter.inject_message(envF.chan.ref, "cursor-save fails", uF)
    for _ in range(100):
        if envF.audit.has("warning", "watch-cursor save failed"):
            break
        await asyncio.sleep(0.02)
    check("cursor-save OSError: audited, daemon still running",
          envF.audit.has("warning", "watch-cursor save failed")
          and not task.done()
          and len(envF.store.list_ids()) == 2)

    # agent death mid-run (t1120_5): the recorded spec carries the daemon's
    # death signal; firing it drives the full loop-side path — cancelled
    # answer, record failed, dirs removed — executed by the ONE sequential
    # consumer (the executor), never by the signalling thread.
    specF = envF.launcher.launched[0]
    sidF = specF.session_id
    check("run_daemon threads the production argv into the launched spec",
          specF.agent_argv == prod_argv)
    check("death signal threaded into the launched spec",
          specF.on_death is not None)
    sessF = SessionDir(envF.relay_root / sidF)
    sessF.write_question(make_question(sidF, 1))
    specF.on_death(sidF)  # thread-safe entry point (same-loop call is fine)
    for _ in range(100):
        recF = envF.store.load(sidF)
        if recF is not None and recF.state == "failed":
            break
        await asyncio.sleep(0.02)
    check("agent death: record failed via the daemon loop",
          envF.store.load(sidF).state == "failed")
    check("agent death: cancelled answer written + both dirs removed",
          envF.audit.has("info", "cancelled answer written")
          and not (envF.relay_root / sidF).exists()
          and not (cl_paths.workspaces_root_beside(envF.relay_root)
                   / sidF).exists())
    check("agent death dispatch audited", envF.audit.has("info", "agent death:"))
    # duplicate/stale signal: record already terminal → planner no-ops
    lines_beforeF = len(envF.audit.lines)
    specF.on_death(sidF)
    await asyncio.sleep(0.1)
    check("duplicate death signal is a no-op (terminal record)",
          not any("agent death:" in m
                  for _, m in envF.audit.lines[lines_beforeF:])
          and not task.done())
    stop.set()
    envF.adapter.simulate_disconnect()
    rcF = await asyncio.wait_for(task, 2.0)
    check("run_daemon stops cleanly on stop signal", rcF == 0)

    # ================= serve(): zero-side-effect refuse paths =============
    import chatlink.paths as paths_mod
    real_cfg_file = paths_mod.config_file
    real_get_logger = dm.audit_mod.get_logger
    constructed = []
    dm.audit_mod.get_logger = lambda *a: constructed.append("logger")
    try:
        # refuse 1: no config path
        dm.paths.config_file = lambda: None
        rc1 = await dm.serve()
        # refuse 2: config present but no token
        dm.paths.config_file = real_cfg_file
        real_read_token = dm.paths.read_token
        dm.paths.read_token = lambda: None
        rc2 = await dm.serve()
        dm.paths.read_token = real_read_token
        # refuse 3: config + token ok, but the agent argv is unresolvable
        # (t1120_5 — a gateway that can never launch must not start)
        import contextlib
        import io
        cfg_tmp = tmp_base / "serve_cfg.yaml"
        cfg_tmp.write_text(
            "intake_channel:\n  provider: mock\n  workspace_id: W1\n"
            "  conversation_id: C1\nallowed_user_ids: [U1]\n")
        dm.paths.config_file = lambda: cfg_tmp
        dm.paths.read_token = lambda: "tok"
        real_resolve = dm.resolve_explore_relay_argv
        dm.resolve_explore_relay_argv = lambda: ()
        err3 = io.StringIO()
        with contextlib.redirect_stderr(err3):
            rc3 = await dm.serve()
        dm.resolve_explore_relay_argv = real_resolve
        dm.paths.read_token = real_read_token
    finally:
        dm.paths.config_file = real_cfg_file
        dm.audit_mod.get_logger = real_get_logger
    check("serve refuses without config (rc=2)", rc1 == 2)
    check("serve refuses without token (rc=2)", rc2 == 2)
    check("serve refuses when the agent argv cannot be resolved (rc=2)",
          rc3 == 2 and "explore-relay" in err3.getvalue())
    check("refuse paths construct NOTHING (spy)", constructed == [])

    print(f"\nAll {PASS + 1} Python checks passed.")


asyncio.run(main())
PYEOF

# ---- Part 2: launcher / dispatcher routing ---------------------------------
cd "$PROJECT_DIR"

# No --headless → the launcher dispatches the TUI module (--smoke
# constructs the app and exits 0 without entering the event loop).
out="$(./ait chatlink --smoke 2>&1)" && rc=0 || rc=$?
if [[ $rc -eq 0 ]]; then
    echo "ok - ait chatlink (no --headless) routes to the TUI (smoke rc=0)"
elif echo "$out" | grep -q "Missing Python packages"; then
    echo "ok - ait chatlink routes to the launcher (deps preflight fired)"
else
    echo "FAIL: unexpected ait chatlink --smoke output (rc=$rc): $out"
    exit 1
fi

# Direct daemon invocation without --headless stays refused (defense in
# depth — the launcher, not the daemon, owns TUI dispatch).
out="$(PYTHONPATH="$PROJECT_DIR/.aitask-scripts" "$PYTHON" -m chatlink.daemon 2>&1 || true)"
if echo "$out" | grep -q "headless-only"; then
    echo "ok - chatlink.daemon without --headless refuses (headless-only)"
else
    echo "FAIL: unexpected chatlink.daemon output: $out"
    exit 1
fi

echo
echo "PASS: test_chatlink_daemon.sh"
