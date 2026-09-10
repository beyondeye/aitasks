# Live-endpoint resolution — finding the agent session that holds a task

Decision and contract record for the resolver added by t1657_4 and composed by
t1657_5. It is a document of its own rather than a section of the note
mailbox's, because the boundary outlives notes: the primitive is "find the live
agent session implementing task X", and notes are only its first consumer.

Read together with:

- `aidocs/framework/task_note_mailbox.md` — the durable lane this resolver runs
  behind, and the `/aitask-note` composition that sequences the two.
- `.aitask-scripts/aitask_live_endpoint.sh` — the resolver. Its header is the
  canonical statement of the output contract and the resolution order.
- `.aitask-scripts/live_delivery/agents.txt` and the procedures beside it — the
  adapter registry and the per-agent delivery steps.
- `aidocs/framework/tmux_gateway.md` — the only sanctioned route to tmux.
- `aiplans/archived/p1657/p1657_4_live_endpoint_resolution_infrastructure.md` —
  its "What verification changed" table records the findings behind several of
  the rules below.

## The problem

Before the resolver, telling a live session something meant a human
cross-referencing three things by hand: `ait lock --check <id>` for the pid and
hostname, `tmux list-panes -a` for the pane owning that pid, and the agent
runtime's session listing for the name to address. The resolver collapses that
into one task-centric call. If any path still needs a human to run
`tmux list-panes`, the resolver has failed.

## The split: a generic resolver, per-agent adapters

| Half | What it does | Where |
|---|---|---|
| Resolver (generic) | task id → lock record → host → liveness → implementing agent family → tmux pane | `.aitask-scripts/aitask_live_endpoint.sh` |
| Adapter (per agent) | tmux pane → the agent runtime's own session → deliver | `.aitask-scripts/live_delivery/<family>.md` |
| Composition | write the note, then resolve, then deliver | the `/aitask-note` skill |

**The adapter is a procedure, not a script, and that is structural.** For
Claude Code, the join from a pane to a session needs `ListAgents` and delivery
needs `SendMessage` — model-facing tools with no CLI surface. A shell script
cannot perform that join, which is why the resolver stops at the pane and hands
off.

**Why adapters live under `.aitask-scripts/live_delivery/`, not in a skill
directory.** `aitask_skill_render.sh` is a reachability dep-walker: an `.md`
under `.claude/skills/<skill>/` that nothing references is never rendered into
the per-profile variants (`task-fold-content.md` is already such an orphan). An
adapter is profile-invariant, so it sits outside the skill tree entirely.

**Ordering is the composition's property, not the resolver's.** The resolver
neither appends notes nor calls `SendMessage`, so it cannot promise
durable-first ordering. `ait note --with-live` invokes it only after a
successful append and commit, and its exit status follows the durable lane
alone. `tests/test_note_with_live_composition.sh` pins both.

## Output contract

Exactly **one line on stdout, always**:

| Shape | Exit |
|---|---|
| `LIVE_PANE:<%pane>\|<session>:<@win>.<%pane>\|<pid>\|agent=<family>` | 0 |
| `LIVE_NONE:<reason>` | 0 |
| `LIVE_ERROR:<reason>` | 2 |

`LIVE_NONE` exits 0 because "there is no live endpoint" **is** a successful
resolution. `LIVE_ERROR` is deliberately disjoint from it: it means the
resolver itself could not run. A caller asking "did I get an endpoint?"
branches on the prefix; one asking "did the resolver work?" branches on the
exit status. The two questions never collapse into one.

Usage errors print help to **stderr** and still emit exactly one stdout line,
so a caller reading the first line can never mistake prose for a result.
`-h` / `--help` is the single exception — that invocation is addressed to a
human. Every advisory goes to stderr.

## The degradation table

<!-- Contract: each `| Code | Layer | Meaning |` table in this document has one
code per row, as a backticked token in the first cell; `Layer` names the
component that mints it. tests/test_note_doc_contract.sh compares these tokens,
per layer, against the shipped sources — keep the shape when editing. -->

Every outcome that is not `LIVE_PANE:`, and the layer that produces it. The
durable outcome is the same for every row: **the note is already committed**,
and nothing on this line can undo it.

| Code | Layer | Meaning |
|------|-------|---------|
| `LIVE_NONE:unlocked` | resolver | No lock record — nobody holds the task. |
| `LIVE_NONE:remote_host` | resolver | The lock's `hostname` is not this host. A cross-machine holder degrades to the durable lane instead of being chased. |
| `LIVE_NONE:holder_dead` | resolver | Liveness says the holding process is provably gone. |
| `LIVE_NONE:holder_unknown` | resolver | Liveness could not be established — **including a legacy lock with no `pid:` field at all**, which arrives here as an empty pid. Never collapsed into `holder_dead`: that conflation is the t1465 defect class, and `unknown` is the fail-safe direction. |
| `LIVE_NONE:agent_unknown` | resolver | The task records no `implemented_with` yet. The lock is claimed at task-workflow Step 4 and attribution lands at Step 7, so a task being planned is legitimately locked and blank here. This window must read as unknown, never as an error. |
| `LIVE_NONE:agent_unsupported:<family>` | resolver | The family has no **usable** adapter row in the manifest (see "The registry" below). |
| `LIVE_NONE:no_pane` | resolver | The holder is alive, but no pane on the gateway tmux socket maps to it. |
| `LIVE_NONE:no_session_match` | adapter | The pane was verified, but no row of the agent runtime's session listing matched it. |
| `LIVE_ERROR:usage` | resolver | Wrong argument count, or an empty argument. |
| `LIVE_ERROR:bad_task_id` | resolver | The id is not `N` or `N_M` once a leading `t` is stripped. |
| `LIVE_ERROR:task_not_found:<id>` | resolver | The lock record exists, but no task file resolves for the id. |
| `LIVE_ERROR:resolver_unavailable` | writer | **Minted by `ait note`, never by the resolver**: the resolver produced no parseable `LIVE_*` first line at all — it is missing, not executable, or its contract changed. Kept distinct from "no live endpoint" on purpose. |

## Resolution order

1. **Lock record**, read through `lib/lock_record.sh`. The note writer's sender
   proof reads the same four fields through the same reader, which is what keeps
   the two from drifting about what a lock says. Absent → `unlocked`.
2. **Host scope.** A `hostname` mismatch → `remote_host`. The lock records the
   host precisely so that a cross-machine holder is not chased.
3. **Liveness**, three-valued (`alive` / `dead` / `unknown`), via
   `lock_holder_liveness`.
4. **Implementing agent family** — the part of `implemented_with` before the
   `/`. Derived locally, deliberately **not** with `parse_agent_string`, which
   `die`s on an unrecognised agent: exactly the input the `agent_unsupported`
   branch exists to answer.
5. **Pane.** `pane_pid` first, then a bounded walk up the holder's ancestors
   (20 levels), over the gateway socket only.

Every step is independent of the agent runtime; only the adapter is not.

**The socket boundary, stated honestly.** Only the tmux gateway's socket is
searched (`lib/tmux_exec.sh`). An agent running on a different tmux server
reads as `no_pane`, indistinguishable here from an agent in no pane at all.

## The target string: `window_id`, never `window_index`

`LIVE_PANE`'s middle field is `#{session_name}:#{window_id}.#{pane_id}`.
Measured on the framework's own sessions, a session-listing row renders pane
`%2` as `aitasks:@2.%2`, while tmux reports that same pane's `window_index` as
3 and its `window_id` as `@2` (`#{window_id}` carries its own `@`). A target
built from the index looks right and joins to nothing.

The adapter therefore joins on the **pane id alone**, and treats the
`<session>:<@win>` prefix as display context. The listing's row format is an
*observed* contract of a model-facing tool, not a documented API, and `%N` is
its most stable token.

## Adapters

### The adapter's output contract

<!-- Same contract as the degradation table above. -->

| Code | Layer | Meaning |
|------|-------|---------|
| `LIVE_QUEUED:<session>\|<note-id>` | adapter | The session accepted the note. **Queued, never read**: `success: true` from `SendMessage` means enqueued, and the message drains at the recipient's next tool round — for a session blocked at a prompt, possibly many minutes later. |
| `LIVE_NONE:<reason>` | adapter | Delivery was unavailable after the pane was verified — most often `no_session_match` above. Still a success overall: the note is durably recorded. |

A `no_session_match` report must say **what was searched for** — the pane id,
and how many listed rows carried a tmux column out of how many were listed. A
bare reason code is indistinguishable from "that session ended". If no row
carries the join key at all while many are listed, the listing's rendering has
changed: a framework bug to report, not a dead session.

A note addressed to a task **this** session holds lands on `no_session_match`
by construction, because a session is never listed among its own peers. That
is the right answer, not a missing case: telling yourself what you just wrote
is a no-op.

The payload must carry the **note id**, so the recipient can tie the message to
the exact `## Inbox` entry rather than guessing which note it refers to.

### The registry

`.aitask-scripts/live_delivery/agents.txt` has two whitespace-separated
columns; `#` comments and blank lines are ignored. Column 1 is the agent family
as it appears before the `/` in `implemented_with:`. Column 2 is the adapter
procedure's **filename**, resolved inside that directory. The resolver contains
no agent literal of its own — the manifest alone decides which families are
deliverable.

**A name match is not enough.** A row makes its family supported only when all
of these hold, and failing any one answers `agent_unsupported`, never
`LIVE_PANE`:

- **Column 2 is a bare filename.** A `/` or `..` is refused, not followed: the
  manifest is a data file, and a row must not be able to point the resolver
  somewhere else.
- **The file is a readable *regular* file** — `-f` and `-r`. `-r` alone is true
  for a directory, which is a readable path but not a readable procedure.
- **The row names a procedure at all.** A row with no second column is
  unusable.

The reason is worth keeping: `LIVE_PANE` is a promise the caller acts on — a
live endpoint *and* something to deliver through. Breaking that promise one
layer later leaves the caller with nothing to run after it has already been
told the endpoint is live. A missing manifest means no family is deliverable,
not an error.

### Adding an adapter for a new agent runtime

A data change, not a code change:

1. Add a row to `agents.txt`: `<family>  <family>.md`.
2. Put the procedure file beside it. It must be **non-executable** — adapters
   are procedures, not scripts.
3. The procedure must state the `send-keys` prohibition, name the **pane id** as
   its join key, and require the `no_session_match` diagnostic.
4. It reports exactly `LIVE_QUEUED:<session>|<note-id>` or `LIVE_NONE:<reason>`,
   and carries the note id in what it sends.

`tests/test_live_endpoint_no_sendkeys.sh` walks the manifest and enforces steps
2 and 3 for every adapter it names, and fails on anything executable under
`live_delivery/`.

### Current state

`claudecode` is the only family that resolves. Codex and OpenCode are **absent
by decision, not omission**. Measured on codex-cli 0.151.0,
`codex queue --thread <UUID|exact name> --message` exists, but `codex agents` is
an interactive TUI with no machine-readable listing, so there is no scriptable
way to enumerate Codex sessions or map one to a pane — nothing could resolve a
verified pane to a session. Both families answer `agent_unsupported:<family>`
today. Revisit when a listing exists.

## tmux is discovery, never transport

The standing rule, stated in the resolver header and in every adapter:
`send-keys` must never deliver a note. Keystroke injection lands in whatever UI
state a pane happens to be in — a prompt, a shell, an editor, a half-typed
answer — carries no agent identity or message framing, and offers no
queued/received semantics. Delivery goes through the agent runtime's own
cross-session mechanism, or it does not happen.

It is enforced as an **allowlist**, not a denylist.
`tests/test_live_endpoint_no_sendkeys.sh` pins the tmux verbs the resolver may
issue — `list-panes`, and nothing else — and additionally names `send-keys`,
`paste-buffer`, `run-shell`, `load-buffer`, `set-buffer` and `respawn-pane` for
a clear failure message. The allowlist is what catches a new transport verb
nobody thought to deny. All tmux access also goes through `lib/tmux_exec.sh`,
which `tests/test_no_raw_tmux.sh` enforces.

## Known limits

- `LIVE_QUEUED` proves enqueue, not receipt; there is no read-back.
- The session listing's row format is observed, not documented. If a runtime
  changes it, the adapter's join breaks — and the required `no_session_match`
  diagnostic is what makes that visible rather than silent.
- Only the gateway tmux socket is searched.
