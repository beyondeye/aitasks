---
Task: t1657_4_live_endpoint_resolution_infrastructure.md
Parent Task: aitasks/t1657_task_note_mailbox_with_live_delivery.md
Sibling Tasks: aitasks/t1657/t1657_5_aitask_note_skill_and_discoverability.md, aitasks/t1657/t1657_6_documentation_website_and_aidocs.md, aitasks/t1657/t1657_7_manual_verification_task_note_mailbox.md
Archived Sibling Plans: aiplans/archived/p1657/p1657_1_promote_ledger_block_substrate.md, aiplans/archived/p1657/p1657_2_inbox_format_and_ait_note_writer.md, aiplans/archived/p1657/p1657_3_read_receipts_and_pick_surfacing.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-06 13:07
---

# p1657_4 — Live-endpoint resolution infrastructure and agent adapters

*(Verify pass, 2026-09-06: the pre-existing `aiplans/p1657/p1657_4_*.md` was
re-checked against the tree. Findings and corrections are marked **[verify]**.)*

## Context

Parent: `aitasks/t1657_task_note_mailbox_with_live_delivery.md` — "let tasks mail
notes to each other". Siblings 1–3 shipped the durable lane: `lib/ledger_block.sh`
(the append substrate), `aitask_note.sh` (the `## Inbox` writer), and pick-time
surfacing with read receipts. What is missing is the **live** lane.

Today a sender who wants to reach the agent actually working on task X has to
cross-reference by hand: `aitask_lock.sh --check` for the pid, `tmux list-panes`
for the pane owning it, then eyeball the `ListAgents` row. This child collapses
those three steps into one task-centric primitive — **"find the live agent
implementing task X"** — and adds the Claude-side send adapter on top of it.

Notes are the first consumer, **not the owner**: the resolver script is named for
the capability and contains no reference to any agent runtime. The *composition*
of writer + resolver + adapter belongs to t1657_5, which depends on this task.

**Goal test:** if any path still requires a human or an agent to run
`tmux list-panes` or enumerate agent sessions by hand, this child has not met its
goal.

## What verification changed

| # | Finding | Effect on the plan |
|---|---|---|
| 1 | **`ListAgents` renders `#{window_id}`, not `@#{window_index}`.** Measured: pane `%2` is `aitasks:@2.%2` in `ListAgents` but `window_index 3` / `window_id @2` in tmux. The old plan's `@<win>` was ambiguous and would have produced a mismatched target string. | Format string is `#{session_name}:#{window_id}.#{pane_id}`; the adapter joins on `%pane` alone. |
| 2 | **The plan contradicted itself on the agent gate.** It required `LIVE_NONE:agent_unsupported:<agent>` *and* `grep 'claudecode' aitask_live_endpoint.sh` → nothing. | Resolved by a **manifest** at `.aitask-scripts/live_delivery/agents.txt`; the resolver contains no agent literal. |
| 3 | **The adapter's proposed home is an orphan slot.** `aitask_skill_render.sh` is a reachability dep-walker — an `.md` under `.claude/skills/task-workflow/` that nothing references is never rendered into the per-profile variants (`task-fold-content.md` is already such an orphan). | Adapter moves to `.aitask-scripts/live_delivery/claudecode.md`, agent-neutral and profile-invariant. |
| 4 | **A legacy lock has no `pid:` field at all.** Real record on this host: `t259` predates the PID anchor. `lock_holder_liveness "" "-" proc` → `unknown`, so it lands on `holder_unknown` — correct, but the degradation table never said so. | Added as an explicit, tested row. |
| 5 | **`parse_agent_string` calls `die` on an unrecognised agent.** Using it to derive the family would abort the resolver on exactly the input the `agent_unsupported` branch exists to handle. | Family is derived locally by splitting `implemented_with` on `/`. |
| 6 | **`note_sender_is_self()` already parses the lock record** (host/pid/token/kind) with the exact four `sed` extractions the resolver needs. | Extracted into `lib/lock_record.sh`; both callers use it. |
| 7 | `aidocs/framework/aitasks_extension_points.md` prose says "7-touchpoint checklist" but its table lists **5**, and `aitask_note.sh` is whitelisted in exactly those 5. | Plan uses 5; the doc's stale count is handed to t1657_6 (docs child), not fixed here. |
| 8 | **The resolver cannot assert `NOTE_APPENDED:` survival.** It takes a task id and returns a code — it never appends a note nor calls `SendMessage`. The task's AC to that effect describes the *composition*, which t1657_5 declares as its single join point. | Tests scoped to result codes; the two behavioral assertions relocated to t1657_5 and handed over durably via `ait note`. |
| 10 | **REVIEW (blocking): usage prose leaked onto stdout.** A no-argument invocation printed 16 lines of help *and then* `LIVE_ERROR:usage`, breaking the "exactly ONE line on stdout, always" contract — a caller reading the first line would parse `Usage:` as the result. | Help goes to stderr for every invalid invocation; `--help` is the one documented exception. Pinned by a LINE-COUNT assertion, not a prefix match. |
| 11 | **REVIEW (blocking): a manifest name match alone produced `LIVE_PANE`.** `adapter_for_family` never checked that the row named a procedure, or that the file existed — so a truncated row promised a live endpoint the caller had nothing to deliver through. Worse, the degradation test used nonexistent `fake.md` paths as *accepted* rows, making the hole the contract. | The procedure file must exist and be readable, and column 2 became a bare filename resolved inside the delivery directory (no `/`, no `..`). Tests rebuilt on real files, with cases for every unusable-row shape. |
| 12 | **REVIEW (blocking): `-r` alone is true for a DIRECTORY.** The first fix for row 11 checked only readability, so a manifest row naming a directory still passed the agent gate and emitted `LIVE_PANE` — the same broken promise, one shape further in. Reproduced directly. | `-f && -r`: readable must mean *readable as a procedure*. Added as a case to the unusable-row set. |
| 9 | **The live-tmux positive case as written was vacuous.** Claiming a task writes only the lock; `implemented_with` lands at Step 7 attribution, so a fresh claim short-circuits at step 5 (`agent_unknown`) and never reaches PID→pane. Real evidence: `t1569_6` is live in pane `%2` right now with the field empty. | Fixture seeds `implemented_with`, plus an explicit ordering control and a socket negative control. |

Confirmed unchanged: `aitask_lock.sh` stdout contract (`aitask_lock.sh:402`),
`lock_holder_liveness` three-valued return, `get_session_anchor_pid`'s two rungs,
the `lib/tmux_exec.sh` gateway, `tests/test_no_raw_tmux.sh`. Nothing named
`live_endpoint` / `LIVE_PANE` exists yet — this is greenfield.

---

## Step 1 — `.aitask-scripts/aitask_live_endpoint.sh <task-id>` (new)

Named for the capability. **Contains no reference to any agent runtime.**
Exactly one line on stdout, mirroring `aitask_note.sh`'s output contract:

```
LIVE_PANE:<%pane>|<session>:<@win>.<%pane>|<pid>|agent=<family>     exit 0
LIVE_NONE:<reason>                                                  exit 0
LIVE_ERROR:<reason>                                                 exit 2
```

`LIVE_NONE` is a **successful resolution** ("there is no live endpoint"), not a
failure — hence exit 0, disjoint from `LIVE_ERROR` (the resolver itself could not
run: bad usage, unresolvable task file). Every advisory goes to stderr via
`warn()`.

**"Exactly one line" holds on the misuse paths too.** A usage error prints its
help to **stderr** and still emits its single `LIVE_ERROR:usage` line on stdout,
so a caller reading the first line can never find prose there. `-h` / `--help` is
the sole exception — that invocation is addressed to a human — and it is pinned
as an exception so it stays deliberate rather than becoming a second leak.

Resolution order — reuse the canonical seams, do not reimplement:

1. **Canonicalise the id to bare form** (`t1657_4` → `1657_4`). Mirror
   `aitask_note.sh` §0: `aitask_lock.sh --check t1669` prints *nothing* while
   `--check 1669` works, so a `t`-prefixed id would silently read as "unlocked".
2. **`aitask_lock.sh --check <bare>`** — its stdout *is* the lock record (raw
   YAML). Empty / exit 1 → `LIVE_NONE:unlocked`.
3. **`hostname` != `$(hostname)`** → `LIVE_NONE:remote_host`.
4. **`lock_holder_liveness <pid> <token> <kind>`** (`lib/pid_anchor.sh`) →
   `dead` → `LIVE_NONE:holder_dead`; `unknown` → `LIVE_NONE:holder_unknown`.
   **`unknown` is never collapsed into `dead`** — that conflation is the t1465
   defect class. A legacy lock with no `pid:` line arrives here as `unknown`.
5. **Agent family** — `resolve_task_file` → `extract_implemented_with`
   (`lib/task_utils.sh:2064`) → family = the part before `/`.
   - empty → `LIVE_NONE:agent_unknown` (the Step 4 lock → Step 7 attribution
     window; **not an error**);
   - family absent from the manifest → `LIVE_NONE:agent_unsupported:<family>`.
6. **PID → pane.** Build the map in one gateway call:
   ```bash
   ait_tmux list-panes -a -F '#{pane_pid}'$'\t''#{pane_id}'$'\t''#{session_name}:#{window_id}.#{pane_id}'
   ```
   `pane_pid`-first (the lock anchors to the pane process by construction —
   `get_session_anchor_pid` rung 2), then a **bounded ancestor walk**
   (`ps -o ppid= -p`, stop at pid 1 or 20 hops) so an `AIT_AGENT_PID`-anchored
   lock (rung 1) still resolves. No hit → `LIVE_NONE:no_pane`.
7. Emit `LIVE_PANE:…`.

**All tmux access through `lib/tmux_exec.sh`** (`tests/test_no_raw_tmux.sh`
enforces it). **Discovery only — this script never calls `send-keys`.**

Scope note to document: the gateway targets the `ait` socket, so an agent on
another tmux server is invisible and reads as `no_pane`. That is the honest
boundary — the framework launches every managed agent on the gateway socket.

### Degradation table (complete enumeration of the resolver's result codes)

| `LIVE_NONE:<reason>` | condition |
|---|---|
| `unlocked` | no lock record |
| `remote_host` | lock's `hostname` != this host |
| `holder_dead` | liveness → `dead` |
| `holder_unknown` | liveness → `unknown`, **including a legacy lock with no `pid:` field** |
| `agent_unknown` | `implemented_with` empty (Step 4 → Step 7 window) |
| `agent_unsupported:<agent>` | family has no adapter in the manifest |
| `no_pane` | PID alive but no gateway pane maps to it |
| `no_session_match` | **adapter-layer**: pane verified, no `ListAgents` row matches |

## Step 2 — `.aitask-scripts/live_delivery/` (new directory)

`agents.txt` — the manifest; two whitespace-separated columns, `#` comments:

```
# <agent-family>  <adapter procedure filename>
claudecode        claudecode.md
```

Column 2 is a **bare filename resolved inside this directory** — not a
repo-relative path. That is what makes the same manifest work under the
`AIT_LIVE_DELIVERY_DIR` test seam, and it lets a `/` or `..` in the column be
*refused* rather than followed: the manifest is a data file, so its paths are
untrusted input.

**A name match is not enough to call a family supported.** `LIVE_PANE` is a
promise the caller acts on — a live endpoint *and* a procedure to deliver
through. A truncated row, or one naming a file that is not there, would break
that promise one layer too late: the caller is told the endpoint is live and then
finds nothing to run. So the row must resolve to a **readable regular file**
(`-f && -r`, not `-r` alone — that is true for a directory, which is a readable
path but not a readable procedure) before the gate opens. Anything less answers
`agent_unsupported:<family>`, which is exactly what a family with no usable
adapter is.

Framework-owned data shipped inside `.aitask-scripts/`, exactly like
`.aitask-scripts/gates_reference.yaml` (`install.sh:502` — "source is the
canonical reference under `.aitask-scripts/`, NOT `seed/`"). It therefore needs
**no `seed/` mirror and no `aitask_setup.sh` edit**. Adding Codex later is one
row plus one file.

Tests reach it through a documented seam: `AIT_LIVE_DELIVERY_DIR` overrides the
directory, so the manifest can be proven to actually drive the decision rather
than decorate it.

`claudecode.md` — the adapter procedure. A **skill procedure, not a script**:
`SendMessage` / `ListAgents` are model-facing tools with no CLI, so the join can
only happen agent-side.

1. Call `ListAgents`.
2. Match the row whose tmux column ends in `.<%pane>`. **Join on the pane id
   alone** — pane ids are unique per server and are the most stable token in a
   row whose exact rendering is an observed contract, not a documented API.
3. No match → `LIVE_NONE:no_session_match`. (This session is never listed, so a
   self-directed send lands here by construction — no extra reason code.)
4. Two rows sharing a bare name → address with the row's ` [ref]` suffix.
5. `SendMessage({to: <name>, …})` with a payload **carrying the note id**, so the
   recipient can tie the message to the exact `## Inbox` entry.
6. Report `LIVE_QUEUED:<session>|<note-id>` — **queued, never read**.
   `success: true` means enqueued and drained at the recipient's next tool round.
7. Any adapter failure after a successful durable write → `LIVE_NONE:…`, reported
   as *success with live delivery unavailable*, never a partial failure.

Codex / OpenCode adapters are **absent by decision, not omission**: verified,
`codex-cli 0.151.0` has `codex queue --thread … --message`, but `codex agents` is
an interactive TUI with **no `--json`** — there is no scriptable way to enumerate
Codex sessions or map one to a pane. Spawn a follow-up for when that changes.

## Step 3 — `lib/lock_record.sh` (new, small)

`lock_record_read <bare-id>` runs `aitask_lock.sh --check` once and sets
`LOCK_REC_HOST` / `_PID` / `_TOKEN` / `_KIND`; returns 1 when unlocked.
`aitask_note.sh::note_sender_is_self` (lines 313–330) is refactored onto it in the
same commit — it currently owns the only copy of those four `sed` extractions, and
the resolver needs the identical parse. Guarded by `tests/test_note_append.sh`
cases 6a/6b/6c, which cover both the verified and unverified sender paths.

## Step 4 — tmux is discovery, NEVER the transport

`send-keys` must not deliver a note: it injects keystrokes into whatever UI state
a pane is in (a prompt, a shell, an editor, a half-typed answer), carries no agent
identity or message framing, and offers no queued/received semantics. tmux
identifies the endpoint pane; delivery goes through the agent runtime's own
cross-session mechanism.

## Step 5 — Whitelist (5 touchpoints)

`aitask_live_endpoint.sh` is invoked from t1657_5's skill, so it needs the full
helper allowlist — the same five entries `aitask_note.sh` carries:
`.claude/settings.local.json`, `.codex/rules/default.rules`,
`seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
`seed/opencode_config.seed.json`.

**No `ait` dispatcher entry** — `aitasks_extension_points.md` says default to "no
dispatcher entry" when in doubt; adding later is trivial, removing is breaking.

### Post-phase (risk mitigations)

Runs after Steps 1–5, before the task is considered complete.

- **`diagnosable_no_session_match`** — the adapter must not report a bare
  `no_session_match`. It reports the pane id it searched for and how many
  `ListAgents` rows carried a tmux column, and a guard test pins the join token
  shape (`^\S+:@\d+\.%\d+$`) the match depends on. A future rendering change then
  fails the guard loudly instead of turning every send into a silent "no match".
- **`lock_record_unit`** — direct assertions for `lock_record_read`: all four
  fields parsed from a live record; a legacy record with no `pid:` line yields an
  **empty** PID rather than a stale one; an unlocked id returns 1. Pins the shared
  seam on its own rather than only through `note_sender_is_self`.
- **`durable_handoff_to_t1657_5`** — send the two moved assertions to t1657_5 via
  `./ait note 1657_5 --from 1657_4`, and verify `NOTE_APPENDED:` in the output.
  Two acceptance criteria are being relocated across a task boundary; a note in
  the recipient's `## Inbox` is the artifact that survives this session, and it
  surfaces automatically when t1657_5 is picked.

---

## Verification

Live fixtures confirmed present on this host while planning: `t1569_6` is held by
a second live Claude session (pid 80738 = pane `%2` = `ListAgents` row
`aitasks-f2 · tmux aitasks:@2.%2`) **and has no `implemented_with`**, so it is a
real `agent_unknown`; `t1705_1` is locked from `Darios-Mac-mini.local`
(`remote_host`); `t259` is a legacy lock with no `pid:` (`holder_unknown`).

**Scope of these tests — resolver result codes only.** The resolver takes a task
id and returns a code; it never appends a note and never calls `SendMessage`.
Asserting that `NOTE_APPENDED:` survives a branch therefore requires `ait note`
*plus* the adapter in one test — which is the composition t1657_5 owns as its
single join point. See "Deviation from the task's stated AC" below.

- **`tests/test_live_endpoint_degradation.sh`** — one case per reason code,
  driven through documented seams on the `test_note_append.sh` fixture pattern
  (private `AITASKS_LOCK_DIR`, a `$DATA` clone with a real `aitask-locks`
  branch): lock removed → `unlocked` · `hostname` rewritten → `remote_host` ·
  PID killed → `holder_dead` · a lock written without a `pid:` field →
  `holder_unknown` · `implemented_with` cleared → `agent_unknown` ·
  `implemented_with` set to a Codex string → `agent_unsupported:codex`. Each
  asserts **the exact stdout line and exit status**, nothing about notes.
- **`tests/test_live_endpoint_tmux_live.sh`** — the end-to-end proof, modelled on
  `tests/test_lock_anchor_tmux_live.sh`: an isolated tmux server on a private
  socket, a real pane claims a task.

  **The fixture MUST seed `implemented_with: claudecode/opus5` on that task
  before the resolver runs.** Claiming writes only the lock; `implemented_with`
  is written later by Agent Attribution (Step 7), so a freshly-claimed task has
  an empty field — and under the resolution order above, step 5 returns
  `agent_unknown` *before* step 6 ever attempts PID→pane correlation. Without the
  seed the positive case is unreachable and would pass vacuously over a
  completely broken correlator. `AIT_LIVE_DELIVERY_DIR` points at a fixture
  manifest declaring that family, so the live test does not depend on the shipped
  manifest's contents. (Real evidence: `t1569_6` is live in pane `%2` on this
  host right now with no `implemented_with`.)

  Three cases against the *same* live pane, so each discriminates on one variable:
  1. **Positive** — seeded field → `LIVE_PANE:` naming *that* pane's `%id` and a
     target string of the exact `session:@win.%pane` shape `ListAgents` renders.
  2. **Ordering control** — identical run with `implemented_with` cleared →
     `agent_unknown`, proving step 5 precedes step 6 rather than the pane simply
     being unfindable.
  3. **Correlation negative control** — identical run, seeded field, gateway
     socket repointed at a nonexistent server → `no_pane`, so case 1 cannot pass
     vacuously.
- **Manifest guard** — with `AIT_LIVE_DELIVERY_DIR` pointing at a fixture
  containing a fabricated family **and a procedure file that exists**, that
  family resolves; with it absent, the same input yields `agent_unsupported`.
  Proves the manifest drives the decision.
- **Unusable-row guard** — one case per shape a truncated install or a hand-edit
  actually produces: a row with no procedure column, a row naming a missing file,
  a row naming a **directory**, a row naming an unreadable file, a `../`
  traversal, and a subdirectory path that *does* resolve. All must answer `agent_unsupported`, never `LIVE_PANE`.
  Fixture rows point at **real files**: a test that accepts a nonexistent
  procedure would make the hole the contract.
- **Shipped-manifest check** — the manifest that actually ships must satisfy its
  own rule, or the live lane is dead in the product while every fixture case
  passes.
- **stdout purity on misuse** — a no-argument call and a too-many-arguments call
  each put exactly **one** line on stdout (asserted as a line count, not a
  prefix), that line is `LIVE_ERROR:usage`, the exit status is 2, and the help
  text is present on stderr. `--help` is pinned separately as the one exception.
- **`tests/test_live_endpoint_no_sendkeys.sh`** — asserts no `send-keys` on any
  delivery path (resolver *and* adapter procedure).
- `grep -rn 'ListAgents\|SendMessage\|claudecode' .aitask-scripts/aitask_live_endpoint.sh`
  returns nothing.
- `bash tests/test_no_raw_tmux.sh` · `bash tests/test_note_append.sh` ·
  `shellcheck .aitask-scripts/aitask_live_endpoint.sh .aitask-scripts/lib/lock_record.sh`

## Deviation from the task's stated AC — and the handoff that covers it

`t1657_4`'s Verification section says every degradation branch "must still leave
`NOTE_APPENDED:` intact" and that a "forced adapter failure after a successful
write" is reported as success-with-live-unavailable. **Neither is assertable
here.** Both describe *durable-first ordering* — a property of the sequence
`ait note` → resolver → adapter — and that sequence is t1657_5's declared single
composition point. Testing it from t1657_4 would either depend on an unshipped
sibling or stand up a second, drifting copy of the composition.

So the resolver's contract stays here (result codes, exit statuses, the adapter
procedure's written obligation to report `LIVE_NONE` rather than a partial
failure), and the two behavioral assertions move to t1657_5. They are **handed
over durably, not just noted here** — as the final implementation step, using the
mailbox this task tree exists to build:

```bash
./ait note 1657_5 --from 1657_4 --text "…"
```

carrying exactly two items for t1657_5's composition test: (a) `ait note` returns
`NOTE_APPENDED:` before any resolver call is made, for every `LIVE_NONE` reason
code; (b) an adapter failure *after* a successful durable write is reported as
success with live delivery unavailable, never a partial failure.

## Out of scope (owned elsewhere)

- **Composition** — writer → resolver → adapter is t1657_5's contract, including
  the two assertions handed over above.
- **Docs** — the resolver contract and degradation table land in `aidocs/` via
  t1657_6, together with the stale "7-touchpoint" count noted above.
- **Two-real-session acceptance** — t1657_7's manual-verification checklist.

## Step 9 (Post-Implementation)

Cleanup, archival and merge per `task-workflow` Step 9.

## Risk

### Code-health risk: low

- New script plus a new data directory; no existing behaviour is altered and all
  state reads go through existing seams · severity: low · → mitigation: none
  needed
- The one edit to shipped code is extracting `note_sender_is_self`'s lock-record
  parse into `lib/lock_record.sh` — mechanical, and `test_note_append.sh` 6a–6c
  already pin both sender-proof outcomes · severity: low · → mitigation: inline
  post-phase `lock_record_unit`
- tmux correlation would regress if a future launcher stopped anchoring the lock
  to the pane process · severity: low · → mitigation: the ancestor-walk fallback
  and the explicit `no_pane` branch

### Goal-achievement risk: medium

- **The `ListAgents` row format is an observed contract of a model-facing tool,
  not a documented API.** A rendering change degrades the adapter silently to
  `no_session_match` — fail-safe, but indistinguishable from "that session is
  gone" · severity: medium · → mitigation: inline post-phase
  `diagnosable_no_session_match`
- The end-to-end acceptance needs two real live sessions on one host, which no
  unit test can assert · severity: medium · → mitigation: covered by t1657_7
- The degradation enumeration must be complete, or the resolver reports "cannot
  classify" as "no problem" · severity: medium · → mitigation: one test per
  reason code, each pinning the exact stdout line and exit status
- **Two of the task's stated acceptance criteria are relocated to t1657_5.** If
  the handoff is lost, durable-first ordering ends up asserted by nobody ·
  severity: medium · → mitigation: inline post-phase
  `durable_handoff_to_t1657_5`
- The live-tmux positive case is only meaningful if `implemented_with` is seeded;
  otherwise step 5 short-circuits and the correlator is never exercised ·
  severity: medium · → mitigation: the seeded fixture plus the ordering control
  and socket negative control in `test_live_endpoint_tmux_live.sh`

### Planned mitigations
- timing: post-phase | name: diagnosable_no_session_match | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: ListAgents row-format drift degrades silently | desc: adapter names the searched pane and row count; guard test pins the join token shape
- timing: post-phase | name: lock_record_unit | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: shared lock-record parser extracted from shipped aitask_note.sh | desc: direct assertions for lock_record_read incl. legacy no-pid record and unlocked return
- timing: post-phase | name: durable_handoff_to_t1657_5 | type: chore | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: two acceptance criteria relocated to t1657_5 could be lost | desc: send the two moved assertions to t1657_5 via ait note and verify NOTE_APPENDED

*Reassessment after inlining all three mitigations: code-health stays **low**
(two bounded test additions plus one CLI call). Goal-achievement stays
**medium** — format drift and the relocated criteria are now mitigated, and the
live-tmux ordering trap is closed by the seeded fixture, but the
two-real-sessions acceptance remains unassertable in-suite and is carried by
t1657_7.*

## Final Implementation Notes

- **Actual work done:** All five plan steps landed as designed, plus the three
  inline post-phase mitigations.
  - `.aitask-scripts/aitask_live_endpoint.sh` — the resolver. One stdout line
    always; `LIVE_PANE:` / `LIVE_NONE:` at exit 0, `LIVE_ERROR:` at exit 2.
    Reuses `aitask_lock.sh --check`, `lock_holder_liveness`,
    `extract_implemented_with` and the `lib/tmux_exec.sh` gateway; reimplements
    none of them.
  - `.aitask-scripts/live_delivery/` — `agents.txt` (adapter manifest) and
    `claudecode.md` (the Claude adapter procedure). Shipped inside
    `.aitask-scripts/` on the `gates_reference.yaml` precedent, so it needed no
    `seed/` mirror and no `aitask_setup.sh` edit.
  - `.aitask-scripts/lib/lock_record.sh` — the shared lock-record parse;
    `aitask_note.sh::note_sender_is_self` refactored onto it in the same commit.
  - Whitelist: 5 touchpoints, mirroring `aitask_note.sh`. No `ait` dispatcher entry.
  - Tests: `test_live_endpoint_degradation.sh` (53), `_tmux_live.sh` (16),
    `_no_sendkeys.sh` (26).
  - The `durable_handoff_to_t1657_5` mitigation was executed with `ait note` —
    dogfooding the mailbox this tree is building. It returned
    `NOTE_APPENDED:2026-09-06T10:31:51Z.735d5174ae0697c82769afcc` with
    `from_verified=yes`, which is also live proof of the refactored sender check.

- **Deviations from plan:** Two, both recorded as findings in the plan body.
  (1) The manifest's second column became a **bare filename resolved inside the
  delivery directory** rather than a repo-relative path — it makes the
  `AIT_LIVE_DELIVERY_DIR` seam coherent and lets `/` and `..` be refused rather
  than followed. (2) Two of the task's own acceptance criteria
  (`NOTE_APPENDED:` survival per branch; post-write adapter failure) were
  **relocated to t1657_5**: the resolver neither writes notes nor calls
  `SendMessage`, so only the composition owner can assert them.

- **Issues encountered:**
  - The plan's two internal contradictions (agent gate vs. the "no `claudecode`
    literal" criterion; adapter placed in an unrendered orphan slot) were found
    during the verify pass and resolved before implementation.
  - `ListAgents` renders `#{window_id}`, not `@#{window_index}` — measured, they
    differ for the same pane. The first draft would have emitted a target that
    looked right and joined to nothing.
  - The live-tmux positive case was initially designed on a bare claim, which
    short-circuits at `agent_unknown` before the correlator runs; the fixture now
    seeds `implemented_with` and keeps the unseeded run as an ordering control.
  - Review round 1: usage prose leaked onto stdout on an invalid invocation,
    breaking the one-line contract. Fixed (help to stderr; `--help` the sole
    exception) and pinned by line count.
  - Review round 2: `adapter_for_family` accepted a name match without checking
    that a procedure existed — and the first test wrote nonexistent `fake.md`
    rows as *accepted*, making the hole the contract. Fixed and rebuilt on real
    files.
  - Review round 3: `-r` alone is true for a directory, so the round-2 fix still
    let a row naming a directory through. Now `-f && -r`.

- **Key decisions:**
  - **`LIVE_NONE` exits 0.** A degradation is a successful resolution; only
    `LIVE_ERROR` (exit 2) means the resolver could not run. The two sets are
    disjoint so "no endpoint" and "resolver broke" are never confusable.
  - **`unknown` is never collapsed into `dead`** (the t1465 class), and a legacy
    lock with no `pid:` line reaches that branch — an explicit, tested row.
  - **The agent gate is data-driven.** No agent literal in the resolver; the
    manifest decides, and it must resolve to a readable regular file before a
    family counts as supported, because `LIVE_PANE` is a promise the caller acts on.
  - **Agent-family check precedes PID→pane** — cheaper, and it makes
    `agent_unknown` reachable during the Step 4 → Step 7 attribution window.
  - **The adapter is a procedure, not a script**, and lives outside the skill
    tree: profile-invariant, agent-neutral, and not subject to the renderer's
    reachability walk.

- **Upstream defects identified:**
  - `aidocs/framework/aitasks_extension_points.md:319 — prose says "7-touchpoint
    checklist" while its own table lists 5; `aitask_note.sh` is whitelisted in
    exactly those 5, so the count is stale. Handed to t1657_6 (the docs child),
    not fixed here.

- **Notes for sibling tasks:**
  - **t1657_5 owns the composition** and has been sent a durable note with the
    two relocated assertions and the full resolver/adapter contract. Read its
    `## Inbox` first.
  - The resolver's stdout contract mirrors `aitask_note.sh`: exactly one line,
    advisories to stderr. Follow it in any new helper here.
  - `AIT_LIVE_DELIVERY_DIR` is the documented seam for driving the manifest from
    a fixture; `AITASKS_TMUX_SOCKET` pointed at a nonexistent server is the
    documented way to force `no_pane` without touching a real tmux server.
  - When testing the live lane, remember `implemented_with` is written at Step 7,
    not at claim time — a freshly claimed fixture task answers `agent_unknown`.
  - `tests/test_lock_anchor_tmux_live.sh` is the template for isolated-tmux
    tests; `tests/test_note_append.sh` is the template for a lock-bearing
    fixture repo.
