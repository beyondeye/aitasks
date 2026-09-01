---
Task: t1657_4_live_endpoint_resolution_infrastructure.md
Parent Task: aitasks/t1657_task_note_mailbox_with_live_delivery.md
Sibling Tasks: aitasks/t1657/t1657_1_*.md, aitasks/t1657/t1657_2_*.md, aitasks/t1657/t1657_3_*.md, aitasks/t1657/t1657_5_*.md, aitasks/t1657/t1657_6_*.md
Base branch: main
Output branch: main
---

# p1657_4 — Live-endpoint resolution infrastructure and agent adapters

## Goal

Deliver the reusable primitive **"find the live agent implementing task X."**
Notes are its first consumer, not its owner. A sender addresses a **task id** and
never inspects tmux or enumerates agent sessions.

**If any path still requires a human or an agent to run `tmux list-panes` or
enumerate sessions by hand, this child has not met its goal.**

## Main steps

### 1. `.aitask-scripts/aitask_live_endpoint.sh <task-id>` (new, generic)

Named for the capability, not for notes. **No reference to any agent runtime.**

```
LIVE_PANE:<%pane>|<session>:@<win>.%<pane>|<pid>|agent=<family>
LIVE_NONE:<reason>
```

Resolution order, reusing canonical seams rather than reimplementing them:

1. `aitask_lock.sh --check <id>` — stdout **is** the lock record (raw YAML:
   `locked_by`, `locked_at`, `hostname`, `pid`, `pid_starttime`,
   `pid_starttime_kind`). Its stdout contract is strict (`aitask_lock.sh:400`).
   Exit 1 / empty → `LIVE_NONE:unlocked`.
2. `hostname` != this host → `LIVE_NONE:remote_host`.
3. `lib/pid_anchor.sh::lock_holder_liveness <pid> <token> <kind>` →
   `alive | dead | unknown`. **`unknown` must never be collapsed into `dead`** —
   that conflation is the t1465 defect class. `dead` → `LIVE_NONE:holder_dead`;
   `unknown` → `LIVE_NONE:holder_unknown`.
4. `implemented_with` → `agent=<family>`. Empty → `LIVE_NONE:agent_unknown`
   (the Step 4 lock → Step 7 attribution window; **not an error**).
   Non-Claude → `LIVE_NONE:agent_unsupported:<agent>`.
5. PID→pane: `pane_pid`-first (the lock anchors to the pane process by
   construction — `get_session_anchor_pid` rung 2), ancestor walk as fallback so
   an `AIT_AGENT_PID`-anchored lock (rung 1) still resolves. No pane →
   `LIVE_NONE:no_pane`.

**All tmux access through the `lib/tmux_exec.sh` gateway**
(`tests/test_no_raw_tmux.sh` enforces it). **Discovery only — never `send-keys`.**

### 2. Adapter — `.claude/skills/task-workflow/live-delivery-claude.md` (new)

Given a verified `LIVE_PANE`, match `%pane` against the `ListAgents` row's
`tmux <session>:@<win>.%<pane>` column, then `SendMessage`. No match →
`LIVE_NONE:no_session_match`.

A **skill procedure, not a script**: `SendMessage` / `ListAgents` are model-facing
tools with no CLI, so the join can only happen agent-side.

- reports **queued**, never "read" — `success: true` means enqueued and drained
  at the recipient's next tool round;
- the payload **carries the note id**, so the recipient can tie the message to
  the exact `## Inbox` entry.

Codex/OpenCode adapters are **absent by decision**: `codex-cli 0.151.0` has
`codex queue --thread <UUID|exact name> --message`, but `codex agents` is an
interactive TUI with **no `--json`** — nothing to resolve against. Spawn a
follow-up for when that changes.

### 3. tmux is discovery, NEVER the transport

`send-keys` must not deliver a note: it injects keystrokes into whatever UI state
a pane is in (prompt, shell, editor, half-typed answer), carries no agent identity
or message framing, and offers no queued/received semantics.

### 4. Whitelist

5 touchpoints per `aidocs/framework/aitasks_extension_points.md`. **No `ait`
dispatcher entry** — that doc says default to "no dispatcher entry" when in
doubt; adding later is trivial, removing is breaking.

## Verification

- a task id resolves to the correct live agent **solely through the
  infrastructure**, end-to-end against a **real second session on this host**,
  not a replica
- every degradation branch exercised through a documented seam: lock removed ·
  `hostname` rewritten · PID killed · `implemented_with` set to a Codex string ·
  `implemented_with` cleared. **Each must still leave `NOTE_APPENDED:` intact.**
- **forced adapter failure after a successful write** → durable note intact,
  reported as *success with live delivery unavailable*, not a partial failure
- `grep -rn 'ListAgents\|SendMessage\|claudecode' .aitask-scripts/aitask_live_endpoint.sh`
  returns nothing
- a test asserts **no `send-keys`** on any delivery path
- `bash tests/test_no_raw_tmux.sh`
- `shellcheck .aitask-scripts/aitask_live_endpoint.sh`

## Step 9 (Post-Implementation)

Cleanup, archival and merge per `task-workflow` Step 9.

## Risk

### Code-health risk: **low**

- New script, no existing behaviour altered; all state reads go through existing
  seams · severity: low
- tmux correlation could regress if a future launcher stops anchoring the lock to
  the pane process · severity: low · → mitigation: the ancestor-walk fallback and
  the explicit `no_pane` branch

### Goal-achievement risk: **medium**

- The end-to-end acceptance needs two real live sessions on one host, which no
  unit test can assert · severity: medium · → mitigation: covered by the
  aggregate manual-verification sibling
- The degradation enumeration must be complete or the resolver reports "cannot
  classify" as "no problem" · severity: medium · → mitigation: one test per
  reason code, each asserting the durable note survived
