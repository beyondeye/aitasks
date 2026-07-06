#!/usr/bin/env bash
# test_chatlink_relay.sh — Q&A relay protocol library tests (t1120_1).
#
# Covers the t1120_1 verification list: schema round-trip + rejection,
# custom_id build/parse/reject, atomic-write hygiene (readers ignore *.tmp),
# restart-derivability (pending = question present ∧ answer absent; a
# timed-out question is TERMINAL), stale-answer negative control, timeout
# fail-safe (durable answer artifact, never-overwrite, never-hang),
# option-value stability, session-dir collision retry, renderer capability
# fail-closed + degradation (26 options / 3000-char text), the no-chat-import
# guard for the agent side, and an E2E test through the REAL
# aitask_relay_ask.sh wrapper (question → hand-written answer → output).
# t1120_4 additions: TaskPayload schema matrix (Part 1), E2E through the
# REAL aitask_relay_payload.sh wrapper incl. independent wire decode and
# no-write-on-invalid (Part 4), and a scripted fake agent playing the
# aitask-explorechat role against the real helpers (Part 5).
# Spec: aidocs/chat/qa_relay_protocol.md
# Run: bash tests/test_chatlink_relay.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

PASS_COUNT=0
FAIL_COUNT=0

assert_eq() {
    local label="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        PASS_COUNT=$((PASS_COUNT + 1))
        echo "ok - $label"
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "FAIL - $label: expected '$expected', got '$actual'"
    fi
}

assert_contains() {
    local label="$1" haystack="$2" needle="$3"
    if [[ "$haystack" == *"$needle"* ]]; then
        PASS_COUNT=$((PASS_COUNT + 1))
        echo "ok - $label"
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "FAIL - $label: '$needle' not found in output"
    fi
}

# ---------------------------------------------------------------------------
# Part 1: Python unit tests (relay.py + render.py)
# ---------------------------------------------------------------------------

if "$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import json
import os
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))

from chatlink.relay import (
    Answer, CustomIdError, Option, Question, RelayError, SessionDir,
    ValidationError, assign_option_values, build_custom_id,
    create_session_dir, mint_session_id, parse_custom_id,
)
from chatlink import relay as relay_mod

PASS = 0
def check(label, cond, detail=""):
    global PASS
    assert cond, f"FAIL: {label}{': ' + str(detail) if detail else ''}"
    PASS += 1
    print(f"ok - {label}")

def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"expected {exc.__name__}, got {type(e).__name__}: {e}")
    return False

tmp = Path(tempfile.mkdtemp(prefix="chatlink_test_"))

# --- session id minting (contract 1) ---
sid = mint_session_id()
check("mint_session_id shape", sid.startswith("s") and len(sid) <= 12
      and all(c in "abcdefghijklmnopqrstuvwxyz0123456789" for c in sid[1:]))

sd = create_session_dir(tmp / "relay")
check("create_session_dir creates dir", sd.path.is_dir())

# collision retry: pre-create every possible dir for a frozen clock+rng
class FixedRandom:
    def __init__(self):  # cycle a tiny deterministic sequence
        self.i = 0
    def choice(self, alphabet):
        self.i += 1
        return alphabet[self.i % 3]

import chatlink.relay as _r
_orig_mint = _r.mint_session_id
_calls = {"n": 0}
def _colliding_mint(now=None):
    _calls["n"] += 1
    if _calls["n"] < 3:
        return "scollide01"   # same id twice -> collision on 2nd call
    return _orig_mint(now)
_r.mint_session_id = _colliding_mint
try:
    first = create_session_dir(tmp / "relay2")
    check("collision setup: first dir minted", first.session_id == "scollide01")
    second = create_session_dir(tmp / "relay2")
    check("collision retry re-mints on FileExistsError",
          second.session_id != "scollide01", second.session_id)
finally:
    _r.mint_session_id = _orig_mint

# --- custom_id (contract 4) ---
cid = build_custom_id(sid, 3, "select")
check("build_custom_id round-trip", parse_custom_id(cid) == (sid, 3, "select"))
check("custom_id rejects bad component",
      raises(CustomIdError, build_custom_id, sid, 1, "WAY_TOO_LONG_TAG"))
check("custom_id rejects seq 0",
      raises(CustomIdError, build_custom_id, sid, 0, "select"))
check("custom_id rejects seq > 999999",
      raises(CustomIdError, build_custom_id, sid, 1_000_000, "select"))
check("parse rejects foreign prefix",
      raises(CustomIdError, parse_custom_id, f"xx1:{sid}:1:select"))
check("parse rejects overlong input",
      raises(CustomIdError, parse_custom_id, "cl1:" + "a" * 120))

# --- option values (contract 3 amendment) ---
opts = assign_option_values([("Parser", "the tokenizer"), ("Renderer", "")])
check("option values auto-assigned o<idx>",
      [o.value for o in opts] == ["o0", "o1"])
check("option label required",
      raises(ValidationError, lambda: Option(value="o0", label="").validate()))
check("option label length capped",
      raises(ValidationError,
             lambda: Option(value="o0", label="x" * 101).validate()))

# --- question/answer schema round-trip + rejection ---
q = Question(id=f"q-{sd.session_id}-1", seq=1, session_id=sd.session_id,
             text="A or B?", header="Spike",
             options=assign_option_values([("A", "a"), ("B", "b")]),
             multi_select=False, allow_free_text=True, timeout_s=90)
q2 = Question.from_dict(json.loads(json.dumps(q.to_dict())))
check("question round-trip", q2 == q)
check("question rejects unknown keys",
      raises(ValidationError, Question.from_dict,
             {**q.to_dict(), "extra": 1}))
check("question rejects missing keys",
      raises(ValidationError, Question.from_dict,
             {k: v for k, v in q.to_dict().items() if k != "text"}))
check("unanswerable question rejected",
      raises(ValidationError, lambda: Question(
          id="x", seq=1, session_id=sd.session_id, text="?",
          allow_free_text=False).validate()))
check("duplicate option values rejected",
      raises(ValidationError, lambda: Question(
          id="x", seq=1, session_id=sd.session_id, text="?",
          options=[Option("o0", "A"), Option("o0", "B")]).validate()))

a = Answer(id=q.id, seq=1, status="answered", values=["o1"],
           free_text=None, answered_by="U1")
a2 = Answer.from_dict(json.loads(json.dumps(a.to_dict())))
check("answer round-trip carries option values", a2.values == ["o1"])
check("answer rejects bad status",
      raises(ValidationError, lambda: Answer(
          id="x", seq=1, status="maybe").validate()))
check("timeout answer must be empty",
      raises(ValidationError, lambda: Answer(
          id="x", seq=1, status="timeout", values=["o0"]).validate()))
check("answered answer needs content",
      raises(ValidationError, lambda: Answer(
          id="x", seq=1, status="answered").validate()))

# --- spool: atomicity, seq derivation, restart-derivability ---
sd.write_question(q)
check("question file written", sd.question_path(1).exists())
check("no tmp residue after write",
      not list(sd.path.glob("*.tmp")))
check("next_seq derived from spool", sd.next_seq() == 2)

# reader ignores *.tmp: a partial writer crash leaves only garbage tmp
(sd.path / "answer-1.json.tmp").write_text("{not json")
check("reader ignores *.tmp (pending unaffected)",
      [p.seq for p in sd.pending_questions()] == [1])
check("read_answer ignores *.tmp", sd.read_answer(1) is None)

# restart-derivability: pending = question present AND answer absent
check("pending before answer", len(sd.pending_questions()) == 1)
sd.write_answer(a)
check("pending drains after answer", sd.pending_questions() == [])

# timed-out question is TERMINAL, not pending (contract 6 amendment)
q3 = Question(id=f"q-{sd.session_id}-2", seq=2, session_id=sd.session_id,
              text="second?", options=assign_option_values([("X", "")]),
              allow_free_text=False)
sd.write_question(q3)
sd.write_answer(Answer(id=q3.id, seq=2, status="timeout"))
check("timed-out question is terminal (not pending)",
      sd.pending_questions() == [])

# never-overwrite rule
took = sd.write_answer(Answer(id=q3.id, seq=2, status="answered",
                              values=["o0"]), overwrite=False)
check("write_answer refuses to overwrite", took is False)
check("original timeout answer intact", sd.read_answer(2).status == "timeout")
check("refused write leaves no tmp residue",
      not list(sd.path.glob("answer-2.json.tmp")))

# TOCTOU negative control: the no-overwrite path must be an atomic
# create-no-replace — os.replace being invoked there would reintroduce the
# check-then-act race (gateway answer clobbered by a helper timeout write).
_orig_replace = os.replace
def _no_replace(*a, **kw):
    raise AssertionError("os.replace used on the no-overwrite answer path")
relay_mod.os.replace = _no_replace
try:
    q4 = Question(id=f"q-{sd.session_id}-4", seq=4,
                  session_id=sd.session_id, text="race?",
                  options=assign_option_values([("A", "")]))
    ok = sd.write_answer(Answer(id=q4.id, seq=4, status="timeout"),
                         overwrite=False)
    check("no-overwrite write succeeds without os.replace", ok is True)
    check("no-overwrite write is readable", sd.read_answer(4).status == "timeout")
finally:
    relay_mod.os.replace = _orig_replace

# staging-name negative control: a competing writer squatting the OLD shared
# tmp name must not be able to poison another writer's staged payload — the
# staging file is per-writer unique, so the squatted file is simply ignored.
squatted = sd.path / "answer-8.json.tmp"
squatted.write_text('{"poisoned": true}')
ok8 = sd.write_answer(Answer(id="q-x-8", seq=8, status="answered",
                             values=["o0"]), overwrite=False)
check("unique staging: write succeeds despite squatted shared tmp", ok8 is True)
check("unique staging: published answer is the writer's payload",
      sd.read_answer(8).values == ["o0"])
check("unique staging: squatted tmp untouched",
      squatted.read_text() == '{"poisoned": true}')

# session mismatch guard
check("write_question rejects foreign session",
      raises(ValidationError, sd.write_question,
             Question(id="x", seq=9, session_id="sother1",
                      text="?", options=[Option("o0", "A")])))

# --- renderer (gateway side) ---
from chat.capabilities import Capabilities
from chat.interactions import Interaction, InteractionType
from chat.model import Actor, ActorType, ConversationRef
from chatlink.render import (
    AnswerMismatch, RenderRejected, assemble_answer, build_modal,
    is_free_text_trigger, is_page_nav, page_count, render_question,
)

caps = Capabilities()
conv = ConversationRef(provider="mock", workspace_id="w", conversation_id="c")
actor = Actor(id="U42", type=ActorType.USER)

r = render_question(q, caps)
check("render: one select row + free-text row", len(r.rows) == 2)
select = r.rows[0].components[0]
check("render: select carries stable option values",
      [o.value for o in select.options] == ["o0", "o1"])
check("render: single chunk under limit", len(r.text_chunks) == 1)

# capability fail-closed (negative controls)
check("no selects => RenderRejected",
      raises(RenderRejected, render_question, q,
             Capabilities(supports_selects=False)))
check("no modals + free text => RenderRejected",
      raises(RenderRejected, render_question, q,
             Capabilities(supports_modals=False)))
check("no buttons + free text => RenderRejected",
      raises(RenderRejected, render_question, q,
             Capabilities(supports_buttons=False)))

# degradation: 26 options paginate; 3000-char text chunks
big_q = Question(id=f"q-{sd.session_id}-3", seq=3, session_id=sd.session_id,
                 text="pick", options=assign_option_values(
                     [(f"L{i}", "") for i in range(26)]))
check("26 options => 2 pages", page_count(big_q) == 2)
rp0 = render_question(big_q, caps, page=0)
check("page 0: 24 options + nav row",
      len(rp0.rows[0].components[0].options) == 24 and len(rp0.rows) == 2)
rp1 = render_question(big_q, caps, page=1)
check("page 1: remaining 2 options",
      len(rp1.rows[0].components[0].options) == 2)
nav_next = rp0.rows[1].components[1]
check("nav button targets page statelessly",
      parse_custom_id(nav_next.custom_id)[2] == "pg1")
check("nav interaction resolves target page",
      is_page_nav(big_q, Interaction(
          id="i1", type=InteractionType.BUTTON, actor=actor,
          conversation=conv, custom_id=nav_next.custom_id)) == 1)
check("page out of range rejected",
      raises(RenderRejected, render_question, big_q, caps, 5))

# pagination nav is button-based: selects-without-buttons must fail closed
check("pagination without buttons => RenderRejected",
      raises(RenderRejected, render_question, big_q,
             Capabilities(supports_buttons=False, supports_modals=False)))
# but the same capability set renders a NON-paginated select fine
small_q = Question(id=f"q-{sd.session_id}-5", seq=5,
                   session_id=sd.session_id, text="pick one",
                   options=assign_option_values([("A", ""), ("B", "")]))
check("selects-only adapter renders unpaginated options",
      len(render_question(small_q, Capabilities(
          supports_buttons=False, supports_modals=False)).rows) == 1)

# paginated multi-select cannot accumulate across pages => rejected in v1
multi_big = Question(id=f"q-{sd.session_id}-6", seq=6,
                     session_id=sd.session_id, text="pick many",
                     options=assign_option_values(
                         [(f"M{i}", "") for i in range(26)]),
                     multi_select=True)
check("paginated multi-select => RenderRejected",
      raises(RenderRejected, render_question, multi_big, caps))

long_q = Question(id=f"q-{sd.session_id}-4", seq=4,
                  session_id=sd.session_id, text="x" * 3000,
                  options=assign_option_values([("A", "")]))
rl = render_question(long_q, caps)
check("3000-char text chunked to <= max_message_length",
      len(rl.text_chunks) >= 2
      and all(len(c) <= caps.max_message_length for c in rl.text_chunks))

# assemble_answer: select path
sel_cid = select.custom_id
ans = assemble_answer(q, Interaction(
    id="i2", type=InteractionType.SELECT, actor=actor, conversation=conv,
    custom_id=sel_cid, values={"values": ["o1"]}))
check("assemble select answer", ans.status == "answered"
      and ans.values == ["o1"] and ans.answered_by == "U42")

# assemble_answer: modal path
modal = build_modal(q)
field_id = modal.fields[0].custom_id
ans_ft = assemble_answer(q, Interaction(
    id="i3", type=InteractionType.MODAL_SUBMIT, actor=actor,
    conversation=conv, custom_id=modal.custom_id,
    values={field_id: "free answer"}))
check("assemble modal answer", ans_ft.free_text == "free answer"
      and ans_ft.values == [])

# free-text trigger is NOT an answer
ft_btn = r.rows[1].components[0]
check("free-text trigger detected",
      is_free_text_trigger(q, Interaction(
          id="i4", type=InteractionType.BUTTON, actor=actor,
          conversation=conv, custom_id=ft_btn.custom_id)))
check("free-text trigger rejected as answer",
      raises(AnswerMismatch, assemble_answer, q, Interaction(
          id="i5", type=InteractionType.BUTTON, actor=actor,
          conversation=conv, custom_id=ft_btn.custom_id)))

# stale-answer negative control: interaction for a DIFFERENT seq
stale_cid = build_custom_id(sd.session_id, 1, "select")
check("stale interaction (wrong seq) rejected",
      raises(AnswerMismatch, assemble_answer, big_q, Interaction(
          id="i6", type=InteractionType.SELECT, actor=actor,
          conversation=conv, custom_id=stale_cid,
          values={"values": ["o0"]})))
check("unknown option value rejected",
      raises(AnswerMismatch, assemble_answer, q, Interaction(
          id="i7", type=InteractionType.SELECT, actor=actor,
          conversation=conv, custom_id=sel_cid,
          values={"values": ["o9"]})))
# single-select must carry exactly one value (forged multi-value rejected)
check("multi-value on single-select rejected",
      raises(AnswerMismatch, assemble_answer, q, Interaction(
          id="i8", type=InteractionType.SELECT, actor=actor,
          conversation=conv, custom_id=sel_cid,
          values={"values": ["o0", "o1"]})))
# ...while a multi_select question accepts several values
multi_q = Question(id=f"q-{sd.session_id}-7", seq=7,
                   session_id=sd.session_id, text="pick many",
                   options=assign_option_values([("A", ""), ("B", "")]),
                   multi_select=True)
multi_cid = build_custom_id(sd.session_id, 7, "select")
ans_multi = assemble_answer(multi_q, Interaction(
    id="i9", type=InteractionType.SELECT, actor=actor, conversation=conv,
    custom_id=multi_cid, values={"values": ["o0", "o1"]}))
check("multi-select accepts multiple values",
      ans_multi.values == ["o0", "o1"])

# --- TaskPayload schema (contract 7 + contract 1; t1120_4) ---
from chatlink.relay import TaskPayload

def payload_kwargs(**over):
    base = dict(session_id=sd.session_id, name="fix_login",
                title="Fix login", priority="high", effort="medium",
                issue_type="bug", labels=["auth", "back-end"],
                description="body\n")
    base.update(over)
    return base

good = TaskPayload(**payload_kwargs())
good.validate()
check("payload: valid payload accepted", True)
rt = TaskPayload.from_dict(good.to_dict())
check("payload: to_dict/from_dict round-trip", rt == good)

check("payload: missing key rejected",
      raises(ValidationError, TaskPayload.from_dict,
             {k: v for k, v in good.to_dict().items() if k != "title"}))
check("payload: unknown key rejected",
      raises(ValidationError, TaskPayload.from_dict,
             dict(good.to_dict(), extra=1)))
check("payload: bad session_id rejected",
      raises(ValidationError,
             TaskPayload(**payload_kwargs(session_id="NOPE")).validate))
check("payload: bad name slug rejected",
      raises(ValidationError,
             TaskPayload(**payload_kwargs(name="Bad Name")).validate))
check("payload: oversize name rejected",
      raises(ValidationError,
             TaskPayload(**payload_kwargs(name="x" * 65)).validate))
check("payload: oversize title rejected",
      raises(ValidationError,
             TaskPayload(**payload_kwargs(title="t" * 121)).validate))
check("payload: empty title rejected",
      raises(ValidationError,
             TaskPayload(**payload_kwargs(title="   ")).validate))
check("payload: bad priority enum rejected",
      raises(ValidationError,
             TaskPayload(**payload_kwargs(priority="urgent")).validate))
check("payload: bad effort enum rejected",
      raises(ValidationError,
             TaskPayload(**payload_kwargs(effort="huge")).validate))
check("payload: bad issue_type rejected",
      raises(ValidationError,
             TaskPayload(**payload_kwargs(issue_type="Bug!")).validate))
check("payload: non-list labels rejected",
      raises(ValidationError,
             TaskPayload(**payload_kwargs(labels="auth")).validate))
check("payload: bad label slug rejected",
      raises(ValidationError,
             TaskPayload(**payload_kwargs(labels=["ok", "no spaces"])).validate))
check("payload: empty labels accepted",
      TaskPayload(**payload_kwargs(labels=[])).validate() is None)
check("payload: empty description rejected",
      raises(ValidationError,
             TaskPayload(**payload_kwargs(description=" ")).validate))
check("payload: oversize description rejected (64 KiB, UTF-8 bytes)",
      raises(ValidationError,
             TaskPayload(**payload_kwargs(
                 description="é" * (32 * 1024 + 1))).validate))

print(f"\nPART1_PASS:{PASS}")
PYEOF
then
    PART1_OK=1
    PASS_COUNT=$((PASS_COUNT + 1))
    echo "ok - part 1: python unit tests"
else
    PART1_OK=0
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "FAIL - part 1: python unit tests"
fi

# ---------------------------------------------------------------------------
# Part 2: import-purity guard — the agent side must not import chat/ or any
# framework module (mirror of tests/test_chat_no_aitasks_import.sh).
# ---------------------------------------------------------------------------

if "$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import sys
from pathlib import Path

root = Path(sys.argv[1])
scripts_dir = root / ".aitask-scripts"
for extra in (scripts_dir, scripts_dir / "lib"):
    sys.path.insert(0, str(extra))

before = set(sys.modules)
import chatlink.relay          # noqa: F401
import chatlink.relay_ask      # noqa: F401
import chatlink.relay_payload  # noqa: F401
new_modules = set(sys.modules) - before

FRAMEWORK_PREFIXES = ("monitor", "applink", "aitask", "board",
                      "tui_", "tmux_", "task_yaml", "gate_ledger")
offenders = sorted(
    m for m in new_modules
    if (top := m.split(".")[0]) != "chatlink"
    and (top == "chat" or top.startswith(FRAMEWORK_PREFIXES)))
assert not offenders, f"agent side imported framework/chat: {offenders}"
print("ok - agent side imports no chat/framework module")

stdlib_names = getattr(sys, "stdlib_module_names", frozenset())
nonstd = [m for m in new_modules
          if m.split(".")[0] not in stdlib_names
          and m.split(".")[0] != "chatlink"]
assert not nonstd, f"agent side imported non-stdlib: {nonstd}"
print("ok - agent side is stdlib-only")
PYEOF
then
    PASS_COUNT=$((PASS_COUNT + 1))
    echo "ok - part 2: import-purity guard"
else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "FAIL - part 2: import-purity guard"
fi

# ---------------------------------------------------------------------------
# Part 3: E2E through the REAL aitask_relay_ask.sh wrapper (real entry point)
# ---------------------------------------------------------------------------

E2E_TMP="$(mktemp -d "${TMPDIR:-/tmp}/chatlink_e2e_XXXXXX")"
trap 'rm -rf "$E2E_TMP"' EXIT
SESSION_DIR="$E2E_TMP/stest01"
mkdir -p "$SESSION_DIR"
WRAPPER="$PROJECT_DIR/.aitask-scripts/aitask_relay_ask.sh"

# 3a: answered round trip
"$WRAPPER" --relay-dir "$SESSION_DIR" \
    --text "A or B?" --header "Spike" \
    --option "A::option a" --option "B::option b" \
    --timeout 30 > "$E2E_TMP/out1.txt" 2>"$E2E_TMP/err1.txt" &
ASK_PID=$!

# wait for the question to appear (the wrapper wrote it), then answer by hand
for _ in $(seq 1 50); do
    [ -f "$SESSION_DIR/question-1.json" ] && break
    sleep 0.2
done
assert_eq "e2e: question-1.json appears" "1" \
    "$([ -f "$SESSION_DIR/question-1.json" ] && echo 1 || echo 0)"
Q_CONTENT="$(cat "$SESSION_DIR/question-1.json" 2>/dev/null || true)"
assert_contains "e2e: question carries text" "$Q_CONTENT" '"A or B?"'
assert_contains "e2e: question carries auto value o0" "$Q_CONTENT" '"o0"'
assert_contains "e2e: question carries auto value o1" "$Q_CONTENT" '"o1"'

printf '%s' '{"id": "q-stest01-1", "seq": 1, "status": "answered", "values": ["o1"], "free_text": null, "answered_by": "tester"}' \
    > "$SESSION_DIR/answer-1.json.tmp"
mv "$SESSION_DIR/answer-1.json.tmp" "$SESSION_DIR/answer-1.json"

wait "$ASK_PID"
E2E_RC=$?
OUT1="$(cat "$E2E_TMP/out1.txt")"
assert_eq "e2e: wrapper exit 0 on answered" "0" "$E2E_RC"
assert_contains "e2e: STATUS:answered" "$OUT1" "STATUS:answered"
assert_contains "e2e: VALUE resolved to label" "$OUT1" "VALUE:B"

# 3b: second invocation picks seq 2 (seq derived from spool)
OUT2="$("$WRAPPER" --relay-dir "$SESSION_DIR" \
    --text "again?" --option "X::x" --timeout 2 2>/dev/null)"
assert_eq "e2e: second ask writes question-2.json" "1" \
    "$([ -f "$SESSION_DIR/question-2.json" ] && echo 1 || echo 0)"

# 3c: timeout fail-safe — exit 0, STATUS:timeout, durable answer artifact
assert_contains "e2e: timeout prints STATUS:timeout" "$OUT2" "STATUS:timeout"
ANSWER2="$(cat "$SESSION_DIR/answer-2.json" 2>/dev/null || true)"
assert_contains "e2e: durable timeout answer written" "$ANSWER2" '"timeout"'

# 3d: helper never hangs — a 1s-timeout subprocess terminates promptly
START_S=$SECONDS
"$WRAPPER" --relay-dir "$SESSION_DIR" --text "hang check" \
    --option "Y::y" --timeout 1 > /dev/null 2>&1
ELAPSED=$((SECONDS - START_S))
if [ "$ELAPSED" -le 5 ]; then
    PASS_COUNT=$((PASS_COUNT + 1))
    echo "ok - e2e: 1s-timeout ask returns promptly (${ELAPSED}s)"
else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "FAIL - e2e: ask took ${ELAPSED}s with 1s timeout"
fi

# 3e: usage/environment error is loud (exit 2), not silent
set +e
"$WRAPPER" --relay-dir "$E2E_TMP/does_not_exist" --text "x" --option "A::a" \
    > /dev/null 2>"$E2E_TMP/err_missing.txt"
MISSING_RC=$?
set -e
assert_eq "e2e: missing relay dir exits 2" "2" "$MISSING_RC"
assert_contains "e2e: missing relay dir is loud on stderr" \
    "$(cat "$E2E_TMP/err_missing.txt")" "ERROR:"

# ---------------------------------------------------------------------------
# Part 4: E2E through the REAL aitask_relay_payload.sh wrapper (t1120_4)
# ---------------------------------------------------------------------------

PAYLOAD_WRAPPER="$PROJECT_DIR/.aitask-scripts/aitask_relay_payload.sh"
PAY_DIR="$E2E_TMP/spay01"
mkdir -p "$PAY_DIR"
printf '## Findings\n\nline one\n' > "$E2E_TMP/desc.md"

# 4a: valid payload — PAYLOAD_WRITTEN + wire bytes decoded INDEPENDENTLY
OUT_PAY="$("$PAYLOAD_WRAPPER" --relay-dir "$PAY_DIR" \
    --name fix_login_timeout --title "Fix login timeout" \
    --priority high --effort medium --issue-type bug \
    --labels auth,back-end --description-file "$E2E_TMP/desc.md")"
PAY_RC=$?
assert_eq "payload e2e: exit 0" "0" "$PAY_RC"
assert_contains "payload e2e: PAYLOAD_WRITTEN line" "$OUT_PAY" \
    "PAYLOAD_WRITTEN:$PAY_DIR/payload.json"
# Independent ground truth: parse the wire bytes with plain json, not the
# dataclass that wrote them.
WIRE_CHECK="$("$PYTHON" - "$PAY_DIR/payload.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
ok = (d["session_id"] == "spay01" and d["name"] == "fix_login_timeout"
      and d["title"] == "Fix login timeout" and d["priority"] == "high"
      and d["effort"] == "medium" and d["issue_type"] == "bug"
      and d["labels"] == ["auth", "back-end"]
      and d["description"].startswith("## Findings"))
print("WIRE_OK" if ok else f"WIRE_BAD:{d}")
PYEOF
)"
assert_eq "payload e2e: wire bytes match fields (independent decode)" \
    "WIRE_OK" "$WIRE_CHECK"

# 4b: session_id derived from the dir name (contract 1)
assert_contains "payload e2e: session_id from dir name" \
    "$(cat "$PAY_DIR/payload.json")" '"session_id": "spay01"'

# 4c: invalid input → exit 2, ERROR:, and NO payload written (no side
# effect before validation)
PAY_DIR2="$E2E_TMP/spay02"
mkdir -p "$PAY_DIR2"
set +e
"$PAYLOAD_WRAPPER" --relay-dir "$PAY_DIR2" \
    --name "Bad Name" --title "x" --priority high --effort medium \
    --issue-type bug --description-file "$E2E_TMP/desc.md" \
    > /dev/null 2>"$E2E_TMP/err_pay.txt"
BAD_RC=$?
set -e
assert_eq "payload e2e: invalid name exits 2" "2" "$BAD_RC"
assert_contains "payload e2e: invalid name is loud on stderr" \
    "$(cat "$E2E_TMP/err_pay.txt")" "ERROR:"
assert_eq "payload e2e: nothing written on validation failure" "0" \
    "$([ -f "$PAY_DIR2/payload.json" ] && echo 1 || echo 0)"

# 4d: --description-file - reads stdin
OUT_STDIN="$(printf 'stdin body\n' | "$PAYLOAD_WRAPPER" --relay-dir "$PAY_DIR2" \
    --name from_stdin --title "t" --priority low --effort low \
    --issue-type chore --description-file -)"
assert_contains "payload e2e: stdin description accepted" "$OUT_STDIN" \
    "PAYLOAD_WRITTEN:"

# ---------------------------------------------------------------------------
# Part 5: relay-conformance with a scripted fake agent (t1120_4) — a bash
# script plays the aitask-explorechat role end-to-end against the REAL
# helpers: ask (answered), ask (timeout → durable artifact, flow proceeds),
# write payload. Proves the machinery below the LLM.
# ---------------------------------------------------------------------------

FAKE_DIR="$E2E_TMP/sfake01"
mkdir -p "$FAKE_DIR"
cat > "$E2E_TMP/fake_agent.sh" <<FAKEEOF
#!/usr/bin/env bash
set -euo pipefail
RELAY="\$1"
ASK="$PROJECT_DIR/.aitask-scripts/aitask_relay_ask.sh"
PAY="$PAYLOAD_WRAPPER"
# Q1: gets answered by the test
OUT1="\$("\$ASK" --relay-dir "\$RELAY" --text "Which module?" \
    --header "Module" --option "parser::p" --option "renderer::r" \
    --timeout 30)"
echo "\$OUT1" | grep -q "STATUS:answered" || exit 10
CHOSEN="\$(echo "\$OUT1" | sed -n 's/^VALUE://p')"
# Q2: nobody answers — must proceed on timeout (fail-safe), not die
OUT2="\$("\$ASK" --relay-dir "\$RELAY" --text "Repro steps?" \
    --free-text --timeout 1)"
echo "\$OUT2" | grep -q "STATUS:timeout" || exit 11
# Final act: write the payload via the real helper
printf 'Chosen: %s (Q2 timed out; default taken)\n' "\$CHOSEN" \
    | "\$PAY" --relay-dir "\$RELAY" --name fake_fix --title "Fake fix" \
        --priority medium --effort low --issue-type bug \
        --labels auth --description-file -
FAKEEOF
chmod +x "$E2E_TMP/fake_agent.sh"

"$E2E_TMP/fake_agent.sh" "$FAKE_DIR" > "$E2E_TMP/fake_out.txt" 2>&1 &
FAKE_PID=$!
for _ in $(seq 1 50); do
    [ -f "$FAKE_DIR/question-1.json" ] && break
    sleep 0.2
done

# 5a: emitted question conforms to contract 3 (schema-validated via lib)
Q1_CONFORM="$("$PYTHON" - "$PROJECT_DIR" "$FAKE_DIR/question-1.json" <<'PYEOF'
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / ".aitask-scripts"))
from chatlink.relay import Question
q = Question.from_dict(json.load(open(sys.argv[2])))
ok = (q.text == "Which module?" and [o.value for o in q.options] == ["o0", "o1"]
      and q.session_id == "sfake01" and q.seq == 1)
print("Q1_OK" if ok else "Q1_BAD")
PYEOF
)"
assert_eq "fake agent: question-1 conforms to contract 3" "Q1_OK" "$Q1_CONFORM"

# answer Q1 (renderer option value, gateway-style)
printf '%s' '{"id": "q-sfake01-1", "seq": 1, "status": "answered", "values": ["o1"], "free_text": null, "answered_by": "tester"}' \
    > "$FAKE_DIR/answer-1.json.tmp2" \
    && mv "$FAKE_DIR/answer-1.json.tmp2" "$FAKE_DIR/answer-1.json"

wait "$FAKE_PID"
FAKE_RC=$?
assert_eq "fake agent: full flow exits 0" "0" "$FAKE_RC"

# 5b: timeout question left a durable terminal answer (contract 6)
assert_contains "fake agent: durable timeout answer for q2" \
    "$(cat "$FAKE_DIR/answer-2.json" 2>/dev/null || true)" '"timeout"'

# 5c: payload landed and validates via the shared schema
PAYLOAD_CONFORM="$("$PYTHON" - "$PROJECT_DIR" "$FAKE_DIR/payload.json" <<'PYEOF'
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / ".aitask-scripts"))
from chatlink.relay import TaskPayload
p = TaskPayload.from_dict(json.load(open(sys.argv[2])))
ok = (p.session_id == "sfake01" and "renderer" in p.description
      and "timed out" in p.description)
print("PAYLOAD_OK" if ok else "PAYLOAD_BAD")
PYEOF
)"
assert_eq "fake agent: payload validates + carries Q&A outcomes" \
    "PAYLOAD_OK" "$PAYLOAD_CONFORM"

# ---------------------------------------------------------------------------
echo ""
echo "PASS: $PASS_COUNT, FAIL: $FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ] && [ "$PART1_OK" -eq 1 ]
