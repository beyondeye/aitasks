---
priority: high
effort: medium
depends: [t1657_2]
issue_type: feature
status: Ready
labels: [framework, tmux, concurrency, codeagent, bash_scripts]
gates: [risk_evaluated]
anchor: 1657
created_at: 2026-09-01 12:36
updated_at: 2026-09-01 12:37
---

# Live-endpoint resolution infrastructure and agent adapters

Delivers the reusable primitive **"find the live agent implementing task X."**
Notes are its first consumer, **not its owner**.

## Context

Parent plan: `aiplans/p1657_task_note_mailbox_with_live_delivery.md`.
Depends on t1657_2 (the writer) — **not** on t1657_3, which is the independent
read side and can proceed in parallel with this.

The whole user-facing value is that a sender addresses a **task id** and never
has to discover by hand (1) whether the task is being implemented, (2) the
holder's lock/PID, (3) its tmux pane, (4) which agent session owns that pane, or
(5) how to route a message there. The parent task's Origin section documents a
human performing exactly that three-step cross-reference manually. Collapsing it
into one task-centric operation IS the feature.

**If any path still requires a human or an agent to run `tmux list-panes` or
enumerate agent sessions by hand, this child has not met its goal.**

## The boundary

```text
task id
  → validated local lock holder          ─┐
  → PID + start-time verification         │ generic, agent-runtime independent
  → tmux pane identity                    │
  → LIVE_PANE:… | LIVE_NONE:<reason>     ─┘
  → native agent-session match           ─┐ per-agent adapter
  → queued native message                ─┘
```

## Generic layer — `.aitask-scripts/aitask_live_endpoint.sh <task-id>`

Named for the capability, not for notes. **Contains no reference to any agent
runtime.**

Output: `LIVE_PANE:<%pane>|<session>:@<win>.%<pane>|<pid>|agent=<family>`
or `LIVE_NONE:<reason>`.

Reuse the canonical seams; do not reimplement:

- `aitask_lock.sh --check <id>` — stdout IS the lock record (raw YAML:
  `locked_by`, `locked_at`, `hostname`, `pid`, `pid_starttime`,
  `pid_starttime_kind`). Its stdout contract is strict — see the comment at
  `aitask_lock.sh:400`.
- `lib/pid_anchor.sh::lock_holder_liveness <pid> <token> <kind>` — returns
  `alive | dead | unknown`. **`unknown` must never be collapsed into `dead`**;
  that conflation is the t1465 defect class.
- `implemented_with` from the task frontmatter → `agent=<family>`.
- **All tmux access through the `lib/tmux_exec.sh` gateway.**
  `tests/test_no_raw_tmux.sh` enforces this. **Discovery only — this script never
  calls `send-keys`.**

PID→pane correlation: `pane_pid`-first (the lock anchors to the tmux pane process
by construction — `get_session_anchor_pid` rung 2), with an ancestor walk as
fallback so an `AIT_AGENT_PID`-anchored lock (rung 1) still resolves.

### Degradation table — complete enumeration, every branch a successful note

| `LIVE_NONE:<reason>` | condition |
|---|---|
| `unlocked` | no lock — nobody holds the task |
| `remote_host` | lock's `hostname` != this host |
| `holder_dead` | liveness → `dead` |
| `holder_unknown` | liveness → `unknown` (never read as dead) |
| `no_pane` | PID alive but no tmux pane maps to it |
| `agent_unsupported:<agent>` | Codex/OpenCode — no scriptable session listing |
| `agent_unknown` | `implemented_with` empty — the Step 4 → Step 7 window |
| `no_session_match` | pane verified, but no agent session row matches |

**None is an error. Every one leaves the durable note appended and committed.**

`agent_unknown` matters: `implemented_with` is written by Agent Attribution at
**Step 7**, while the lock is claimed at **Step 4**. During planning a task is
`Implementing` and locked with the field still empty. That window must read as
*unknown → durable lane*, never as an error.

## Adapter layer — per agent runtime

`.claude/skills/task-workflow/live-delivery-claude.md`: given a verified
`LIVE_PANE`, match the `%pane` against the `ListAgents` row's
`tmux <session>:@<win>.%<pane>` column, then `SendMessage`.

The adapter is a **skill procedure, not a script**, because `SendMessage` and
`ListAgents` are model-facing tools with no CLI — the join can only happen
agent-side. Reports **queued**, never "read": `success: true` means enqueued and
drained at the recipient's next tool round.

The live payload **carries the note id** so the recipient can tie the message to
the exact `## Inbox` entry.

Codex/OpenCode adapters are **absent by decision, not omission**: verified on
this host, `codex-cli 0.151.0` has `codex queue --thread <UUID|exact name>
--message`, but `codex agents` is an **interactive TUI with no `--json`** — there
is no scriptable way to enumerate Codex sessions or map one to a pane. Spawn a
follow-up for when that changes.

## tmux is discovery infrastructure, NEVER the transport

**`send-keys` must not be used to deliver a note.** It injects keystrokes into
whatever UI state the pane happens to be in — a prompt, a shell, an editor, a
half-typed answer — carries no agent identity or message framing, and offers no
queued/received semantics. tmux identifies the endpoint pane; delivery goes
through the agent runtime's own cross-session mechanism.

## Explicit requirements

1. No sender-side manual discovery; the calling workflow invokes the resolver.
2. A documented resolver contract + degradation table (lands in `aidocs/`, t1657_6).
3. Agent-runtime adapters own the native send and nothing else.
4. **Durable-first ordering is verified, not assumed**: the note is appended and
   committed *before* any live attempt.
5. tmux is never the transport.

## Whitelist

5 touchpoints for `aitask_live_endpoint.sh` per
`aidocs/framework/aitasks_extension_points.md`. No `ait` dispatcher entry for
now — per that doc, default to "no dispatcher entry" when in doubt; adding it
later is trivial, removing it is breaking.

## Verification

- A task id resolves to the correct live agent **solely through the
  infrastructure** — end-to-end against a **real second session on this host**,
  not a replica.
- Each degradation branch exercised through a documented seam: lock removed,
  `hostname` rewritten, PID killed, `implemented_with` set to a Codex string,
  `implemented_with` cleared (the Step 4→7 window). Each must still leave
  `NOTE_APPENDED:` intact.
- **Forced adapter failure after a successful write** leaves the durable note
  intact and is reported as *success with live delivery unavailable*, not a
  partial failure.
- `grep -rn 'ListAgents\|SendMessage\|claudecode' .aitask-scripts/aitask_live_endpoint.sh`
  returns nothing.
- A test asserts **no `send-keys`** on any delivery path.
- `bash tests/test_no_raw_tmux.sh`
- `shellcheck .aitask-scripts/aitask_live_endpoint.sh`
