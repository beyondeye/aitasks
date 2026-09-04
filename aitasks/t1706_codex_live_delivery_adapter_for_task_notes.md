---
priority: medium
effort: medium
depends: [1657_4]
issue_type: feature
status: Ready
labels: [codeagent, framework, concurrency, bash_scripts]
gates: [risk_evaluated]
anchor: 1657
created_at: 2026-09-04 11:53
updated_at: 2026-09-04 11:53
---

# Codex live-delivery adapter for task notes, via app-server thread enumeration

Deliver the **Codex** arm of the note mailbox's live lane. `t1657_4` scoped it
out — `LIVE_NONE:agent_unsupported:<agent>` — and `p1657_4:67-70` states the
reason and the trigger to revisit:

> Codex/OpenCode adapters are **absent by decision**: `codex-cli 0.151.0` has
> `codex queue --thread <UUID|exact name> --message`, but `codex agents` is an
> **interactive TUI with no `--json`** — there is no scriptable way to enumerate
> Codex sessions or map one to a pane. Spawn a follow-up for when that changes.

**That has now changed.** This task is that follow-up.

## What changed, as measured on this host

`codex-cli 0.153.2` (the exclusion was measured against `0.151.0`):

- `codex app-server proxy` — "Proxy stdio bytes to the running app-server
  control socket" (`--sock <SOCKET_PATH>`). A **scriptable stdio JSON-RPC
  channel into the same shared local daemon** that `codex agents` browses
  interactively. The TUI is no longer the only door.
- `codex app-server generate-json-schema --out <DIR>` emits the full protocol.
  Two methods matter:
  - **`thread/loaded/list`** → `{ data: [threadId…], nextCursor }`, documented as
    "Thread ids for sessions currently loaded in memory" — i.e. **the live set**.
  - **`thread/list`** → per-thread records with `id`, `name`, `cwd`, `status`,
    `source` (`cli` | `vscode` | `exec` | `appServer` | `subAgent*`), `gitInfo`,
    `model`, `agentNickname`, `agentRole`. Params accept a **`cwd` filter**,
    sort keys, and an `archived` filter.
- `codex queue --thread <UUID|exact session name> --message <text>` is unchanged
  and remains the delivery verb.
- `strings $(command -v codex)` shows **`CODEX_THREAD_ID`** in the binary's
  environment-variable surface, alongside `CODEX_HOME` / `CODEX_NON_INTERACTIVE`.
  If Codex exports it into the session's shell, a Codex-held task can record its
  **own** endpoint token at claim time and the discovery problem collapses.
  **`CODEX_THREAD_ID` is inferred from the binary, not observed in a live Codex
  session — verifying it is step one of this task, and the design must not
  assume it.**

## The load-bearing gap: the Claude join does not transfer

`t1657_4`'s generic layer resolves **task id → lock pid → tmux pane → agent
session**, and the Claude adapter matches `%pane` against the `ListAgents` row.
The Codex `Thread` record has **no `pid` and no pane identity** — its fields are
listed above. So `LIVE_PANE:…|agent=codex` cannot be joined to a Codex thread by
the pane token that works for Claude.

Two candidate joins, in preference order:

1. **Self-recorded endpoint token (preferred).** The Codex session records its
   own `CODEX_THREAD_ID` when it claims the task, so resolution is a lookup, not
   a search. This is the same shape as `implemented_with` (written by the agent
   about itself) and it sidesteps daemon enumeration entirely for the common
   case. Needs a decision on **where** the token lives — the lock record, task
   frontmatter, or a sidecar — and that decision must respect the
   `## Inbox`/gate-ledger append discipline and path-scoped commits.
2. **Enumerate and filter.** `thread/loaded/list` ∩ `thread/list --cwd <repo
   root>`, narrowed by `status` / `source`. This is a **heuristic**: two Codex
   sessions in the same repo are indistinguishable, so it must either resolve
   unambiguously or degrade. **Never guess a recipient** — a note delivered to
   the wrong session is worse than no live delivery.

## Requirements

1. **Durable-first ordering is preserved unconditionally.** Every branch here
   still leaves `NOTE_APPENDED:` intact and committed before any live attempt.
   Live delivery remains an optimisation, per the parent task's non-negotiables.
2. **Verify `CODEX_THREAD_ID` against a real Codex session on this host** before
   building on it. If it is not exported, fall back to join (2) or scope the
   task down to enumeration-only and say so.
3. **The generic layer stays agent-agnostic.** `t1657_4`'s verification pins
   `grep -rn 'ListAgents\|SendMessage\|claudecode'
   .aitask-scripts/aitask_live_endpoint.sh` returning nothing — the Codex arm
   must not put `codex` in there either. Extend the resolver's **output** shape
   (a per-agent endpoint token), not its knowledge of runtimes.
4. **`agent_unsupported:codex` must be retired, not left lying.** It is a
   documented degradation branch in `t1657_4`'s table and in `aidocs/` (t1657_6).
   When Codex becomes supported, that row and its docs change together, and the
   new branches (`daemon_absent`, `ambiguous_thread`, …) join the table with the
   same "none is an error" property.
5. **tmux is never the transport** — inherited verbatim from `t1657_4`. Codex
   delivery goes through `codex queue`, never `send-keys`.
6. **The daemon may be absent.** `codex app-server proxy` needs a running
   daemon; a Codex session started without one, or a stale socket, must produce
   a clean `LIVE_NONE:` reason, not a hang or a stderr leak. Bound any proxy
   call with a timeout.
7. **The protocol is `[experimental]`.** `app-server` is flagged experimental
   and the schema is versioned (`v1`/`v2` trees). Pin the observed shape in a
   test fixture and fail loudly on drift rather than silently degrading — the
   framework already has this problem shape with `models_*.json`.
8. **No `notify_when_idle` analogue.** Claude's read-receipt subscription has no
   Codex counterpart in the CLI surface. Report **queued, never read**, and do
   not introduce polling to fake it.

## Explicitly out of scope

- **OpenCode.** Unexamined here; it keeps `agent_unsupported:opencode` until
  someone measures it. Spawn a sibling follow-up if that changes.
- **Cross-host delivery** — still the durable lane's job (parent non-negotiable).
- **Cross-agent pairs** (`claude→codex`, `codex→claude`). Once each runtime can
  both identify itself and be addressed, these fall out of the same resolver —
  but the sender-side dispatch on `agent=<family>` is a separate decision and
  should be settled once, not twice. Note it in planning; do not build it here.

## Sequencing

Depends on `t1657_4`, which owns the generic resolver, the degradation table,
and the adapter-layer boundary. **Do not start before it lands** — this task
adds an arm to a contract that does not exist yet, and building against the
design rather than the implementation is how the two drift.

## Provenance

Found while answering "does t1657 support codex→codex live messages?".
Answer at the time of writing: **no** for Codex (excluded by decision), and
**not yet** for Claude (t1657_4 is `Ready`; `grep -rln 'SendMessage\|ListAgents'`
over `.claude/skills/`, `.aitask-scripts/` and `aidocs/` returns nothing). The
durable lane (`ait note` → `aitask_note.sh`, dispatcher `ait:203`) is live and
is already agent-agnostic.

The parent task `t1657` carries a hand-delivered `## Inbox` note making the same
argument from the other direction — that the design was silent on agent type and
that Codex "HAS an equivalent in a different shape". This task closes the half of
that note the plan deferred.
