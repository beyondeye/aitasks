---
Task: t1705_2_framework_session_store.md
Parent Task: aitasks/t1705_frozen_codeagents_session_store_and_viewer_tui.md
Sibling Tasks: aitasks/t1705/t1705_10_freeze_restore_workflow_docs.md, aitasks/t1705/t1705_11_manual_verification_frozen_codeagents_session_store_and_view.md, aitasks/t1705/t1705_3_session_id_capture_hooks.md, aitasks/t1705/t1705_4_freeze_engine.md, aitasks/t1705/t1705_5_restore_and_repick_flows.md, aitasks/t1705/t1705_6_frozenagent_viewer_tui.md, aitasks/t1705/t1705_7_monitor_minimonitor_frozen_rows.md, aitasks/t1705/t1705_8_frozen_agents_acceptance_test.md, aitasks/t1705/t1705_9_frozenagent_tui_docs.md
Archived Sibling Plans: aiplans/archived/p1705/p1705_1_spike_freeze_standin_and_session_id_capture.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-06 16:46
---

# t1705_2 — Framework session store

## Context

The machine-wide store of code-agent records (`~/.config/aitasks/agent_sessions.json`)
that every later t1705 child drives. Pure store + locked shell writer +
lock-free reader, mirrored on `lib/agent_marks.py` / `aitask_agent_marks.sh`.
The **PINNED contracts** block at the end of this plan is normative for the
schema, identity, conflict policy, lease, state machine, verbs, wire lines,
exit codes, purge policy and observation protocol. No tmux, no TUI —
implementable from any shell.

**This plan was re-verified against the codebase on 2026-09-06** (verify path,
`plan_verified` empty). The pinned block is unchanged in content — a byte diff
against the parent's §A–§D differs only in heading level. t1705_1's
`## Spike findings` amends §C/§D (children 4 and 5) and touches **nothing** in
§A, so this child's contracts stand as written *in content*. The verification
surfaced **sixteen** concrete corrections (A1–A16), recorded below and folded into
the steps; A7–A14 and A16 are blocking defects rather than tidy-ups. A12–A16 came
from review of the implemented code and were each reproduced before being
fixed. A16 is a defect in A13's own fix — evidence that a validation rule
needs its *own* review pass, not just the bug it was written for. A10 was found during implementation by tracing rule 1 against the
purge rule — the same cross-section reading that found A3 and A4.

## Plan verification (2026-09-06) — amendments

**A1 — `agent_marks._read_observed` line reference is stale, and the edit is
smaller than the plan implies.** The function is at
`.aitask-scripts/lib/agent_marks.py:587-620`, not `:623-654` (those lines are
`_cli_cycle`). Every other reference-pattern line range checks out: `_parse`
:209-270, `load`/`load_safe` :273-305, `_target_mode`/`dump` :308-362,
`mark_key` :176-184, `sweep_liveness` :440-478, `MarksView` :506-584, CLI `main`
:658-684. More importantly, its parser is an `if/elif` chain over `parts[0]`
with **no else** — an unrecognized row kind is *already* dropped silently, so a
`PANE` row is a no-op there today. The deliverable is therefore an explicit
`elif kind == "PANE": continue` plus the docstring row, and — the real content —
the regression test in `tests/test_agent_marks_liveness.py` that pins the
behaviour so a future `else: raise` cannot break the shared observation file.

**A2 — `dump()` must not use bare `atomic_write_text`.**
`atomic_write.target_mode()` (`lib/atomic_write.py:62-73`) returns
`0o666 & ~umask` for a file that does not exist yet — **not** 0600. Routing
`dump()` through `atomic_write_text` would land the first-ever store at 0644
under the default umask, and this file holds transcript paths and codeagent
session ids; the PINNED contract says 0600. Use the split API so the mode is set
on the temp **before** the rename (no window where the store is world-readable):

```python
resolved = os.path.realpath(sessions_path(path))          # prepare() does not follow symlinks
mode = _target_mode(resolved)                             # existing st_mode, else _FILE_MODE (0o600)
tmp = atomic_write.prepare(resolved, render)
os.chmod(tmp, mode)
atomic_write.commit(tmp, resolved)
```

Same class of trap for `capture_dir()`: `os.makedirs(..., mode=0o700)` has its
mode masked by the umask, so follow it with an explicit `os.chmod(d, 0o700)`.

**A3 — `standin_respawned` must also be legal from `freezing`.** PINNED §C's
reconcile table has the row
`freezing | @aitask_frozen==id, pane dead | respawn the stand-in (clear ready first), standin-respawned, then re-check`
— it calls the verb on a `freezing` record. But §A's verb description and this
plan's step-4 legal-from table admit only `aborting` and `frozen`, so
implementing the table as written makes that reconcile row fail with
`TRANSITION_REFUSED` when child 4 lands. Resolution (additive, nothing else
changes): **`freezing → freezing`** — records `standin_pid` / `pane_id` /
`pane_pid` and **keeps** the lease, because the freeze is still in flight; the
re-check then matches the `freezing` + stand-in-up row and commits. Propagate to
the parent plan's §A verb list and to `aiplans/p1705/p1705_4_freeze_engine.md`
in this task's commit, per the pinned block's own "on any discrepancy" rule.

**A4 — `upsert` refusal wire lines, disambiguated.** §A states both
`UPSERT_REFUSED:<id>|<state>_unacknowledged` (rule 2, transitional records whose
pane is the caller's) and `UPSERT_REFUSED:<id>|<state>` (the "freezing / frozen"
other-branch), and the two overlap on `freezing`. Pin one deterministic shape:
**select first, then gate on state.** A record is *selected* by `--id` (rule 1)
or by pane identity (rule 2); a record that merely shares `(root, window)` is
not a candidate at all and falls through to rule 3. Once selected:

| state | outcome |
|---|---|
| `live` | proceed (update / relocate; a differing `(root, window)` is written back and the slot re-allocated — A10) |
| `restoring` + `--restore-of` + `--nonce` | the ack path (§A) |
| `restoring` | `UPSERT_REFUSED:<id>\|restoring_unacknowledged` |
| `freezing` | `UPSERT_REFUSED:<id>\|freezing_unacknowledged` |
| `aborting` | `UPSERT_REFUSED:<id>\|aborting_unacknowledged` |
| `frozen` | `UPSERT_REFUSED:<id>\|frozen` |

The `frozen` row is exactly §A's "a hook firing in a stand-in pane is a bug":
the stand-in pane carries `@aitask_record`, so it arrives via `--id`. The one
behavioural consequence is that `freezing` refuses with
`freezing_unacknowledged`, not `freezing`. Propagate to the parent §A.

**A5 — `agent_kind` has no Python derivation helper.**
`lib/agent_string.sh:48 parse_agent_string` is bash-only and `die`s on a
malformed string; there is no Python equivalent anywhere under
`.aitask-scripts/`. Derive it locally and non-fatally:

```python
_AGENT_STRING_RE = re.compile(r"([a-z]+)/[a-z0-9_]+")
m = _AGENT_STRING_RE.fullmatch(agent_string or "")
agent_kind = m.group(1) if m else ""
```

Do **not** validate against `SUPPORTED_AGENTS`: the field is display-only and
the store must not reject a record because a new agent shipped.

**A6 — the `session` field needs a flag to be writable.** The PINNED schema
carries `"session"` (tmux session name, display only) but no wrapper verb sets
it, so it would be permanently `""`. Add an optional `--session <name>` to
`upsert` (and the matching `session=None` kwarg). This is additive — it makes an
existing pinned field writable rather than changing the schema. `list`'s wire
line is unchanged (it does not carry `session`); `show` prints it.

**A7 — the lease-minting verbs must carry the coordinator pid explicitly
(blocking).** §A says `freeze-begin`, `restore-begin` and `lease-take` "record
`op_owner_pid` (**the coordinator**)", and §C repeats it (`op_owner_pid` = this
coordinator). But **none of the three wrapper forms has an argument for it**
(§A's verb list: `freeze-begin <id> --capture-ansi … --lines <n> [--phase <t>]`,
`restore-begin <id> --mode resume|repick`, `lease-take <id>`). The module-layout
signatures do take `owner_pid`, so with no flag to supply it the wrapper would
fall back to its own `$$` / `os.getpid()` — and that process **exits the instant
the verb returns**, while the real coordinator (`aitask_frozen.sh`, detached via
`run-shell -b`) keeps working.

This does not merely lose information; it inverts the design. `_lease_stale` is
`op_started_at + STALE_OP_GRACE_DEFAULT < now and not pid_alive(op_owner_pid)` —
with an always-dead pid the conjunction collapses to a bare 60 s timer, so after
the grace `reconcile` seizes a lease that §C says it must never touch ("Within
the grace, or with a live owner, reconcile leaves the record alone"; "a
`LEASE_HELD` answer means a live coordinator owns it and reconcile skips"). It
then issues recovery actions against a live operation: respawning the stand-in
over an in-flight restore, or `freeze-abort`ing a freeze that is still
capturing. The coordinator's next verb fails `NONCE_MISMATCH` and bails, so the
user's freeze or restore silently loses. And 60 s is well inside normal runtime:
spike finding 5b requires the freeze flow to **let the agent persist before
respawning its pane**, and §C's own indeterminate row waits `stale_op_grace × 2`.

Fix: `--owner-pid <pid>` becomes a **required** argument on `freeze-begin`,
`restore-begin` and `lease-take`; the wrapper validates it as a positive integer
and exits 2 otherwise (never defaulting to `$$` — a silent default is exactly
the failure above). The transition functions keep `owner_pid` required with no
default. Test: a lease minted with the pid of a process the test keeps alive is
**not** stale after the grace elapses, even though the process that ran the
wrapper is long gone; the same lease with a dead pid **is** stale. Propagate to
the parent §A verb list, and to `aiplans/p1705/p1705_4_freeze_engine.md` and
`aiplans/p1705/p1705_5_restore_and_repick_flows.md` (both are lease minters).

**A8 — `@aitask_record` stamping is the caller's obligation, not the store's
(blocking).** §A:265 says "In every create/update branch the caller's pane is
stamped `@aitask_record=<id>`", and the ack branch repeats it — in the passive
voice, inside the store's own section. But this module is tmux-free by
construction ("No tmux, no TUI — implementable from any shell"), and the
framework permits raw `tmux` only from `lib/tmux_exec.py` / `lib/tmux_exec.sh`,
enforced by `tests/test_no_raw_tmux.sh`. So the store **cannot** perform that
side effect, and §B's table only hedges ("Set by `upsert` (hook or freeze
engine)") without assigning it. Left unassigned, a caller persists a record and
never establishes the pane→record join; the next `upsert` from that pane then
arrives with no `--id`, and after a tmux restart (fresh `pane_id`s) rule 2 has
nothing to match on — so the freeze engine's step-1 fallback creates a **second**
record for an already-recorded agent, or an ambiguous relocation picks the wrong
one.

Pin it: **the store never touches tmux. The caller stamps
`@aitask_record=<id>` on its own pane, through the tmux gateway, immediately
after a successful `UPSERTED:<id>|…` line** — the id in that wire line is what
makes this mechanically possible, and it is the caller (child 3's SessionStart
hook on the normal path, child 4's freeze engine on the fallback path) that owns
the pane. This child's deliverable for it is contract text, not code: state the
obligation in `aitask_agent_sessions.sh`'s header beside the exit-code contract,
and again in `lib/agent_sessions.sh` directly above `AIT_RECORD_OPTION` — which
exists precisely so shell callers can perform the stamp. The end-to-end
assertion that the pane option is actually set belongs to child 3's hook tests
and to `t1705_8_frozen_agents_acceptance_test`. Propagate the assignment to the
parent §A/§B and to `aiplans/p1705/p1705_3_session_id_capture_hooks.md` and
`aiplans/p1705/p1705_4_freeze_engine.md`.

**A9 — record ids and nonces must be validated as canonical 8-hex (blocking).**
§A documents `id` as "8 hex, `os.urandom`" and `op_nonce` as "8 hex", but step 1
requires only that fields be *type*-checked. Format is load-bearing here because
both values escape the store into two dangerous sinks:

- `capture_dir(id)` → `<frozen root>/<id>/`, and `drop` "also removes
  `capture_dir(id)`". An `id` containing `../` — from a hand-edited store, or
  from `--id` fed off a pane option a user can set with `tmux set-option -p` —
  makes that deletion escape the frozen root.
- `standin_command(id)` → `ait frozenagent --record <id>`, which §C step 5 hands
  to `respawn-pane -k -t <pane> '<cmd>'`, i.e. a **shell command string**. A
  quote plus metacharacters in `id` is command injection into the respawn.

`os.urandom(4).hex()` can only ever emit `[0-9a-f]{8}`, so a well-formed store is
safe — but `load()`'s whole posture is that the store is untrusted input (an
unknown `state` is corruption, not a default), and `--id` / `--nonce` /
`--restore-of` are CLI boundaries fed from pane options. Fix:

- `_parse` rejects any `id` or `op_nonce` not matching `^[0-9a-f]{8}$` (empty
  `op_nonce` stays legal — it means "no lease") with `MalformedSessionsError`.
- the wrapper validates `--id`, `--nonce` and `--restore-of` against the same
  pattern and exits 2 on a mismatch, **before** the value reaches Python.
- `capture_dir()` asserts, defensively, that
  `os.path.realpath(d).startswith(os.path.realpath(frozen_root) + os.sep)` and
  raises otherwise — so a future caller that bypasses the boundary checks still
  cannot delete outside the root.
- tests: a store carrying `"id": "../../etc"` fails to load; `--id ../../x`
  exits 2; `capture_dir` raises on an injected traversal id; `standin_command`
  round-trips only hex ids.

**A10 — a renamed window must be written back to its record (found during
implementation; blocking).** §A rule 1 says `--id` selects "that record,
whatever its `(root, window)` (a renamed window keeps its record)". Implemented
literally — select by id, update pane and descriptive fields, leave `root` /
`window` alone — the record *is* kept, and looks entirely healthy: still `live`,
still pointing at the right pane. The damage lands one purge later. The liveness
rule drops a `live` record whose `(root, window)` is absent from a successfully
enumerated root, so a record still naming the pre-rename window is dropped as
`dead_window`, and the agent silently becomes unfreezable and unrestorable.

Reproduced before fixing: rename → `upsert --id` → purge against an observation
naming the new window → `DROPPED:<id>|dead_window`.

Fix: on the selected path, when the caller's `(root, window)` differs from the
record's, write both back and **re-allocate `window_slot`** to the lowest unused
slot under the new pair — the old slot number is meaningless under a new key and
reusing it can collide with a record already sitting there. `id` is the schema's
declared PRIMARY KEY, so this is the reading that makes rule 1 true end to end;
`(root, window, window_slot)` remains the durable *lookup* identity for callers
that arrive without an id.

**A11 — `SessionMismatch` must persist before it reports (found during
implementation; blocking).** §A says the store "**persists** `last_error` (state
unchanged) and prints `RESTORE_SESSION_MISMATCH:<id>` exit 7", and §D has the
coordinator poll `show <id>` until `last_error` carries the current nonce. The
transition did mutate the record before raising — but the CLI's exception
handler returned the exit code for *every* refusal without dumping, so the
mutation was computed and then discarded. Exit 7 was reported; `last_error`
stayed empty.

This is a different defect class from A1–A10: not a contract ambiguity but a
**layering gap**. The transitions are pure and their tests assert against the
in-memory store, so no unit test could see a CLI that decided correctly and
failed to persist. Found only by driving the shipped wrapper end to end.

Consequence if shipped: the hook's mismatch report never reaches the
coordinator, which waits out `restore_ack_grace` and takes the **liveness**
branch — confirming as `live` a pane running a *different* session than the one
being restored. That is exactly the outcome §A's mismatch check exists to
prevent, and §C's reconcile table calls out ("**never** liveness-confirm").

Fix: `SessionMismatch` gets its own handler that calls `dump()` before
returning 7; every other refusal keeps the write-nothing contract. Pinned by a
new `CliPersistenceTests` class that drives `main()` and reads the file back —
covering the persist-on-mismatch case and the write-nothing case for
`TRANSITION_REFUSED`, `NONCE_MISMATCH` and usage errors.

**A12 — `--pane` / `--pane-pid` must be a COHERENT pair, not merely both
present (review finding; blocking).** §A allows `""`/`0` "as a pair" and calls a
mismatched pair a usage error, but the wrapper only checked that both flags were
supplied. Reproduced: `freeze-commit --pane '' --pane-pid 123` **succeeded** and
persisted a frozen record with `pane_id=""`, `pane_pid=123`, `standin_pid=123` —
a live process at no pane at all. `freeze_commit` writes all three from that one
pair, so reconcile can never match the stored location against a real pane
again and the record is stranded in `frozen` with no way back. Exactly two
shapes are legal: `%N` + a positive pid, or `""` + `0`. Enforced in **both** the
wrapper and the Python CLI — the latter is a documented direct entry point, not
merely the wrapper's private backend.

**A13 — the lease triple must be coherent at parse (review finding; blocking).**
§A's schema says `op_owner_pid` is `0` only when there is no lease, but `_parse`
type-checked the fields independently. Reproduced: a record with
`op_nonce="11223344"` and `op_owner_pid=0` loaded fine and then read as **stale**
the moment the grace elapsed. That is the A7 failure reached through a
hand-edited store instead of through the wrapper — `_lease_stale` is
`grace elapsed AND owner dead`, and a zero pid is never alive. The same collapse
happens with an empty `op_started_at`, which epochs to `0.0` so the grace is
always long past. All three fields are written and cleared as a unit by
`_mint_lease` / `_clear_lease`, so the store now requires them all-set or
all-empty and treats a half-lease as corruption.

**A14 — an empty capture path is a MISSING capture (review finding; blocking).**
`purge` only checked `capture_ansi` when it was non-empty, so a frozen record
with `capture_ansi=""` survived every purge forever. Frozen records are
deliberately exempt from the `dead_window` and `dead_pane` rules, so nothing
else would ever collect it — and a frozen record with no capture path has
nothing to display and nothing to restore from, which is precisely what the
`capture_missing` rule exists to retire. Purged rather than rejected at parse:
one corrupt record must not make the whole store unreadable for every other
agent.

**A15 — the direct CLI path must bounds-check `--file` (review finding).**
`--file` is parsed *above* the try block, so `agent_sessions.py --file` with no
value raised an uncaught `IndexError` and handed automation a traceback instead
of the documented usage exit 2.

**A16 — a timestamp must PARSE, not merely be non-empty (review finding;
blocking).** A13 made the lease triple all-set-or-all-empty, but "set" was
checked as "non-empty string". `_epoch()` maps an unparseable stamp to `0.0`, so
a lease with a valid nonce and a *live* owner pid but
`op_started_at="not-a-timestamp"` loaded fine and read as **stale** on the first
check — a grace measured from epoch 0 has always elapsed. Reconcile would then
take over an operation a live coordinator still owns: the same fail-open outcome
as A13's zero pid, reached through the third field of the same triple.
Reproduced before fixing.

Fixed as a **class rather than an instance**: every timestamp field
(`op_started_at`, `state_at`, `started_at`, `frozen_at`) must be empty or match
`_TS_FMT` exactly. All four are written by `_iso()`, which emits nothing else,
so any other value is a hand-edit — and `state_at` is not safely "display only"
either, since §C/§D measure `restore_ack_grace` from it. The regression tests
cover obvious garbage *and* the plausible near-misses that a hand-edit actually
produces (`2026-01-01 00:00:00`, a missing `Z`, an explicit `+00:00` offset, an
out-of-range month).

**Out of scope, flagged only:** `aiplans/p1705/p1705_5_restore_and_repick_flows.md`
still describes the `env VAR=… <cmd>` prefix (lines 87, 470) and does not carry
t1705_1's spike finding 2 ("prefer `respawn-pane -e`"). §D as reproduced in the
pinned block below is likewise pre-spike. This child implements no part of §D,
and t1705_5's own verify pass owns the amendment — noted here so it is not lost.

## Files

- **New** `.aitask-scripts/lib/agent_sessions.py`
- **New** `.aitask-scripts/aitask_agent_sessions.sh` (sole writer)
- **New** `.aitask-scripts/lib/agent_sessions.sh` (constants + capture-dir resolver + the `ait_stamp_record` helper of §C5, for shell callers)
- **Edit** `.aitask-scripts/lib/agent_marks.py` — `_read_observed` (**:587-620**, see A1) skips `PANE` rows explicitly
- **Edit** `aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md` §A/§B — amendments A3, A4, A6, A7, A8, A9
- **Edit** `aiplans/p1705/p1705_3_session_id_capture_hooks.md` — amendment A8 (the hook is the normal-path stamper)
- **Edit** `aiplans/p1705/p1705_4_freeze_engine.md` — amendments A3, A7, A8 (its reconcile table is the caller)
- **Edit** `aiplans/p1705/p1705_5_restore_and_repick_flows.md` — amendment A7 (it mints a restore lease)
- **New tests** `tests/test_agent_sessions.py`, `tests/test_agent_sessions_identity.py`,
  `tests/test_agent_sessions_transitions.py`, `tests/test_agent_sessions_lease.py`,
  `tests/test_agent_sessions_observation.py`, `tests/test_agent_sessions_liveness.py`,
  `tests/test_agent_sessions_concurrency.sh`, `tests/test_agent_sessions_stamp.sh`,
  `tests/test_agent_sessions_contract_call_sites.py`
- **Edit** `tests/test_agent_marks_liveness.py` — a `PANE` row in the observation file is ignored by the marks purge

No allow-list or `ait` dispatcher entries: verified against
`aidocs/framework/aitasks_extension_points.md` §"Adding a new helper script" —
the whitelist applies only to helpers invoked from a `SKILL.md` closure, and
these callers are Python TUIs, sibling scripts and the SessionStart hook.

## Module layout — `lib/agent_sessions.py`

```python
SESSIONS_ENV = "AITASKS_AGENT_SESSIONS_FILE"
DEFAULT_SESSIONS_PATH = "~/.config/aitasks/agent_sessions.json"
FROZEN_DIR_ENV = "AITASKS_FROZEN_DIR"
DEFAULT_FROZEN_DIR = "~/.config/aitasks/frozen"
STANDIN_CMD_ENV = "AITASKS_FROZEN_STANDIN_CMD"          # test seam only
SCHEMA_VERSION = 1
OLDEST_READABLE_VERSION = 1
STATES = ("live", "freezing", "frozen", "restoring", "aborting")
_FILE_MODE = 0o600; _DIR_MODE = 0o700
STALE_OP_GRACE_DEFAULT = 60.0

@dataclass
class SessionRecord:  # every field of the PINNED schema, same names, same defaults
    ...

class MalformedSessionsError(Exception): ...
class TransitionRefused(Exception): ...   # exit 5
class NonceMismatch(Exception): ...       # exit 6
class SessionMismatch(Exception): ...     # exit 7 — the store has ALREADY persisted last_error when this is raised
class LeaseHeld(Exception): ...           # exit 8

def record_key(root, window, slot) -> tuple[str, str, int]   # realpath(root) both sides
def load(path=None) -> SessionsFile        # raises MalformedSessionsError; missing/empty file = empty store
def load_safe(path=None) -> SessionsFile   # never raises
def dump(sf, path=None) -> None            # atomic_write prepare/chmod/commit — see A2
def standin_command(record_id) -> str      # "ait frozenagent --record <id>" unless STANDIN_CMD_ENV
def capture_dir(record_id) -> Path         # makedirs + explicit chmod 0o700 (A2); asserts containment (A9)

_ID_RE = re.compile(r"[0-9a-f]{8}")        # A9 — canonical record id / op_nonce
def valid_id(s) -> bool                    # _ID_RE.fullmatch; "" is a valid EMPTY nonce, never a valid id

# transitions — pure: (sf, **args) -> (sf, wire_line); the shell wrapper serialises + dumps
def upsert(sf, *, root, window, pane, pane_pid, id=None, session=None, session_id=None,
           transcript=None, agent_string=None, operation=None, task_id=None,
           restore_of=None, nonce=None, now=None, pane_alive=None) -> (sf, str)   # --session per A6
def freeze_begin(sf, id, *, capture_ansi, capture_txt, lines, phase="", owner_pid, now) -> (sf, str)
def freeze_commit(sf, id, *, nonce, pane, pane_pid, now) -> (sf, str)
def freeze_abort(sf, id, *, nonce, now) -> (sf, str)
def restore_begin(sf, id, *, mode, owner_pid, now) -> (sf, str)
def restore_launched(sf, id, *, nonce, pane, pane_pid, now) -> (sf, str)
def restore_confirm(sf, id, *, nonce, pane, pane_pid, now) -> (sf, str)
def restore_abort(sf, id, *, nonce, now) -> (sf, str)
def standin_respawned(sf, id, *, nonce, pane, pane_pid, now) -> (sf, str)
def lease_take(sf, id, *, owner_pid, now, pid_alive=None) -> (sf, str)
def drop(sf, id) -> (sf, str)              # also removes capture_dir(id)
def purge(sf, observed: Observation) -> (sf, list[str])

class Observation: roots, windows{root: set}, panes{(root, window): [(pane_id, pane_pid, pane_dead)]}, complete, pane_complete{root: bool}
def read_observation(path) -> Observation  # ROOT / WINDOW / PANE / INCOMPLETE

class SessionsView: same shape as MarksView (mtime+size+inode), .records(), .frozen(), .by_id(), .invalidate()
```

`pane_alive` / `pid_alive` are injectable predicates (default `os.kill(pid, 0)`
with `ESRCH` → dead, anything else → alive) so tests never depend on real pids.

## Implementation steps

1. **Schema + parse/dump.** Copy the strictness of `agent_marks._parse`
   (:209-270): top-level dict, int `version` in
   `[OLDEST_READABLE_VERSION, SCHEMA_VERSION]`, `sessions` list, every field
   type-checked, unknown `state` → `MalformedSessionsError`, duplicate `id`
   → first wins. `dump` sorts by `(root, window, window_slot)` with
   `sort_keys=True` for a stable byte image, and lands 0600 per **A2**.
   `agent_kind` is derived per **A5**. `id` and `op_nonce` are validated against
   `^[0-9a-f]{8}$` per **A9** (an empty `op_nonce` is legal — it means "no
   lease"; an empty `id` never is), and `capture_dir()` asserts containment
   beneath the resolved frozen root. Tests: round-trip, every rejection,
   empty/missing file = empty store, `load_safe` never raises, the
   **0600-under-permissive-umask** case from A2, and the A9 traversal cases
   (`"id": "../../etc"` fails to load; `capture_dir` raises on a traversal id;
   `standin_command` round-trips only hex ids).
2. **Identity + `upsert`.** Implement the four-rule resolution from the PINNED
   block exactly, in order, including `ambiguous_relocation` (≥ 2 `live`
   dead-pane candidates → new slot, stale untouched), `created_slot<N>` (lowest
   unused slot), the **A4** select-then-gate refusal table, and the
   write-back of a changed `(root, window)` with slot re-allocation (**A10**),
   and the `--restore-of` ack branch (nonce check → `NonceMismatch`; `resume` mode
   session-id check → persist `last_error="<nonce>:session_mismatch"` **then**
   raise `SessionMismatch`; `repick` adopts; on success update
   `pane_id`/`pane_pid`, `state=live`, `ack=hook`, delete `capture_dir`, clear
   `capture_*`, clear lease). Wire lines exactly as PINNED, amended by A4.
   `--session` is accepted and stored (**A6**). Tests in
   `test_agent_sessions_identity.py` — one test per branch plus the negative
   controls (a single dead-pane candidate *is* relocated; a recycled `pane_id`
   on a fresh pane with no `--id` and no `(root, window)` match creates, never
   attaches) and one assertion per row of the A4 table.
3. **Lease.** `_mint_nonce()` = `os.urandom(4).hex()`; `_lease_stale(rec, now,
   pid_alive)` = `op_started_at + STALE_OP_GRACE_DEFAULT < now and not
   pid_alive(op_owner_pid)`. `lease_take` refuses with `LeaseHeld` unless no
   lease or stale. `_require_nonce(rec, nonce)` → `NonceMismatch`.
   `owner_pid` is **required, never defaulted**, on all three minting paths per
   **A7** — the wrapper supplies the *coordinator's* pid, not its own. Tests in
   `test_agent_sessions_lease.py`, including the A7 control: a lease whose
   `op_owner_pid` names a process the test keeps alive is **not** stale once the
   grace has elapsed (and the same lease with a dead pid **is**), which is the
   assertion that fails if `owner_pid` ever silently falls back to the helper's
   own pid.
4. **Transitions.** Legal-from table: `freeze_begin: live`;
   `freeze_commit/abort: freezing`; `restore_begin: frozen` (**not**
   `aborting`); `restore_launched/confirm/abort: restoring`;
   **`standin_respawned: freezing → freezing (lease kept, per A3) | aborting →
   frozen (lease cleared) | frozen → frozen (leased)`**; `lease_take: any state
   with no live lease`; `drop: any`. Everything else → `TransitionRefused` with
   the PINNED wire line. `restore_confirm` additionally requires
   `launch_pid != 0 and launch_pid == pane_pid` and sets `ack=liveness`,
   **keeps captures**. `freeze_abort` deletes captures. `freeze_commit` writes
   `frozen_at`, `standin_pid=pane_pid`, `pane_id=pane` (`""`/`0` allowed as a
   pair; a mismatched pair is a usage error in the wrapper). Tests in
   `test_agent_sessions_transitions.py` enumerate the full state × verb matrix.
5. **Observation + purge.** `read_observation` parses the four row kinds
   (tab-separated, unknown kinds → `MalformedSessionsError`), tracks per-root
   `pane_complete` (a root with a `WINDOW` row but no `PANE` row for that window
   is pane-incomplete). `purge`: `INCOMPLETE` → nothing; `live` + root
   enumerated + window absent → `dead_window`; `live` + window present + pane
   rows present + (pane absent or `pane_dead=1`) + `pid_alive(pane_pid)` false →
   `dead_pane`; `frozen` + capture file missing, **including an empty `capture_ansi`** (A14) → `capture_missing`;
   transitional states never purged. Make `agent_marks._read_observed`
   (**:587-620**) skip `PANE` lines explicitly per **A1**, keeping its
   `INCOMPLETE`/`ROOT`/`WINDOW` semantics byte-for-byte, and add the regression
   test to `tests/test_agent_marks_liveness.py`. Tests in
   `test_agent_sessions_observation.py` / `_liveness.py`.
6. **`SessionsView`** — copy `MarksView` (:506-584) including the inode
   rationale comment; `frozen()` and `by_id()` helpers.
7. **Shell wrapper** `aitask_agent_sessions.sh` — copy `aitask_agent_marks.sh`'s
   skeleton: `SESSIONS_FILE="${AITASKS_AGENT_SESSIONS_FILE:-$HOME/.config/aitasks/agent_sessions.json}"`,
   `LOCK_DIR="${SESSIONS_FILE}.lockd"`, `lock_or_busy` (never proceed unlocked;
   `mkdir -p "$(dirname "$LOCK_DIR")"` first, as the marks wrapper does at
   :87), `run_py` merging stderr into stdout, verbs dispatched to
   `"$(require_ait_python)" lib/agent_sessions.py --file "$SESSIONS_FILE" <verb> …`
   which does load → transition → dump → print wire line, mapping exceptions to
   exit codes 4/5/6/7/8. `list`/`show` bypass the lock (2 s keypress timeout for
   mutating verbs, 10 s for `purge`). Argument validation in the wrapper, all
   exit 2: `--pane`/`--pane-pid` pairing; `--owner-pid` **required** on
   `freeze-begin` / `restore-begin` / `lease-take` and a positive integer, with
   no `$$` fallback (**A7**); `--id` / `--nonce` / `--restore-of` matching
   `^[0-9a-f]{8}$` before the value reaches Python (**A9**). The header comment
   carries the exit-code contract **and** the A8 stamping obligation: the store
   never touches tmux, so the caller stamps `@aitask_record=<id>` on its own
   pane via the tmux gateway immediately after a successful `UPSERTED:` line.
   `shellcheck` clean.
8. **`lib/agent_sessions.sh`** — `AIT_RECORD_OPTION="@aitask_record"`,
   `AIT_FROZEN_OPTION="@aitask_frozen"`,
   `AIT_STANDIN_READY_OPTION="@aitask_standin_ready"`,
   `AIT_AGENT_SESSION_OPTION="@aitask_agent_session"`, `ait_frozen_dir()`. The
   Python constants live in `monitor/monitor_core.py` beside
   `SHADOW_TARGET_OPTION` (**verified present at :385**); t1705_4 adds the four
   new ones. Write the shell↔Python spelling-parity test **now** against
   `lib/agent_sessions.py`'s own copies and let t1705_4 re-point it at
   `monitor_core`. Also ship **`ait_stamp_record <pane> <id>`** here per **A8 /
   §C5** — gateway-routed via `ait_tmux set-option -p`, mirroring
   `aitask_shadow_capture.sh:369`, guarded by the 8-hex check — so the stamping
   obligation is a function children 3 and 4 call rather than prose they must
   remember. Document the obligation directly above `AIT_RECORD_OPTION`. Test it
   without a live server (`tests/test_agent_sessions_stamp.sh`): a non-hex id
   returns 2 and emits no tmux call; a well-formed call emits exactly
   `set-option -p -t <pane> @aitask_record <id>` through the gateway.
9. **Concurrency suite** `tests/test_agent_sessions_concurrency.sh` — modelled
   on `tests/test_agent_marks_concurrency.sh`: N background `upsert`s on
   distinct windows + `wait`; assert record count and each payload once; a
   paused writer (`SIGSTOP`) makes a second `upsert` return `LOCK_BUSY` within
   the 2 s budget; `list` returns during the pause (no lock). Scope everything
   to a temp store via `AITASKS_AGENT_SESSIONS_FILE`. Per CLAUDE.md, this file's
   test bodies must **not** run in `( … )` subshells unless it opts into
   `assert_counters_init` / `assert_counters_load`.

10. **Propagate the amendments.** In the same commit, per the pinned block's "if
    a child must deviate, update the parent plan and every sibling plan in the
    same commit" rule:
    - parent plan `aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md`
      §A — A3, A4, A6, A7, A9; §A/§B — A8;
    - `aiplans/p1705/p1705_3_session_id_capture_hooks.md` — A8: the hook calls
      `ait_stamp_record` after a successful `UPSERTED:` line, **and owns the
      integration test that observes the option on a real pane**;
    - `aiplans/p1705/p1705_4_freeze_engine.md` — A3, A7 (its reconcile and
      freeze paths mint leases and must pass the coordinator pid), A8 (its
      fallback `upsert` stamps via `ait_stamp_record`);
    - `aiplans/p1705/p1705_5_restore_and_repick_flows.md` — A7;
    - `aitasks/t1705/t1705_8_frozen_agents_acceptance_test.md` — A8: the
      end-to-end run asserts `@aitask_record` is present on the agent pane after
      a real hook fire, and survives the freeze/restore cycle.

    Each propagation is a small edit to the sibling's own contract text, not a
    re-plan; §C1–C5 above is the text to copy from.

### Post-phase (risk mitigations)

- **`contract_call_site_audit`** — new `tests/test_agent_sessions_contract_call_sites.py`.
  Transcribe PINNED §C's reconcile table and §D's restore flow into a literal
  data table of `(record state, verb, args, expected outcome)` tuples — one row
  per invocation those sections name — and check each row against **§C1–C4**,
  which is the authoritative contract this audit enforces (the PINNED block is
  provenance, not spec). Assert **two** things per row: (i) the `(state, verb)`
  pair is legal per §C3, and refused rows carry the §C2 wire line; (ii) the
  arguments the call site supplies are exactly what §C1 requires and accepts —
  every required flag present, no unknown flag, so a `freeze-begin` row lacking
  `--owner-pid` fails. Assertion (ii) is not optional and (i) is not sufficient:
  A3 is a state-legality defect, but A7 is an argument-shape one and would sail
  through a `(state, verb)`-only table. That is also why §C1 had to be written
  down — an audit with no authoritative argument contract has nothing to
  enforce. A row that cannot be satisfied is a contract bug to amend upstream
  (as A3 and A7 were), not a test to relax.
  **Known limit:** this audit is static — signatures and state legality over the
  pure transitions. It cannot catch a CLI layer that computes the right result
  and then fails to persist it (A11). `CliPersistenceTests` in
  `tests/test_agent_sessions.py` covers that layer; keep both.
- **`store_permissions_regression`** — extend `tests/test_agent_sessions.py`.
  Under `umask 000`, a first-ever `dump()` to a fresh path must land the store
  at `0600`; a store pre-created `0640` must keep `0640` after a `dump()`; and
  `capture_dir(<id>)` must land `0700` under the same umask. Guards the A2 trap
  against a future "simplify to `atomic_write_text`" refactor.

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests      # includes the six new modules
bash tests/test_agent_sessions_concurrency.sh
bash tests/test_agent_sessions_stamp.sh                   # §C5 helper, no live server
bash tests/test_no_raw_tmux.sh                            # the new .sh must stay gateway-only
bash tests/test_agent_marks_concurrency.sh                # unchanged behaviour
bash tests/test_agent_marks_liveness.py-equivalent: covered by the suite above
shellcheck .aitask-scripts/aitask_agent_sessions.sh .aitask-scripts/lib/agent_sessions.sh
export AITASKS_AGENT_SESSIONS_FILE=$PWD/.x.json
S=./.aitask-scripts/aitask_agent_sessions.sh
$S upsert --root "$PWD" --window agent-pick-1 --pane %9 --pane-pid $$   # UPSERTED:<id>|created
$S list && stat -f '%Lp' .x.json                                        # must print 600
$S freeze-begin <id> --capture-ansi /tmp/a --capture-txt /tmp/b --lines 1; echo "want 2: $?"   # A7: --owner-pid required
$S lease-take '../../x'; echo "want 2: $?"                              # A9: non-hex id refused
rm -rf .x.json .x.json.lockd; unset AITASKS_AGENT_SESSIONS_FILE
```

Read only the last line of the python-suite output for the verdict
(`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); an earlier
`Results: N passed, 0 failed` belongs to one script-style module, not the suite.
Piping discards the status — use `set -o pipefail` or check `${PIPESTATUS[0]}`.

Step 9 (Post-Implementation) handles commit and archival. The forward
coordination note to t1389 is **already present** (`aitasks/t1389_stamped_agent_and_task_pane_identity.md:105,113`
names t1705 and links back to this task file) — verified 2026-09-06, no action
needed.

## Risk

Levels below are the **post-augmentation** reassessment (the two confirmed
inline mitigations are already part of the plan above), per
`risk-evaluation.md`'s reassessment note.

### Code-health risk: low
- The change is almost entirely additive — three new files with no existing
  callers, mirroring a shipped, test-covered template (`lib/agent_marks.py` +
  `aitask_agent_marks.sh`). The only touch to load-bearing code is the
  `_read_observed` edit, which A1 established is a no-op made explicit and is
  pinned by a new regression test. · severity: low
  · → mitigation: inline post-phase store_permissions_regression
- `lib/agent_sessions.py` is a large single module (schema + identity + lease +
  state machine + observation + view + CLI), so its internal surface is wide
  even though its external blast radius is nil. Mitigated by the six-module test
  split, which mirrors how `agent_marks` splits store from liveness policy.
  · severity: low · → mitigation: none (accepted)

### Goal-achievement risk: high
- The PINNED block is declared "do not re-decide", yet it has now yielded **six**
  genuine internal inconsistencies (A3 `standin_respawned` from `freezing`, A4
  overlapping refusal wire lines, A6 an unwritable schema field, A7 lease-mint
  verbs with no way to pass the coordinator pid, A8 a tmux side effect assigned
  to a tmux-free module, A9 unvalidated identifiers reaching a `rmtree` path and
  a shell command string). Two independent passes over the same text found three
  each, with no sign of saturation — and A7 in particular would have shipped a
  lease that *looks* correct and silently degrades to a bare 60 s timer, letting
  reconcile fight a live coordinator. This child is the store every later child
  drives, and such defects surface only when those children are implemented.
  · severity: high · → mitigation: inline post-phase contract_call_site_audit
- Nothing consumes the store yet. Its contract is asserted only against its own
  tests here; the first real integration is child 4's freeze engine, so a verb
  that is individually correct but collectively unusable would pass this task's
  verification unchallenged. · severity: medium · → mitigation: none — already
  covered structurally by the decomposition: `t1705_8_frozen_agents_acceptance_test`
  owns the end-to-end freeze → reconcile → restore cycle against the real store.

**Why this was raised from `medium` to `high`.** The level tracks the *discovery
rate*, not the residue of the fixes. Every one of the six defects is now closed
in-plan and each was cheap and locally contained — but two passes finding three
apiece is evidence the defect density is higher than any single pass detects,
and the pinned block's own governing instruction ("do not re-decide") actively
discourages the scrutiny that keeps finding them. That is a shaky core
assumption — that the pinned contract is settled — rather than a bounded
localized risk, which is `high` by the rubric. It does not change the work: the
two mitigations were already confirmed and are folded in above.

**Scope note on `contract_call_site_audit`.** A7 is an *argument-shape* defect,
not a state-legality one: `standin-respawned` from `freezing` (A3) would fail a
`(state, verb)` table, but a `freeze-begin` missing `--owner-pid` would pass one.
The audit table therefore asserts **both** — that each §C/§D call site's
`(state, verb)` pair is legal **and** that the arguments it supplies are exactly
the ones the verb requires and accepts (every required flag present, no unknown
flag). Without that second assertion the mitigation would not have caught the
defect that motivated raising this level.

### Planned mitigations
- timing: post-phase | name: contract_call_site_audit | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement risk 1 (pinned-block internal inconsistencies) | desc: table-driven test asserting every §C/§D `aitask_agent_sessions.sh` call site is both state-legal and argument-shape-correct against the implemented verbs
- timing: post-phase | name: store_permissions_regression | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (the A2 `atomic_write.target_mode` umask trap) | desc: assert the store lands 0600 on a first write under `umask 000`, preserves an existing mode, and that `capture_dir()` lands 0700
## Implementation notes (2026-09-06)

All ten steps and both post-phase mitigations landed as planned. Deviations and
findings worth carrying forward:

- **A1 was smaller than planned, as predicted.** `agent_marks._read_observed`
  already dropped unknown row kinds silently, so the code change is an explicit
  `elif kind == "PANE": continue` plus the docstring row. The real deliverable is
  the pair of regression tests in `tests/test_agent_marks_liveness.py` — one
  pinning that `PANE` rows are ignored, one pinning that a `PANE` row never
  *invents* a window (which would make a genuinely dead window look observed and
  defeat the marks sweep).
- **A2's control is only meaningful under `umask 000`.** At the default 022 a
  broken implementation yields 0644, which looks merely odd; at 000 it yields
  0666 and the intent is unmistakable. Verified by mutation: routing `dump()`
  through `atomic_write_text` makes `StoreModeTests` fail with `420 != 384`.
- **`_target_mode` is local, not `atomic_write.target_mode`.** The shared helper
  defaults a not-yet-existing file to `0o666 & ~umask`; the store needs 0600.
  The mode is applied to the staged temp *before* `commit`, so there is no window
  in which the store is world-readable.
- **A7 needed a discriminating test, not just a passing one.** A lease minted
  with `os.getpid()` passes even under a timer-only implementation, because the
  test process is alive. The control is
  `test_a_live_foreign_owner_is_never_stale`, which owns a real child process:
  mutating `_lease_stale` to ignore the owner fails 2 tests.
- **`LEASE_HELD` is not a contract violation.** The call-site audit treats it as
  a legitimate §C answer ("a live coordinator owns it and reconcile skips"),
  not a refused transition. Only `TRANSITION_REFUSED` fails a row.
- **State is checked before the nonce**, deliberately: `TRANSITION_REFUSED`
  (exit 5) means "wrong state, retry is pointless" while `NONCE_MISMATCH`
  (exit 6) means "reconcile got here first", and they route a coordinator down
  different recovery branches. Pinned by
  `test_state_is_checked_before_the_nonce`.
- **Both mitigations were mutation-verified**, each against the defect class it
  was written for: removing the A3 `freezing` edge fails the audit's state-legality
  assertion; making `owner_pid` defaultable fails its argument-shape assertion.
  Neither assertion catches the other's defect, which is why the audit needs both.
- **shellcheck parity**: `aitask_agent_sessions.sh` emits only the same three
  SC1091 source-follow infos the shipped `aitask_agent_marks.sh` does.
  `lib/agent_sessions.sh` carries three `SC2034` disables for constants consumed
  by children 4/6/7, following the `lib/agent_string.sh` precedent.
- **A10 was found by tracing rule 1 against the purge rule**, not by running
  anything — the same cross-section reading that produced A3 and A4, which is
  the argument for `contract_call_site_audit` existing at all. Its end-to-end
  test initially passed VACUOUSLY: the fixture's `self.root` was the raw temp
  path while records store `realpath`, so on macOS (`/var` → `/private/var`) the
  purge skipped the root entirely and dropped nothing. Fixed the fixture; all
  three A10 tests now fail under mutation.

- **A11 exposed a blind spot in `contract_call_site_audit`.** That mitigation
  checks signatures and state legality — both static properties of the pure
  transitions — so it cannot see a CLI that decides correctly and then fails to
  persist. Nothing in the planned test set drove the shipped wrapper end to end;
  A11 was found by hand, running the real `aitask_agent_sessions.sh` and reading
  the store back. `CliPersistenceTests` now closes that layer: it drives
  `main()` and asserts against the file on disk, for both the persist-on-
  mismatch case and the write-nothing cases. Worth carrying into children 4/5:
  a pure-function test suite over this store proves less than it appears to.

- **A12–A16 all shared one shape: a rule stated in prose but enforced only
  partially.** The pair rule checked presence but not coherence; the lease
  fields were type-checked but not checked *against each other*; the capture
  rule guarded a path it never applied to the empty case; the `--file` parse sat
  outside the handler that was supposed to catch it. None is a contract
  ambiguity — the contract was clear in all four cases — which is why the
  call-site audit could not have found them either. What found them was reading
  the implemented code against the contract, and the lesson for children 4/5 is
  that "the contract says X" and "the code enforces X" need separate checks.
  A16 sharpens it further: it is a hole in A13's *own* fix, so a newly added
  validation rule deserves the same scrutiny as the code it guards.

- **Propagation (step 10) also reached `aitasks/t1705/t1705_8_*.md`**, not just
  the plans: the observing "is `@aitask_record` really on the pane" assertion
  needs a live agent, which only that acceptance task has.

## Verification results (2026-09-06)

- **New/changed modules: 235 tests, all pass.** `test_agent_sessions` (63),
  `_identity` (26), `_transitions` (25), `_lease` (16), `_observation` (13),
  `_liveness` (18), `_contract_call_sites` (7), plus the unchanged
  `test_agent_marks` / `_liveness` (67).
- **Shell suites:** `test_agent_sessions_stamp.sh` 22/22,
  `test_agent_sessions_concurrency.sh` 20/20,
  `test_agent_marks_concurrency.sh` 25/25 (unchanged),
  `test_no_raw_tmux.sh` 5/5 — the new `.sh` files stay gateway-only.
- **shellcheck:** `aitask_agent_sessions.sh` emits only the same three SC1091
  source-follow infos the shipped `aitask_agent_marks.sh` does;
  `lib/agent_sessions.sh` is clean with three documented SC2034 disables.
- **Exit-code contract, driven through the real wrapper:** 2 / 5 / 6 / 7 / 8 all
  observed, and every refusal except `SessionMismatch` leaves the store
  byte-identical.

**Full suite: `PYTHON SUITE: FAILED (runner=unittest, exit=1)` — 6728 tests,
3 failures + 6 errors, ALL PRE-EXISTING.** Verified by stashing this task's
changes and re-running the failing modules on a clean tree; every one fails
identically without this work:

| module | on a clean tree |
|---|---|
| `test_agent_keys.RungTwoTest` (5 errors) | same 5 errors |
| `test_tmux_exec.TestGatewayIntegration` | same failure |
| `test_settings_project_config_value_types` | same failure |
| `test_prompt_scoping_live` (setUpClass) | same error |
| `test_codebrowser_startup_focus_live` | same failure |

The last two are live-TUI modules in CLAUDE.md's serial carve-out, which "fail
rather than skip" under a busy machine; this run was fully serial because the
pytest/xdist dev tier is not installed here (`ait setup --with-dev` installs it).
None of the nine touches `agent_sessions` or `agent_marks`.

## Corrected contracts — AUTHORITATIVE, supersedes the PINNED block below

The PINNED block is reproduced verbatim from the parent and is left unedited so
the provenance stays auditable. **Where this section and the PINNED block
disagree, this section wins** — it is what the implementer codes to and what
`contract_call_site_audit` enforces. Everything here is A1–A9 applied; nothing
else in the PINNED block changes.

### C1. Wrapper verb forms (replaces PINNED §A's verb list)

Every mutating verb takes the lock; `list` / `show` do not. Exit codes are
unchanged: `0` / `2` usage / `3 LOCK_BUSY` / `4 ERROR` / `5 TRANSITION_REFUSED`
/ `6 NONCE_MISMATCH` / `7 RESTORE_SESSION_MISMATCH` / `8 LEASE_HELD`.

```
upsert  --root <r> --window <w> --pane <id> --pane-pid <pid>
        [--id <rid>] [--session <name>] [--session-id <sid>] [--transcript <p>]
        [--agent-string <s>] [--operation <op>] [--task-id <t>]
        [--restore-of <rid> --nonce <n>]
          -> UPSERTED:<id>|created | updated | created_slot<N>
             | created_slot<N>|ambiguous_relocation | restored
             | UPSERT_REFUSED:<id>|<reason>            (reasons: see C2)

freeze-begin      <id> --owner-pid <pid> --capture-ansi <p> --capture-txt <p>
                       --lines <n> [--phase <t>]      -> FREEZING:<id>|<nonce>
restore-begin     <id> --owner-pid <pid> --mode resume|repick
                                                      -> RESTORING:<id>|<nonce>
lease-take        <id> --owner-pid <pid>              -> LEASED:<id>|<nonce>
                                                       / LEASE_HELD:<id> exit 8

freeze-commit     <id> --nonce <n> --pane <pane_id|""> --pane-pid <pid|0> -> FROZEN:<id>
freeze-abort      <id> --nonce <n>                                       -> LIVE:<id>
restore-launched  <id> --nonce <n> --pane <id> --pane-pid <pid>          -> LAUNCHED:<id>
restore-confirm   <id> --nonce <n> --pane <id> --pane-pid <pid>          -> LIVE:<id>|liveness
restore-abort     <id> --nonce <n>                                       -> ABORTING:<id>
standin-respawned <id> --nonce <n> --pane <id> --pane-pid <pid>          -> STANDIN:<id>
drop              <id>                                                   -> DROPPED:<id>
list  [--state <s>] [--root <r>]  -> SESSION:<id>|<state>|<root>|<window>|<pane_id>|<task_id>|<agent_string>|<state_at>
show  <id>                        -> KEY:value lines (includes `session`)
purge --observed <file>           -> DROPPED:<id>|<reason> … then PURGED:<n>
```

**`--owner-pid` is REQUIRED on exactly the three lease-minting verbs** and is
the pid of the **coordinator** — the detached `aitask_frozen.sh` process that
outlives the respawn — never the wrapper's or the Python helper's own pid. The
wrapper rejects a missing, non-numeric or non-positive value with exit 2 and
**has no `$$` fallback**: a default here is indistinguishable from a correct
call at the wire, and silently degrades `_lease_stale` to a bare 60 s timer
(A7). `--owner-pid` appears on no other verb — the leased verbs authenticate
with `--nonce` instead.

**Identifier arguments are validated before they reach Python** (A9):
`<id>`, `--id`, `--restore-of` and `--nonce` must match `^[0-9a-f]{8}$`, else
exit 2.

**`--pane` / `--pane-pid` is a coherent pair** (A12): exactly `%N` + a positive
pid, or `""` + `0` (the gone-pane commit). Both present but mismatched → exit 2.
Enforced in the wrapper **and** the Python CLI, which is a documented direct
entry point.

**`--file` is bounds-checked** (A15): a bare `--file` is exit 2, never a
traceback.

### C2. `upsert` refusal reasons (replaces the overlapping PINNED §A wording)

Select first — by `--id`, else by pane identity — then gate on state. A record
that merely shares `(root, window)` is not a candidate and falls through to the
create rules.

| selected record state | result |
|---|---|
| `live` | proceed (update / relocate) |
| `restoring` + `--restore-of` + `--nonce` | the ack path |
| `restoring` | `UPSERT_REFUSED:<id>\|restoring_unacknowledged` |
| `freezing` | `UPSERT_REFUSED:<id>\|freezing_unacknowledged` |
| `aborting` | `UPSERT_REFUSED:<id>\|aborting_unacknowledged` |
| `frozen` | `UPSERT_REFUSED:<id>\|frozen` |

### C3. State machine legal-from table (replaces PINNED §A's diagram edges)

| verb | legal from | lease |
|---|---|---|
| `freeze-begin` | `live` | mints |
| `freeze-commit` | `freezing` | clears |
| `freeze-abort` | `freezing` | clears |
| `restore-begin` | `frozen` (**not** `aborting`) | mints |
| `restore-launched` | `restoring` | keeps |
| `restore-confirm` | `restoring`, and `launch_pid != 0 and launch_pid == --pane-pid` | clears |
| `restore-abort` | `restoring` → `aborting` | keeps (same nonce) |
| `standin-respawned` | **`freezing` → `freezing` (keeps lease, A3)** \| `aborting` → `frozen` (clears) \| `frozen` → `frozen` (clears) | as noted |
| `lease-take` | any state with no live lease | mints |
| `drop` | any | n/a |

Anything else → `TRANSITION_REFUSED:<id>|<from>|<verb>`, exit 5, nothing written.

### C4. Schema field constraints (tightens PINNED §A's schema comments)

- `id` — **required** `^[0-9a-f]{8}$`. A record failing this is corruption:
  `load()` raises `MalformedSessionsError`, `load_safe()` returns empty.
- `op_nonce` — `^[0-9a-f]{8}$` **or** `""` (empty = no lease). Any other value
  is corruption.
- `op_nonce` / `op_owner_pid` / `op_started_at` — the lease **triple**: all
  three set, or all three empty (A13). A half-lease is corruption, because
  `_lease_stale` collapses to "stale" on any broken part and reconcile then
  steals a live coordinator's operation.
- **every timestamp** (`op_started_at`, `state_at`, `started_at`, `frozen_at`) —
  empty, or exactly `%Y-%m-%dT%H:%M:%SZ` (A16). Non-empty is not sufficient:
  `_epoch()` maps an unparseable stamp to `0.0`, which is the same fail-open as
  a missing one.
- `state` — one of `STATES`; unknown is corruption, never a default.
- `agent_kind` — derived, never stored by a caller: the prefix of
  `agent_string` when it matches `^[a-z]+/[a-z0-9_]+$`, else `""` (A5).
- `session` — free-form tmux session name, display only, written via
  `--session` (A6).

### C5. `@aitask_record` stamping — assigned, and single-sourced (A8)

The store performs **no** tmux side effect: `lib/agent_sessions.py` imports no
tmux and `tests/test_no_raw_tmux.sh` forbids raw `tmux` outside the gateways.
The stamp is the **caller's** obligation, performed **only after** a successful
`UPSERTED:<id>|…` line (never on a refusal, never before), on the caller's own
pane.

To make that mechanical rather than advisory, **this child ships the helper**
in `lib/agent_sessions.sh`, routed through the sanctioned shell gateway and
mirroring the existing `shadow_stamp_analyzed_at` precedent
(`aitask_shadow_capture.sh:369`):

```bash
# Stamp the pane->record join. Call ONLY after aitask_agent_sessions.sh printed
# UPSERTED:<id>|… — a stamp without a stored record is a dangling join, and a
# stored record without a stamp breaks the restart/restore identity handoff.
ait_stamp_record() {
    local pane="$1" record_id="$2"
    [[ "$record_id" =~ ^[0-9a-f]{8}$ ]] || return 2
    ait_tmux set-option -p -t "$pane" "$AIT_RECORD_OPTION" "$record_id"
}
```

Responsibilities, so no caller can read this as someone else's job:

| caller | when | child |
|---|---|---|
| SessionStart hook | after its `upsert` prints `UPSERTED:` (create, update **and** the `restored` ack branch) | t1705_3 |
| freeze engine | after its fallback `upsert` prints `UPSERTED:` (hook never fired) | t1705_4 |

**Tests.** This child asserts the helper's contract without a live server: the
non-hex-id guard returns 2 and emits no tmux call, and a well-formed call emits
exactly `set-option -p -t <pane> @aitask_record <id>` through the gateway (using
`AITASKS_TMUX_SOCKET` isolation, the same seam `tests/test_no_raw_tmux.sh`
assumes). The **observing** integration test — stamp present on the real pane
after a real hook fire — belongs to t1705_3's hook suite and to
`t1705_8_frozen_agents_acceptance_test`, which already own a live tmux server;
propagating A8 to those two plans (step 10) is what books that work.

## PINNED contracts (from p1705 — superseded above where they differ)

Copied verbatim from `aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md` §A–§D. On any discrepancy the parent plan wins; if a child must deviate, update the parent plan and every sibling plan in the same commit.


#### A. Session store — `lib/agent_sessions.py` + `aitask_agent_sessions.sh`

- Path `~/.config/aitasks/agent_sessions.json`, env override
  `AITASKS_AGENT_SESSIONS_FILE`, lock dir derived from the resolved path
  (`<file>.lockd`), 0600 with `_target_mode` preservation, write via
  `lib/atomic_write.py`. Captures under `~/.config/aitasks/frozen/<id>/`
  (0700 dir; `capture.ansi`, `capture.txt`), env `AITASKS_FROZEN_DIR`.
- Schema v1:
  ```json
  {"version": 1, "sessions": [{
    "id": "7f3a2c1d",                 // record id (8 hex, os.urandom) — PRIMARY KEY
    "root": "/real/path/project",     // realpath, both sides         ┐ DURABLE IDENTITY
    "window": "agent-pick-1705",      //                               │ (root, window, window_slot)
    "window_slot": 0,                 // assigned once; >0 only for a 2nd agent in the same window ┘
    "pane_id": "%104", "pane_pid": 41233,   // LOCATION / GENERATION data — replaceable, never identity
    "session": "aitasks",             // tmux session name — display only
    "operation": "pick", "task_id": "1705",          // task_id "" when unbound
    "agent_string": "claudecode/opus5", "agent_kind": "claudecode",
    "codeagent_session_id": "", "transcript_path": "",  // "" = unknown → re-pick only
    "started_at": "2026-09-04T09:12:03Z",
    "state": "live",                  // live | freezing | frozen | restoring | aborting
    "state_at": "2026-09-04T09:12:03Z",
    "op_nonce": "", "op_owner_pid": 0, "op_started_at": "",   // LEASE of the in-flight freeze/restore (see below)
    "frozen_at": "", "capture_ansi": "", "capture_txt": "",
    "capture_lines": 0, "last_phase": "",
    "standin_pid": 0,                 // #{pane_pid} of the stand-in viewer, written at freeze-commit and every stand-in respawn
    "launch_pid": 0,                  // #{pane_pid} of the replacement agent, written by restore-launched (nonce-bound)
    "restore_attempts": 0, "restore_mode": "",   // "" | resume | repick (current attempt)
    "ack": "",                        // "" | hook | liveness — how the last restore was confirmed
    "last_error": ""                  // "" | "<nonce>:session_mismatch" | "<nonce>:<reason>" — coordinator-readable outcome channel
  }]}
  ```
  `pane_id` / `pane_pid` are **location and generation data**: a tmux server
  restart, a reattach or a respawn replaces them on the same record. They
  are never part of the identity key and a recycled `%N` can attach to
  nothing on its own — attachment needs either `@aitask_record` on the pane
  (options die with the pane, so a recycled pane never carries a stale one)
  or a `(root, window)` match under the conflict policy below.
  Unknown `state` = corruption (not a default). `load()` raises
  `MalformedSessionsError`; `load_safe()` returns empty. Generation normalised
  to `SCHEMA_VERSION` on read.
- **Record ownership (one allocator) and the `(root, window)` conflict
  policy.** The `upsert` verb is the *only* creator of records. Resolution
  order for a caller without `--restore-of`:
  1. `--id <rid>` (from `@aitask_record` on the caller's pane) → that record,
     whatever its `(root, window)` (a renamed window keeps its record).
  2. Else, **among `live` records only** with the caller's `(root, window)`,
     the relocation candidates are: the one whose `pane_id` equals the
     caller's pane, else those whose `pane_pid` is dead or whose pane no
     longer exists. **Exactly one candidate** → it is the same agent slot:
     replace `pane_id`/`pane_pid`, update session id / transcript / agent
     string, print `UPSERTED:<id>|updated` (the tmux-restart and reattach
     case — no second record). **More than one candidate** (two agents shared
     the window before a server restart; nothing on the caller's side can
     tell them apart) → **fail closed on relocation**: fall through to rule 3
     and print `UPSERTED:<id>|created_slot<N>|ambiguous_relocation`; the stale
     records are left for purge (rule: a `live` record whose `pane_pid` is
     dead and whose `pane_id` is absent from an enumerated window →
     `DROPPED:…|dead_pane`), never guessed.
     Transitional records (`freezing`/`restoring`/`aborting`) are **never**
     relocated or updated by an unstamped caller: they are touched only by
     `--restore-of` + the current nonce, or by `reconcile`. If the caller's
     pane *is* a transitional record's pane → refuse
     (`UPSERT_REFUSED:<id>|<state>_unacknowledged`, a stray session in a
     transacting pane); otherwise they are simply not candidates.
  3. Else every `(root, window)` record is `live` in **another** pane (a
     second agent split into the same window), transitional, or `frozen`
     (retained state whose window name is being reused, e.g. the same task
     re-picked after a tmux restart) → **create beside it**: new record,
     `window_slot` = lowest unused slot for that `(root, window)`, print
     `UPSERTED:<id>|created_slot<N>`. A retained frozen record never blocks a
     live launch and is never attached to; it stays restorable into a fresh
     window (`unique_window_name` disambiguates) and is listed distinctly by
     its `frozen_at`.
  4. Else → create (`state=live`, `window_slot=0`), print `UPSERTED:<id>|created`.
  In every create/update branch the caller's pane is stamped
  `@aitask_record=<id>`.
  Other branches:
  - record exists in `restoring` **and** the caller passes
    `--restore-of <id> --nonce <n>` (the hook forwards them from the
    replacement agent's environment, §D) → the **restore acknowledgement**:
    nonce must equal `op_nonce`; in `resume` mode `--session-id` must equal
    `codeagent_session_id` — else the store **persists**
    `last_error="<nonce>:session_mismatch"` (state unchanged) and prints
    `RESTORE_SESSION_MISMATCH:<id>` exit 7. The hook has no return channel to
    the detached coordinator, so the record *is* the channel: the coordinator
    and `reconcile` both read `last_error` for the current nonce and take the
    abort branch, never the liveness fallback. In `repick` mode the new
    session id is adopted. On success: `pane_id`/`pane_pid` updated from the
    caller's pane, `@aitask_record` stamped on it, state `live`, `ack=hook`,
    capture files deleted, print `UPSERTED:<id>|restored`;
  - record exists in `restoring` without `--restore-of`/`--nonce` → refuse,
    print `UPSERT_REFUSED:<id>|restoring_unacknowledged` (a stray session in
    a restoring pane is never an ack);
  - record exists in `freezing` / `frozen` → refuse, print
    `UPSERT_REFUSED:<id>|<state>` (a hook firing in a stand-in pane is a bug).
  Two callers: the SessionStart hook (child 3, normal path) and the freeze
  engine (child 4, fallback when the hook never fired). Both read
  `@aitask_record` off the pane first and pass `--id` when present, so a pane
  that was already recorded is never duplicated even after a `pane_id`
  recycle. A restore into a **new** pane (window gone) carries the record id
  in the environment, never on the pane, so it selects the old record instead
  of creating a second one.
- **Operation lease.** `freeze-begin`, `restore-begin` and `lease-take` mint
  `op_nonce` (8 hex), record `op_owner_pid` (the coordinator) and
  `op_started_at`, and print the nonce. **Every verb that mutates a record
  holding a lease** (`freeze-commit`, `freeze-abort`, `restore-launched`,
  `restore-confirm`, `restore-abort`, `standin-respawned`, the ack form of
  `upsert`) requires `--nonce <n>`; a mismatch prints `NONCE_MISMATCH:<id>`
  exit 6 and writes nothing — a coordinator that lost the race to
  `reconcile` fails closed instead of double-acting. `lease-take <id>` →
  `LEASED:<id>|<nonce>` is how `reconcile` (or a stand-in relaunch on a
  `frozen` record) acquires ownership: it is refused (`LEASE_HELD:<id>`)
  while a lease exists whose `op_started_at` is younger than
  `stale_op_grace` (default 60 s) **or** whose `op_owner_pid` is alive; a
  stale lease with a dead/unverifiable owner is taken over. Within the grace,
  or with a live owner, reconcile leaves the record alone. Lease-clearing
  transitions (`freeze-commit`, `freeze-abort`, `restore-confirm`, hook ack,
  `standin-respawned` out of `aborting`) clear the lease.
- **State machine** (every transition is one locked verb; illegal transitions
  print `TRANSITION_REFUSED:<id>|<from>|<verb>` exit 5 and write nothing):
  ```
  live ──freeze-begin──▶ freezing ──freeze-commit──▶ frozen ◀────────────────┐
   ▲                        │                          │                      │
   └────freeze-abort────────┘                          │ restore-begin        │ standin-respawned
   ▲                                                   ▼                      │ (same nonce)
   └──upsert (hook ack) / restore-confirm── restoring ──restore-abort──▶ aborting
  drop: any state → record removed + capture files removed
  ```
  `aborting` is **nonce-owned**: the record stays leased by the aborting
  attempt until its stand-in is back (`standin-respawned --nonce` → `frozen`,
  lease cleared). `restore-begin` on `aborting` → `TRANSITION_REFUSED`, so a
  user or a second controller cannot start another restore in the gap and
  an old coordinator cannot respawn over a newer attempt: its `standin-respawned`
  carries a stale nonce and is refused.
  **Captures are deleted only on a verified ack** (`ack=hook`). A
  liveness-only `restore-confirm` transitions to `live` but **keeps** the
  capture files (`ack=liveness`); they are removed on `drop` or liveness
  purge. This is what stops a malformed resume that starts a fresh session
  from destroying the only copy.
- Wrapper verbs (sole writer; `list`/`show` take no lock; exit 0/2/3
  `LOCK_BUSY`/4 `ERROR`/5 `TRANSITION_REFUSED`/6 `NONCE_MISMATCH`/7
  `RESTORE_SESSION_MISMATCH`/8 `LEASE_HELD`):
  `upsert --root <r> --window <w> --pane <id> --pane-pid <pid> [--id <rid>] [--session-id <sid>] [--transcript <p>] [--agent-string <s>] [--operation <op>] [--task-id <t>] [--restore-of <rid> --nonce <n>]`;
  `freeze-begin <id> --capture-ansi <p> --capture-txt <p> --lines <n> [--phase <t>]` → `FREEZING:<id>|<nonce>`;
  `freeze-commit <id> --nonce <n> --pane <pane_id|""> --pane-pid <pid|0>` → `FROZEN:<id>` (writes the stand-in's location: `pane_id`/`standin_pid` from the arguments; `--pane "" --pane-pid 0` is the gone-pane commit used by reconcile; `--pane` without `--pane-pid` or vice versa → usage error exit 2);
  `freeze-abort <id> --nonce <n>` → `LIVE:<id>` (captures deleted);
  `restore-begin <id> --mode resume|repick` → `RESTORING:<id>|<nonce>` (captures **retained**, `restore_attempts`+1, `launch_pid=0`, `last_error=""`);
  `restore-launched <id> --nonce <n> --pane <id> --pane-pid <pid>` → `LAUNCHED:<id>` (records the replacement's `launch_pid` + location; written by the coordinator right after `respawn-pane`/`launch_in_tmux` returns — the nonce-bound evidence that the respawn happened);
  `restore-confirm <id> --nonce <n> --pane <id> --pane-pid <pid>` → `LIVE:<id>|liveness` (captures **kept**; refused with `TRANSITION_REFUSED` unless `launch_pid != 0` and equals `--pane-pid`);
  `standin-respawned <id> --nonce <n> --pane <id> --pane-pid <pid>` → `STANDIN:<id>` (records the stand-in's `standin_pid` + location; from `aborting` it also transitions to `frozen` and clears the lease; from `frozen` (a `lease-take`n relaunch of a dead stand-in) it just updates and clears the lease; `freeze-commit` folds the same write in);
  `restore-abort <id> --nonce <n>` → `ABORTING:<id>` (captures retained; lease kept by the same nonce);
  `lease-take <id>` → `LEASED:<id>|<nonce>` / `LEASE_HELD:<id>` exit 8;
  `drop <id>` → `DROPPED:<id>`;
  `list [--state <s>] [--root <r>]` → `SESSION:<id>|<state>|<root>|<window>|<pane_id>|<task_id>|<agent_string>|<state_at>`;
  `show <id>` → `KEY:value` lines;
  `purge --observed <file>` → `DROPPED:<id>|<reason>` + `PURGED:<n>`.
  **Observation protocol (superset of the marks one, backward-compatible):**
  ```
  ROOT<TAB><root>                                   -- successfully enumerated root
  WINDOW<TAB><root><TAB><window>                    -- observed agent window
  PANE<TAB><root><TAB><window><TAB><pane_id><TAB><pane_pid><TAB><pane_dead>   -- every pane of that window
  INCOMPLETE                                        -- suppress every sweep
  ```
  `monitor_shared._write_observation_file()` gains a `panes=` argument and
  writes the `PANE` rows from `TmuxMonitor.last_discovered_panes()` (the
  `_LIST_PANES_FORMAT` already carries `pane_id` and `pane_pid`; `pane_dead`
  is appended to the format — see §B arity rule). The marks reader
  (`agent_marks._read_observed`) is extended to **skip** `PANE` rows so one
  file serves both purges; `agent_sessions` requires them. A file with
  `ROOT`/`WINDOW` but no `PANE` rows for an enumerated root is treated as
  pane-incomplete for that root: `dead_window` still applies, `dead_pane`
  does not (fail closed).
- **Purge policy** (fail-closed on `INCOMPLETE`, mirrors `sweep_liveness`):
  a `live` record whose `(root, window)` is absent from a successfully
  enumerated root → `DROPPED:…|dead_window`; a `live` record whose window has
  a `WINDOW` row **and** `PANE` rows, but whose `pane_id` appears in none of
  them (or appears with `pane_dead=1`) and whose `pane_pid` is dead
  (`os.kill(pid, 0)` → `ESRCH`; an `EPERM`/unverifiable pid is treated as
  alive) → `DROPPED:…|dead_pane` — this is what retires the stale candidates
  left behind by an ambiguous relocation. Two producers feed `purge`: the
  monitor maintenance tick (observation file above) and `aitask_frozen.sh
  reconcile`, which builds the same file from its own `list-panes` pass so
  retirement does not depend on a TUI being open. `freezing` / `frozen` / `restoring` /
  `aborting` records are never purged by liveness — they are reconciled by
  `aitask_frozen.sh reconcile` (§C/§D). A frozen record whose capture file is
  missing → `DROPPED:…|capture_missing`.
- `SessionsView` (mtime+size+inode gated) for the TUIs; `invalidate()` after
  every write. `standin_command(record_id) -> str` returns
  `ait frozenagent --record <id>` unless `AITASKS_FROZEN_STANDIN_CMD` is set
  (documented **test seam**; production never sets it).

#### B. Pane options (tmux user options, pane-scoped)

| Option | Set by | Cleared by | Read by | Meaning |
|---|---|---|---|---|
| `@aitask_record=<id>` | `upsert` (hook or freeze engine) | `drop`; pane death | freeze engine, restore coordinator, hook (`--id`) | the pane-visible join to its store record |
| `@aitask_frozen=<id>` | freeze engine, immediately before `respawn-pane` | `restore-confirm` path (coordinator), `drop` | `_LIST_PANES_FORMAT` (appended), `kill_agent_pane_smart` format, `aitask_companion_cleanup.sh`, `maybe_spawn_minimonitor` occupancy | this pane is a frozen stand-in — **authoritative** classifier |
| `@aitask_standin_ready=<id>` | **the viewer itself**, after mount (only the app stamps its own pane — `mark_monitor_pane` rule) | freeze engine + restore coordinator (`set-option -pu`) immediately **before** every `respawn-pane`; `drop` | `reconcile` | positive proof that the stand-in is up — the only signal that distinguishes "stamped, viewer running" from "stamped, agent still running" |
| `@aitask_agent_session=<sid>` | SessionStart hook on `$TMUX_PANE` | pane death | freeze engine fallback when the store has no session id | codeagent session id |

**Pane user options survive `respawn-pane`** (they are pane-scoped, not
process-scoped), which is why `@aitask_standin_ready` must be explicitly unset
before each respawn and why `@aitask_record` stays valid across freeze/restore
on the same pane. `#{pane_current_command}` is a process basename and is
**never** used as identity; `#{pane_pid}` (stored as `pane_pid`) and the
options above are the only server-observable identities reconcile reads.

Constants live in `monitor/monitor_core.py` beside `SHADOW_TARGET_OPTION`
(`RECORD_OPTION`, `FROZEN_OPTION`, `STANDIN_READY_OPTION`,
`AGENT_SESSION_OPTION`) and are mirrored in `lib/agent_sessions.sh` for shell
callers.

#### C. Freeze — `lib/agent_freeze.py` + `aitask_frozen.sh freeze <pane>|--all`

Runs **out of the agent pane** (from a TUI, a shell, or `run-shell -b`).
Every step is persisted before the next irreversible one:

1. Resolve the record: `@aitask_record` → `show`; else `upsert` (fallback).
   Read `codeagent_session_id`; if empty, try `@aitask_agent_session`.
2. `capture-pane -p -e -J -t <pane> -S -<cap>` via `TmuxClient.run` →
   `capture.ansi`; strip via `monitor/ansi_utils` → `capture.txt`.
3. `freeze-begin` → state `freezing`, capture paths persisted, **lease
   minted** (`op_nonce`, `op_owner_pid`=this coordinator).
4. `set-option -p -t <pane> @aitask_frozen <id>`; `set-option -pu -t <pane>
   @aitask_standin_ready` (clear any stale ready mark from a previous cycle).
5. `respawn-pane -k -t <pane> '<standin_command(id)>'` via the gateway.
   Window name unchanged, so `classify_pane` / `task_id_from_window_name`
   keep working. The viewer stamps `@aitask_standin_ready=<id>` on mount.
6. `freeze-commit --nonce <n> --pane <pane> --pane-pid <stand-in pid>` →
   state `frozen`, `standin_pid` + location recorded (read via
   `display-message -p -t <pane> '#{pane_id}\t#{pane_pid}'` after the
   respawn), lease cleared.

Failure at 1–3 → nothing to undo beyond temp files (`FREEZE_FAILED:<stage>`).
Failure at 4 → `freeze-abort --nonce`. Failure at 5 (tmux refused) → unstamp +
`freeze-abort --nonce`; the agent is still running. Failure at 6 (store busy)
→ the record stays `freezing`; **reconcile** completes it once the lease is
stale. A `NONCE_MISMATCH` at 6 means reconcile already resolved the record;
the coordinator reports it and exits without touching the pane.

**`aitask_frozen.sh reconcile`** (idempotent; run by the coordinator after
every freeze/restore, by the monitor maintenance tick beside
`_maybe_purge_marks`, and manually) resolves every non-`live` record **whose
lease is stale** (`op_started_at` + `stale_op_grace` elapsed **and**
`op_owner_pid` dead/unverifiable — otherwise the record is skipped as
in-flight) from server-observable facts only
(`list-panes -F '#{pane_id}\t#{pane_pid}\t#{pane_dead}\t#{@aitask_frozen}\t#{@aitask_standin_ready}\t#{@aitask_record}'`;
"agent alive" = `pane_pid == record.pane_pid`; "viewer here" =
`pane_pid == record.standin_pid`; "replacement here" =
`pane_pid == record.launch_pid`; "stand-in up" = `@aitask_standin_ready == id`;
"mismatch" = `last_error` begins with the current `op_nonce`):

| record state | pane observation | action |
|---|---|---|
| `freezing` | `@aitask_frozen==id` **and** stand-in up | `freeze-commit --pane <pane> --pane-pid <observed pid>` |
| `freezing` | agent alive, stand-in not up | unstamp both options, `freeze-abort` (captures deleted) |
| `freezing` | `@aitask_frozen==id`, stand-in not up, neither agent nor viewer pid, pane not dead | **indeterminate — no transition** (viewer may still be booting); re-checked next pass |
| `freezing` | `@aitask_frozen==id`, pane dead | respawn the stand-in (clear ready first), `standin-respawned`, then re-check |
| `freezing` | pane gone | `freeze-commit --pane "" --pane-pid 0` |
| `frozen` | pane gone | keep (restorable into a new window) |
| `frozen` | `@aitask_frozen==id`, pane dead | `lease-take`, respawn the stand-in, `standin-respawned --nonce` |
| `restoring` | mismatch recorded for this nonce | `restore-abort` (→ `aborting`), kill the wrong agent via `respawn-pane -k` back to the stand-in, `standin-respawned --nonce` (→ `frozen`) — **never** liveness-confirm |
| `restoring` | viewer here (`pane_pid==standin_pid`) — the coordinator died before or during the respawn, whether or not the ready mark survived | `restore-abort`; respawn the stand-in so it re-stamps ready; `standin-respawned --nonce` |
| `restoring` | `launch_pid==0` and pane pid is neither the viewer's nor the agent's | **indeterminate — no transition** (respawn may be mid-flight); after `stale_op_grace` ×2 → `restore-abort` + respawn stand-in + `standin-respawned --nonce` |
| `restoring` | replacement here (`pane_pid==launch_pid`), pane not dead, no mismatch, `state_at` + `restore_ack_grace` (default 20 s) elapsed | `restore-confirm --pane --pane-pid` (`ack=liveness`, captures kept) |
| `restoring` | pane dead | `restore-abort`, clear ready, respawn the stand-in, `standin-respawned --nonce` |
| `restoring` | pane gone | `restore-abort` with `pane_id=""`, then `standin-respawned --nonce --pane "" --pane-pid 0` (→ `frozen`, restorable into a new window) |
| `aborting` (stale lease taken over) | stand-in up (`@aitask_standin_ready==id`) | `standin-respawned --nonce` (→ `frozen`) |
| `aborting` (stale lease taken over) | anything else | clear ready, respawn the stand-in, `standin-respawned --nonce` (→ `frozen`) |

Every reconcile action on a leased record is preceded by `lease-take`; a
`LEASE_HELD` answer means a live coordinator owns it and reconcile skips.

A liveness confirm therefore requires **positive evidence** that the
process in the pane is the one the coordinator launched (`launch_pid`), and
a viewer whose ready mark was cleared is still recognised by `standin_pid`.

Failure injection: `AITASKS_FREEZE_FAIL_AT=capture|begin|stamp|respawn|commit`,
`AITASKS_RESTORE_FAIL_AT=begin|respawn|ack`, and `AITASKS_FROZEN_PAUSE_AT=<stage>`
(the coordinator `SIGSTOP`s itself so a test can run a concurrent
`reconcile` and then `SIGCONT`) — documented test seams, honoured only under
`AITASKS_TEST_MODE=1`.

**Cleanup contract** (`aitask_companion_cleanup.sh` + `count_other_real_agents`
must agree — pinned by the parity test):
- a `@aitask_frozen`-stamped pane **counts as a real agent sibling** (the
  window exists to hold it; killing agent B must not destroy frozen A's viewer);
- when the *dying* pane is the stamped one, the cleanup script **abstains
  entirely** (it is being respawned, not departing);
- `kill_agent_pane_smart` on a frozen pane = `drop` + kill by the same rule.

#### D. Restore — `lib/agent_restore.py` + `aitask_frozen.sh restore <id> [--repick] | --all`

**Never runs inside the pane it replaces.** The viewer's `R`/`p` keys and the
minimonitor keys invoke `run-shell -b "<repo>/.aitask-scripts/aitask_frozen.sh restore <id>"`
through the gateway; the coordinator is a detached process that outlives the
respawn. Two-phase, acknowledged:

1. Build the argv: `aitask_codeagent.sh --agent-string <s> --resume-session <sid> --dry-run invoke raw`
   (resume) or the existing pick launch argv (`--repick`, task id required).
   Empty session id and no `--repick` → `RESTORE_FAILED:no_session` (nothing changes).
2. `restore-begin --mode <m>` → state `restoring`, lease minted (nonce `n`);
   captures and `@aitask_frozen` retained.
3. Prefix the argv with the **restore identity environment** (the
   `explore-relay` `env` precedent — `env` execs into the agent, so the pane
   pid is still the agent's):
   `env AITASK_RESTORE_RECORD=<id> AITASK_RESTORE_NONCE=<n> AITASK_RESTORE_MODE=<m> AITASK_RESTORE_EXPECT_SESSION=<sid> <argv>`.
   Then `set-option -pu @aitask_standin_ready` and
   `respawn-pane -k -t <stand-in> '<env argv>'` — or, when `pane_id=""`,
   `launch_in_tmux` into a new window with the recorded name. Immediately
   after tmux returns, read the new `#{pane_pid}` and write
   `restore-launched --nonce --pane --pane-pid` — the nonce-bound evidence
   that a replacement was actually started. The replacement agent's
   SessionStart hook forwards the four variables as `upsert --restore-of
   --nonce --session-id` (§A ack rules), which is what selects the **old**
   record from a brand-new pane, verifies the resumed session id, and stamps
   `@aitask_record` there.
4. Wait for the ack: poll `show <id>` until `state=live`, `last_error`
   carries this nonce, **or** `restore_ack_grace` elapses.
   - `live` with `ack=hook` → clear `@aitask_frozen`, print `RESTORED:<id>|hook`
     (captures already deleted by the ack).
   - `last_error="<nonce>:session_mismatch"` (the hook reported a different
     session in `resume` mode; persisted by the store because the hook has
     no channel to this process) → `restore-abort --nonce` (→ `aborting`,
     still owned by this nonce), `set-option -pu @aitask_standin_ready`,
     `respawn-pane -k` back to the stand-in, then `standin-respawned --nonce
     --pane --pane-pid` (→ `frozen`), print `RESTORE_FAILED:<id>|session_mismatch`;
     **capture intact**. The same abort → respawn → `standin-respawned --nonce`
     sequence is used by every failure branch below; a `NONCE_MISMATCH` at
     any step means reconcile already finished the abort.
   - grace elapsed, pane alive, `pane_pid == launch_pid`, no hook ack and no
     error → `restore-confirm --nonce --pane --pane-pid` → `live` with
     `ack=liveness`, **captures kept**, clear the stamp, print
     `RESTORED:<id>|liveness` (the viewer/minimonitor show "restored,
     unverified — capture kept").
   - pane dead at any poll (invalid session, binary missing, immediate exit)
     → `restore-abort --nonce`, clear ready, respawn the stand-in,
     `standin-respawned --nonce`, print `RESTORE_FAILED:<id>|agent_exited` —
     **the capture is intact and the viewer is back**.
   - `NONCE_MISMATCH` on any verb → reconcile already settled it; exit
     without touching the pane.
5. Coordinator crash between 2 and 4 → `reconcile` (§C table) settles it
   once the lease is stale.

`aitask_codeagent.sh` gains a global `--resume-session <sid>` (template
`OPT_HEADLESS`): `claude --model <id> --resume <sid>`, `codex resume <sid>`
(model flag per codex CLI), opencode → `RESUME_UNSUPPORTED:opencode` exit 2.
Resolution stays single-sourced in `lib/agent_string.sh`. Restore-All iterates
`frozen` records; per-record failures are reported, never abort the batch.

