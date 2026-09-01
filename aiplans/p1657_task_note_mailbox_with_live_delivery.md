---
Task: t1657_task_note_mailbox_with_live_delivery.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1657 — Task note mailbox with live delivery

## Context

A task can record something for its own archive, or spawn a follow-up carrying
context. It has **no way to tell an already-existing task something**. The only
channel today is a human copying text between panes.

This is not theoretical. While this very plan was being written, session
`fix-worker-peak-space-path` hand-delivered a design critique of t1657 — by
appending to the task file and sending a cross-session message, i.e. by
hand-rolling both lanes this task exists to build. That note is now sitting in
the task body as unstructured prose below a `---` separator. It is the first
real inbox entry, and it arrived before the mailbox did.

**Goal:** two things, and the second is deliberately larger than "notes".

1. A durable, attributed, append-only `## Inbox` on the target task file,
   surfaced at pick time. This is the product; it works whether or not anyone is
   watching.
2. A reusable **live-endpoint resolution** boundary — *"find the live agent
   implementing task X"* — that turns the manual lock → PID → pane → session
   cross-reference into one task-centric operation. Notes are its first consumer,
   not its owner.

## Findings that shape the design (all verified this session)

1. **`SendMessage` is agent-only — no CLI exists.** A bash helper can never
   deliver live. It can only resolve *task → tmux pane id*; the **skill** does the
   `ListAgents` match and the send. So the helper must never print
   `NOTE_DELIVERED_LIVE:` — that would be a claim it cannot make.
   `ListAgents` rows carry `tmux <session>:@<win>.%<pane>`, so the pane id is the
   join key.

2. **`## Gate Runs` is EOF-anchored.** `_gate_append_locked`
   (`aitask_gate.sh:400-420`) and `gate_ledger.append_block`
   (`lib/gate_ledger.py:483`) both append at EOF whenever the section exists.
   An `## Inbox` placed *after* it would silently capture every future gate
   block. **`## Inbox` must be inserted before `## Gate Runs`.**

3. **The cross-PC merge engine will conflict on inbox appends.**
   `aitask_merge.py::_split_gate_section` treats everything before `## Gate Runs`
   as "head" and requires the two heads to be **byte-equal** to auto-union. Two
   PCs appending notes concurrently produce different heads → whole-body conflict
   markers. `_section_is_clean` also rejects any non-blockquote line in the
   ledger section, so putting Inbox after Gate Runs breaks the union too. The
   union needs generalizing to two append-only sections.

4. **The lock already carries the resolver's inputs, but not agent type.**
   `aitask_lock.sh` writes `locked_by / locked_at / hostname / pid /
   pid_starttime / pid_starttime_kind` (`aitask_lock.sh:294-299`) and nothing
   else. `lib/pid_anchor.sh::lock_holder_liveness` returns the three-state
   `alive | dead | unknown` verdict, and `get_session_anchor_pid` anchors the
   lock to the **tmux pane process**, so the recorded pid *is* the pane pid for
   framework-launched agents.

5. **Deliverable 3's degradation list has a verified hole.** It covers
   "unlocked, remote, or dead". A **Codex-held task is none of those** — locked,
   local, alive, and simply absent from `ListAgents`. Confirmed on this host:
   `codex-cli 0.151.0` exposes `codex queue --thread <UUID|exact name> --message`,
   but `codex agents` is an **interactive TUI with no `--json`** — there is no
   scriptable way to enumerate Codex sessions or map one to a pane. So a Codex
   holder can be *detected* but not *addressed*.
   `implemented_with` is the discriminator, and it is written by Agent
   Attribution at **Step 7** while the lock is claimed at **Step 4** — during
   planning a task is `Implementing` and locked with the field still **empty**.
   That window must read as *unknown → durable lane*, never as an error.

6. **Pick-time reading is three trees, not one.** `aitask-pick` exists under
   `.claude/skills/`, `.agents/skills/` and `.opencode/skills/`.

## Design

### The `## Inbox` section

Mirrors the `## Gate Runs` ledger exactly — append-only marker-first
blockquotes, state derived back-to-front, machine-owned:

```markdown
## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t349** id=2026-09-01T08:43:11Z.9f2c1a7be3d4085c6b1e2fa0 from=t349 from_verified=yes at=2026-09-01T08:43:11Z base=6169d645b base_branch=main dirty=no host=omg16
>
> | t357's line numbers are already stale; the blast radius is wider than the
> | spawning bullet implied.

> **👁 note:read** id=2026-09-01T09:02:44Z.4b70de915cc82f36a1084e77 by=t357 at=2026-09-01T09:02:44Z mode=explicit ids=2026-09-01T08:43:11Z.9f2c1a7be3d4085c6b1e2fa0
```

Marker lines carry only framework-generated fields; **every byte of user text
lives behind the `> | ` sentinel**. That is the whole injection defence, and it
is why the two line shapes are structurally distinguishable rather than merely
conventionally different.

- **`id`** = `<iso-utc>.<24-hex>` — 96 bits from a CSPRNG, not 16. A 4-hex
  suffix gives only 65 536 values per second, which *reduces* the same-second
  hazard without removing it; two parallel senders could mint distinct notes
  sharing one identity, and since `ids=` is the association key, a receipt would
  then acknowledge the wrong entry. Ids are opaque, never renumbered, and
  ordering comes from the timestamp prefix, never from the suffix.
- **Uniqueness is checked, not just improbable.** The id is minted *inside* the
  per-task append lock and verified absent from the section before the write, so
  within a checkout uniqueness is a guarantee. The 96-bit width is what covers
  the case no lock can — two checkouts appending concurrently on different PCs.
- **`base` / `at` / `dirty`** — the two staleness axes. `base` fixes
  *tree-relative* claims (line numbers); `at` + `dirty=yes` flag
  *moment-relative* ones (a `git status` reading), which no SHA can catch.

#### `base` provenance is specified, because the obvious implementation is wrong

This repo has **two live HEADs**, and `aitasks/` is a **symlink into the data
worktree** (`aitasks -> .aitask-data/aitasks`). Measured here:

| queried from | HEAD | branch |
|---|---|---|
| repo root | `6169d645b` | `main` — the code tree a line-number claim means |
| `.aitask-data` | `3f33c1b5b` | `aitask-data` — where the mailbox commit lands |

Resolving git context from the *task file's own path* — the natural thing to
write, since that is the file being appended to — therefore records the
**mailbox** SHA. That is not merely ambiguous: it is a confident, wrong answer to
the one question `base` exists to answer, and it silently defeats the task's
stale-context non-negotiable.

The algorithm, pinned:

1. **Queried from the code repository root** (`AIT_DIR`), explicitly **never**
   from the task-file path, `aitasks/`, or `.aitask-data`.
2. **Captured before** the durable append and its commit, so the value describes
   the tree the sender was looking at and is independent of write ordering.
3. Fields, each true or absent — never fabricated:
   - `base=<short-sha>` — code-repo `HEAD`, the exact tree the claim was made
     against;
   - `base_branch=<abbrev-ref>` — context for the reader;
   - `base_mergebase=<sha>` — written **only** when HEAD is not on the primary
     branch and a merge base exists, so a recipient who cannot resolve a private
     task-branch tip still has an ancestor they can.
4. **Degraded cases get explicit sentinels, never an empty or invented value**,
   because a missing field would read as "fine" to a parser:
   `base=none` (no git repository) · `base=unknown` (git present but HEAD
   unresolvable — unborn branch, no commits).
5. **`dirty` is computed against the code repo too.** Computed in the data
   worktree it would read `yes` almost always — task files are perpetually being
   written — making the field pure noise exactly where it is supposed to carry
   the moment-relative warning.
- **Read state** = entries whose `id` appears in **no** `note:read` receipt's
  `ids=` list. Set-union semantics: order-free, same-second-safe, merge-friendly,
  and needs **no** frontmatter field.

#### The body is untrusted input — and this is a *new* surface

The gate ledger's body lines are fixed labels (`Verifier:`, `Result:`, `Log:`,
`Note:`) built from controlled values. `ait note` is the **first** writer to put
arbitrary user/agent text inside a marker-parsed block, so the ledger's format
has never had to be injection-resistant and is not, by itself, safe to reuse
verbatim for bodies.

Concretely: markers match `^>\s*\*\*` . A body line emitted as plain `> <line>`
whose text begins `**👁 note:read** … ids=…` **is** a syntactically valid receipt.
A note could forge an acknowledgement for entries it never delivered.

**Sanitize at the write site, with a structural separation rather than escaping:**

- Every body line is emitted as **`> | <line>`**. The pipe sentinel sits between
  the quote marker and the text, so `^>\s*\*\*` can never match a body line —
  a forged marker becomes inert text. It also neutralizes `## Inbox` /
  `## Gate Runs` in a body: prefixed and quoted, they are no longer headings and
  cannot move a section boundary.
- Write-site normalization: reject NUL, strip CR, normalize line endings, and
  bound the body to a documented maximum size.
- **Parsers reject, never repair.** A block that does not conform is surfaced as
  malformed rather than best-effort parsed, and the merge union already bails to
  conflict markers rather than guessing (its `_section_is_clean` guard).

**`from=` is a claim, not an authentication.** Nothing stops a sender asserting
any task id. It is rendered as *claimed* everywhere it is displayed. The one
verifiable fact is added separately: `from_verified=yes` is written **only** when
the writing process provably holds the lock on the claimed sender task at write
time, and is otherwise absent — never `no`, so absence and disproof are not
conflated.

### Two lanes

| lane | when | mechanism |
|---|---|---|
| **durable** (always) | unconditional | append to target's `## Inbox`; path-scoped `./ait git` commit |
| **live** (opportunistic) | locked ∧ same host ∧ `liveness == alive` ∧ agent is Claude | resolver emits pane id; **skill** matches `ListAgents` + `SendMessage` |

**Ordering is a contract, not a sequence.** The durable append completes —
appended *and committed* — **before** any live attempt begins, and its success is
independent of it. Live delivery can only ever be an accelerator on top of a note
that is already safe.

### Live-endpoint resolution is infrastructure, not a detail of `ait note`

The primitive is **"find the live agent implementing task X."** Notes are its
first consumer, not its owner. The whole user-facing value is that a sender
addresses a **task id** and never has to discover, by hand, (1) whether the task
is being implemented, (2) the holder's lock/PID, (3) its tmux pane, (4) which
agent session owns that pane, or (5) how to route a message there. That manual
cross-reference — the three steps this task's Origin documents someone performing
by hand — is precisely what gets collapsed into one task-centric operation.

So it is built as a boundary with two layers:

```text
task id
  → validated local lock holder          ─┐
  → PID + start-time verification         │ generic, agent-runtime independent
  → tmux pane identity                    │ (shared framework infrastructure)
  → LIVE_PANE:… | LIVE_NONE:<reason>     ─┘
  → native agent-session match           ─┐ per-agent adapter
  → queued native message                ─┘
```

| layer | owns | must not know |
|---|---|---|
| **generic resolver** (`aitask_live_endpoint.sh`) | lock validation, same-host check, live-PID + start-time verification, PID→pane correlation, structured output | anything about Claude, Codex or OpenCode |
| **agent adapter** (a *skill procedure*, per Finding 1) | correlating the verified pane with that runtime's session listing, calling its native message API, reporting **queued**, never "read" | how a task maps to a pane |

The adapter is a skill procedure rather than a script because `SendMessage` and
`ListAgents` are model-facing tools with no CLI — the join can only happen agent-
side. The resolver hands the adapter an `agent=<family>` field (from
`implemented_with`) so the skill knows which adapter to dispatch to.

**The calling workflow invokes this automatically.** No sender ever inspects tmux
or enumerates agent sessions themselves; if they have to, the feature has failed
at its actual purpose.

### One composition point, and a stable note id threaded through it

The writer, the resolver and the adapter are three pieces; exactly **one** thing
composes them — the `aitask-note` skill (_5). Every caller, including the _5
trigger points, invokes **the skill**, never the pieces. There is no second,
caller-side join to drift.

```text
1. resolve target task id        (explicit arg, else Related Task Discovery)
2. ait note <target> --from <id> --text …
       → NOTE_APPENDED:<note-id>|<path>      ← durable, committed, AUTHORITATIVE
3. aitask_live_endpoint.sh <target>
       → LIVE_PANE:…|agent=<family>  |  LIVE_NONE:<reason>
4. adapter(agent=<family>, pane, note-id, body)        [only on LIVE_PANE]
       → LIVE_QUEUED:<session>|<note-id>  |  LIVE_NONE:<reason>
5. report both outcomes
```

**Step 2 completes before step 3 begins.** The note is on disk and committed
before any live attempt exists.

**The note id is the join key and is threaded end-to-end.** `ait note` emits it,
and the adapter's live payload *carries* it — so the recipient can tie the
message it just received to the exact `## Inbox` entry, and a reader can tell a
live-delivered note from a second, unrelated one. A live payload that cannot name
its durable entry is the failure this thread guards against.

**Two results, one authority.** The CLI reports only what a shell process can
know — the durable write. The adapter's live outcome is reported separately by
the agent, because `ListAgents`/`SendMessage` have no CLI. **The durable result
is authoritative**: `LIVE_NONE:<reason>` following `NOTE_APPENDED:` is a
**success**, not a partial failure, and must be reported as one.
`LIVE_QUEUED` means *enqueued*, never *read*.

### tmux is discovery infrastructure, never the transport

**`send-keys` must not be used to deliver a note.** It injects keystrokes into
whatever UI state the pane happens to be in — a prompt, a shell, an editor, a
half-typed answer — carries no agent identity or message framing, and can offer
no queued/received semantics. tmux is used *only* to safely identify the endpoint
pane. Delivery goes through the agent runtime's own cross-session mechanism, and
the durable inbox stays authoritative whether or not live delivery is available.

### Degradation: a complete enumeration, every branch a successful durable note

| `LIVE_NONE:<reason>` | condition |
|---|---|
| `unlocked` | no lock — nobody holds the task |
| `remote_host` | lock's `hostname` ≠ this host |
| `holder_dead` | `lock_holder_liveness` → `dead` |
| `holder_unknown` | `lock_holder_liveness` → `unknown` (never read as dead) |
| `no_pane` | PID alive but no tmux pane maps to it |
| `agent_unsupported:<agent>` | holder is Codex/OpenCode — no scriptable session listing |
| `agent_unknown` | `implemented_with` empty — the Step 4 → Step 7 window |
| `no_session_match` | pane verified, but no agent session row matches it |

None is an error, and **every one leaves the durable note successfully
appended and committed.**

**Out of scope, now explicit:** cross-agent-type live *delivery*. Not an
oversight — `codex agents` has no machine-readable listing, so there is nothing
to resolve against. The resolver still *detects* and reports the case; only the
adapter is missing. A follow-up is spawned for when that changes.

### Discoverability — the capability has to be *reachable*, not just present

A helper no agent knows to reach for is dead weight, and the task body says
nothing about how an agent learns that `ait note` exists. Three layers, each
carrying a different guarantee:

| layer | surface | reaches |
|---|---|---|
| **always-loaded** | `seed/aitasks_agent_instructions.seed.md` → `AGENTS.md`, `.codex/instructions.md`, `.opencode/instructions.md` (generated), plus hand-maintained `CLAUDE.md` | **every agent, every session, no invocation** |
| **listed skill** | `.claude/skills/aitask-note/` — its *description* is the hook, the way `ait-git`'s is | Claude, on demand, with depth |
| **trigger points** | the workflow moments where noting is the right move | the agent at the moment of the decision |

`ait-git` is the precedent for layer 2: a small static skill that exists purely
to teach a CLI convention, and it lives in `.claude/skills/` **only**. Per
CLAUDE.md ("do the Claude Code version first; suggest separate aitasks for the
other agents"), the skill is Claude-first with a port follow-up — and layer 1,
which *does* fan out to all three instruction files through
`assemble_aitasks_instructions`, is what keeps the **cross-agent** story true in
the meantime. That split matters: the durable lane is agent-agnostic by design,
so a Codex agent must be able to *send* even before it has the skill.

The trigger points are not new policy — they are where this repo's existing
"hand findings to the owning task, not the current one" convention already
applies, and today has no mechanism to act on.

## Decomposition — 6 children

The blast radius spans bash, the Python merge engine, Jinja skill templates +
goldens across three agent trees, and docs. Each child below is independently
testable and lands on its own. They are ordered by dependency: _1 is a
behaviour-preserving refactor, _2 builds the writer on it, _3-_5 add the reading,
live and discoverability surfaces, _6 documents the result.

### t1657_1 — Promote the ledger-block substrate to a shared seam

**Zero behaviour change.** Ships nothing user-visible; its whole acceptance
criterion is that the existing gate suite and goldens stay green while the
duplicated-by-t1657_2 primitives move behind one seam. Lands first so the note
writer is built **on** the seam rather than beside it — a de-duplication
follow-up would mean shipping ~180 lines of near-duplicate code and trusting a
later reconciliation that this repo has already watched drift once
(`aitask-audit-wrappers` exists for exactly that reason).

#### Pre-phase (risk mitigations)

- **`characterize_merge_union`** — before touching anything, pin
  `aitask_merge.py`'s *current* union behaviour in a characterization test: the
  happy union, and each guard's bail-to-conflict path (unclean section, invalid
  `run` id, ambiguous winner, divergent heads). The extraction is then a change
  whose blast radius is measured, not assumed.

#### Main steps

- **`lib/ledger_block.py`** — extract from `lib/gate_ledger.py`, parameterized on
  the block namespace (`gate:` → `<ns>:`) and the section header:
  `iso_now`, `_atomic_write`, marker-block **parse** (today `parse_gate_run_blocks`,
  whose `MARKER_RE` hardcodes `gate:`), marker-block **build** (`build_block`),
  and section ensure-and-append (`append_block`, today EOF-hardcoded — it grows a
  **section-order** argument so a section can be inserted *before* a named one).
- **`lib/ledger_block.sh`** — the bash twin: the per-task append lock
  (`acquire_gate_lock` / `release_gate_lock` / `_gate_lock_exit_trap`
  generalized over a key namespace) and the marker/body block formatter from
  `_gate_append_locked`.
- **`aitask_merge.py`** — generalize `_union_gate_runs` into an
  **ordered-append-only-sections** union, keeping every existing guard intact.
- **Re-point** `aitask_gate.sh` and `lib/gate_ledger.py` at the seam. Everything
  gate-specific stays exactly where it is — `next_attempt`, `live_run`,
  `derive_status`, the summary formatters, and the whole registry /
  active-gates / digest half (~90% of `gate_ledger.py`) are **not** promoted.

#### Acceptance

- The full gate + merge test suites pass **unchanged** — no test is edited to
  accommodate the refactor. That is the whole proof.
- `bash tests/run_all_python_tests.sh` and every `tests/test_gate_*.sh` green.

### t1657_2 — Durable lane: `## Inbox` format + `ait note` writer

Built on the t1657_1 seam.

- **`.aitask-scripts/aitask_note.sh`** — same shape as `aitask_gate_record.sh`:
  append via the seam, then `task_git add -- <file>` + path-scoped commit +
  best-effort `task_push`. Takes the seam's append lock with key `note_<id>`.
  `ait note <target-id> --from <id> [--text ... | --file ...]`
- **Insert before `## Gate Runs`** (Finding 2) — this is the load-bearing
  invariant; a test must pin it by appending a note *and then* a gate block and
  asserting the gate block lands under `## Gate Runs`.
- Output contract — **durable only, and authoritative**:
  `NOTE_APPENDED:<note-id>|<path>` · `NOTE_TARGET_MISSING:<id>` ·
  `NOTE_SELF:<id>` (refuse self-addressed) · `NOTE_ERROR:<reason>`.
  The `<note-id>` leads because it is the join key every later stage threads.
  The CLI emits **no** live-delivery outcome — it cannot observe one (Finding 1);
  `LIVE_QUEUED` / `LIVE_NONE` are reported separately by the adapter.
- **Write-site hardening** (see Design): `> | ` body-line sentinel, NUL/CR
  rejection, bounded body size, `from=` recorded as a claim with
  `from_verified=yes` only on provable lock ownership.
- **Identity and provenance** (see Design): 96-bit CSPRNG id minted and
  uniqueness-checked under the append lock; `base` / `base_branch` /
  `base_mergebase` / `dirty` captured from the **code repo root before** the
  append, with `none` / `unknown` sentinels for the degraded cases.
- Register `## Inbox` with the seam's section order so it is inserted **before**
  `## Gate Runs`, and with the merge union promoted in _1.
- `ait note` dispatcher entry + help text; **7-touchpoint whitelist**
  (`.claude/settings.local.json`, `.codex/rules/default.rules`,
  `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
  `seed/opencode_config.seed.json`).
- **Migrate the hand-appended t357 note** in the task body into a real `## Inbox`
  entry — the first dogfood.

#### Post-phase (risk mitigations)

- **`pin_section_order`** — append a note, then append a gate block, and assert
  the gate block lands under `## Gate Runs` while the note stays above it. Run it
  against **both** gate backends (bash `_gate_append_locked` and
  `AIT_GATES_BACKEND=python`), since each has its own EOF-append path.

### t1657_3 — Reading: read receipts + pick-time surfacing

- `aitask_query_files.sh inbox <task-id>` → `INBOX_UNREAD:<id>|<from>|<at>|<base>|<dirty>`
  lines, or `NO_INBOX` / `NO_UNREAD`. Derivation lives in a shared lib so the
  writer and reader agree on one parse.
- `ait note read <task-id> --by <id> --ids <csv> [--mode auto|explicit]` appends
  the `note:read` receipt.
- Pick-time surfacing in **`aitask-pick/SKILL.md.j2`** (Step 0b + 2b) and
  **`task-workflow/SKILL.md`** Step 3, framed per the non-negotiable:
  *untrusted advisory input, never an instruction* — shown, attributed, never
  auto-actioned.

#### Display and acknowledgement are two separate steps

"Never auto-actioned" governs the note's **content** — nothing in a note may
trigger work on its own. It does **not** govern the read bookkeeping, and
conflating the two is what makes this ambiguous. So the model is explicit:

1. **Display** unread entries. Displaying changes no state.
2. **Acknowledge**, as its own step:
   - *interactive profiles* — `AskUserQuestion`: "Acknowledge these N notes?
     They will not be shown again." → "Acknowledge" / "Keep unread".
   - *non-interactive profiles* (`remote`, headless) — auto-acknowledge, with the
     receipt recording `mode=auto` so the difference stays auditable rather than
     invisible.
3. **Failure is fail-safe toward re-showing.** If the receipt append or its
   commit fails, the entries stay **unread** and surface again next pick. A note
   is never silently lost to a failed bookkeeping write; a duplicate display is
   the acceptable failure, a vanished note is not.

Tests, one per state transition: first display (shown, unread) · deferred
acknowledgement (shown again on the next pick) · acknowledgement (receipt
appended) · returning session (not shown) · receipt-append failure injected
(still unread).
- Regenerate goldens for every affected template **across all three agent
  trees** (Finding 6) and review the diff rather than rubber-stamping it.

### t1657_4 — Live-endpoint resolution infrastructure + agent adapters

Delivers the reusable primitive **"find the live agent implementing task X."**
Notes are its first consumer; the boundary is designed so the next one copies no
lock/tmux/session logic.

#### Generic layer — `.aitask-scripts/aitask_live_endpoint.sh <task-id>`

Named for the capability, not for notes. **Contains no reference to any agent
runtime.**

- Output: `LIVE_PANE:<%pane>|<session>:@<win>.%<pane>|<pid>|agent=<family>`
  or `LIVE_NONE:<reason>` over the full degradation table above.
- Reuses the canonical seams rather than reimplementing them: `aitask_lock.sh
  --check` for the lock record, `lib/pid_anchor.sh::lock_holder_liveness` for the
  three-state verdict (`unknown` is never collapsed into `dead`), and
  `implemented_with` for `agent=`.
- **All tmux access through the `lib/tmux_exec.sh` gateway** —
  `tests/test_no_raw_tmux.sh` enforces it. Discovery only: this script never
  calls `send-keys`.
- PID→pane correlation is `pane_pid`-first (the lock anchors to the pane process
  by construction — `get_session_anchor_pid` rung 2), with an ancestor walk as
  fallback so an `AIT_AGENT_PID`-anchored lock (rung 1) still resolves.

#### Adapter layer — per agent runtime

- `task-workflow/live-delivery-claude.md`: given a verified `LIVE_PANE`, match
  the `%pane` against the `ListAgents` row's `tmux <session>:@<win>.%<pane>`
  column, then `SendMessage`. Reports **queued**, never "read" —
  `success: true` means the message is enqueued and drains at the recipient's
  next tool round.
- Codex/OpenCode adapters are **absent by decision, not by omission**: the
  resolver reports `agent_unsupported:<agent>` and the durable note stands. The
  follow-up for a Codex adapter is spawned here.

#### Explicit requirements

1. **No sender-side manual discovery.** The calling workflow invokes the resolver
   automatically. A sender addresses a task id and nothing else. If any path
   requires a human or an agent to run `tmux list-panes` or enumerate sessions by
   hand, the child has not met its goal.
2. **A documented resolver contract + degradation table** — every reason code,
   its trigger, and its guaranteed durable outcome (lands in `aidocs/`, _6).
3. **Agent-runtime adapters** own the native send and nothing else.
4. **Durable-first ordering is verified, not assumed**: the note is appended and
   committed *before* any live attempt, and a forced adapter failure must leave
   the durable note intact.
5. **tmux is never the transport.** A test asserts no `send-keys` on any delivery
   path.

#### Acceptance

- A task id resolves to the correct live agent **solely through the
  infrastructure** — verified end-to-end against a real second session on this
  host, not a replica.
- Each degradation branch is exercised through a documented seam (lock removed,
  `hostname` rewritten, PID killed, `implemented_with` set to a Codex string,
  cleared for the Step 4→7 window) and each leaves `NOTE_APPENDED:` intact.
- `grep -rn 'ListAgents\|SendMessage\|claudecode' .aitask-scripts/aitask_live_endpoint.sh`
  returns nothing — the generic layer stays agent-independent.

### t1657_5 — Discoverability: the `aitask-note` skill + instruction surfaces

Makes the capability reachable, **and is the single composition point** that
binds writer + resolver + adapter (see Design). Depends on _2 (writer) and _4
(resolver + adapter) — not _3, which is the independent read side.

- **`.claude/skills/aitask-note/SKILL.md`** — static, `user-invocable: true`,
  modeled on `ait-git`. The description is the discoverability hook and must
  state the *when*, not just the what: "Send a durable note to an existing
  aitask — context it needs that is not itself work."
  Two entry paths, an **explicit mode selector** rather than an inferred one:
  - **explicit target** (`/aitask-note 357 --from 1657 --text ...`) — zero
    prompts, so the skill is usable headlessly and from another skill;
  - **discovery** — reuse the existing **Related Task Discovery Procedure**
    (`task-workflow/related-task-discovery.md`) to answer "which existing task
    should hear this?", rather than reinventing task matching.

  It also carries the judgement the helper cannot: **note vs. spawn a task** —
  a note is for *context about work that already exists*; if the content is
  itself work, create a task. And the trust posture: notes are advisory, get
  attributed, and are never auto-actioned.
- **It owns the 5-step composition contract** from the Design section: write →
  capture `<note-id>` → resolve endpoint → dispatch adapter *with the note id and
  body* → report both outcomes, durable authoritative. The trigger points and any
  future caller invoke **this skill**; nothing else composes the pieces, so there
  is no second join to drift.
- **Always-loaded surfaces:** a short `## Sending Notes to Other Tasks` section
  in `seed/aitasks_agent_instructions.seed.md`, regenerated into `AGENTS.md`,
  `.codex/instructions.md` and `.opencode/instructions.md` via
  `assemble_aitasks_instructions` + `insert_aitasks_instructions` (**drive the
  generator — never copy the block out of `AGENTS.md`**, which would destroy
  each mirror's per-agent tail), plus the hand-maintained `CLAUDE.md` block.
  Guarded by `tests/test_agent_instructions.sh` T25–T27, which compare all three
  tracked surfaces byte-for-byte against the live generator.
- **Trigger points** — wired at a *small* number of high-value sites, not
  everywhere: the follow-up/finding paths in `task-workflow` Step 8d,
  `aitask-qa` and `aitask-review`, where a finding belongs to a task that
  already exists. Each is a one-line offer, never automatic.
- Spawn the follow-up for the Codex / OpenCode skill ports.

### t1657_6 — Documentation

**Website — `ait note` gets a full CLI reference page, not a mention.** It is a
new top-level dispatcher command, so it is documented the way `ait lock` and
`ait gates` are:

- **`website/content/docs/commands/note.md`** — its own page, matching the
  house shape of `commands/lock.md`: frontmatter (`title: "Note"`,
  `weight: 37` — between `lock` 36 and `gates` 38, `depth: [intermediate]`), a
  `## ait note` heading, a usage block, and a **flags table** covering
  `<target-task-id>`, `--from`, `--text`, `--file`, and `read --by`. It documents
  the **structured output contract** (`NOTE_APPENDED:<note-id>|<path>` /
  `NOTE_TARGET_MISSING:` / `NOTE_SELF:` / `NOTE_ERROR:`) and the `LIVE_*` reason
  codes with their exit semantics — the same way `lock.md` documents its exit
  codes 0/1/13/14 — since those are the parts a scripting user actually needs.
  It documents the **`base` provenance contract** — which repository is queried,
  that capture happens before the append, and what `none` / `unknown` mean — so a
  reader knows exactly what tree a note's claims can be checked against.
  It must state plainly **which result is authoritative**: the CLI reports the
  durable write and nothing else; live outcomes come from the agent adapter; and
  `LIVE_NONE:<reason>` after a successful append is a success. It also documents
  that `from=` is a **claim** and what `from_verified=` does and does not prove.
- **`commands/_index.md`** — a row in the **Task Management** table:
  `` | [`ait note`](note/) | Send a durable, attributed note to another task's inbox | ``
  and a second row for the read side. This index is hand-maintained; a page that
  is not listed here is effectively invisible.
- **`website/content/docs/workflows/task-notes.md`** — the end-to-end story (when
  to note vs. spawn a task, both lanes, the trust posture) + its entry in the
  manually maintained `workflows/_index.md` under **Tasks**.
- Cross-link from `commands/lock.md` and `concepts/locks`, since live-endpoint
  resolution reads the lock record.
**Internal (`aidocs/`) — the contracts a future maintainer needs:**

- `aidocs/framework/task_note_mailbox.md`: the entry format, section-ordering
  invariant, the merge contract, and the trust posture.
- `aidocs/framework/live_endpoint_resolution.md` — **its own document, because
  the boundary outlives notes**: the resolver contract, the full degradation
  table with each reason's trigger and guaranteed durable outcome, the
  generic/adapter split, how to add an adapter for a new agent runtime, and the
  standing rule that **tmux is discovery, never transport**.

### Manual-verification sibling

Auto-offered after child creation. Live delivery genuinely needs two real
sessions on one host and cannot be asserted from a unit test.

## Verification

- `bash tests/test_note_append.sh` — format, ids, `base`/`at`/`dirty`, self-send
  refusal, missing target.
- **Section-ordering test** — note, then gate append, assert the gate block is
  under `## Gate Runs` and the note is not.
- **Concurrency test** — parallel `ait note` calls to one task; assert every
  entry survives and none is renumbered.
- `bash tests/run_all_python_tests.sh --test-dir tests` for the merge union,
  including the bail-to-conflict negative controls.
- `bash tests/test_skill_render_aitask_pick.sh` (goldens),
  `bash tests/test_no_raw_tmux.sh`, and `bash tests/test_agent_instructions.sh`
  (T25-T27 catch seed-vs-mirror drift on the always-loaded surfaces).
- `shellcheck .aitask-scripts/aitask_note*.sh`
- `./.aitask-scripts/aitask_skill_verify.sh`
- End-to-end dogfood: `ait note 1657 --from 1657 --text ...`, confirm the entry,
  the path-scoped commit, and that pick surfaces it exactly once.
- `cd website && hugo build --gc --minify` builds clean, and every new
  cross-reference resolves — Hugo does **not** fail a dead `#fragment`, so anchor
  targets are checked by hand against the rendered ids.
- **Discoverability check** (the point of _5): in a fresh session that has *not*
  read this plan, confirm `ait note` is reachable from the always-loaded
  instructions alone, and that `aitask-note` appears in the skill listing with a
  description that conveys *when* to use it.
- **Forced-collision test** (note identity): with the CSPRNG stubbed to a fixed
  value so two writers mint the same suffix *deterministically* — not merely a
  parallel-write test, which would almost never collide — assert (a) the
  in-lock uniqueness check detects it and re-mints within a checkout, and
  (b) two checkouts that both produced it are surfaced by the merge's
  ambiguous-identity guard as a conflict rather than silently deduplicated.
- **`base` provenance tests** (staleness): in this repo's own branch-mode layout,
  assert `base` equals the **code-repo** HEAD and **not** `.aitask-data`'s;
  `dirty` reflects the code tree, not the perpetually-dirty data worktree; a
  detached / task-branch HEAD emits `base_mergebase=`; and the degraded cases
  emit the `base=none` / `base=unknown` sentinels rather than an empty or
  fabricated SHA. Capture-point test: a note written while the data branch has
  uncommitted changes still records the code HEAD.
- **Injection round-trip** (concern 3): a note body containing a literal
  `**👁 note:read** … ids=…` line, a `## Gate Runs` line and a `## Inbox` line
  must round-trip as inert body text — parsing the section afterwards must yield
  **one** entry, **zero** receipts, and an unchanged section boundary. Plus NUL /
  CR / oversized-body rejection, and `from_verified=` present only with a real
  lock.
- **Composition + authority** (concerns 1 and 4): a forced adapter failure after
  a successful write leaves `NOTE_APPENDED:<id>|<path>` intact and is reported as
  a **success with live delivery unavailable**, not a partial failure; and the
  live payload names the same `<note-id>` that is in the target's `## Inbox`.
- **Acknowledgement lifecycle** (concern 2): the five transitions listed in _3,
  including the injected receipt-append failure that must leave entries unread.
- **Endpoint-boundary check** (the point of _4): a task id resolves to the right
  live agent with no manual tmux or session inspection anywhere on the path; the
  generic resolver greps clean of agent-runtime names; and no delivery path calls
  `send-keys`.
- **Substrate check** (the point of _1): after _2 lands, no marker-block parse,
  build, section-append or append-lock logic exists in two places —
  `grep -n 'MARKER_RE\|acquire_.*_lock\|append_block' ` over the gate and note
  paths resolves to the one seam.

## Risk

### Code-health risk: **medium**

- The t1657_1 extraction touches the gate ledger and the cross-PC merge union —
  both load-bearing — for a consumer that does not exist yet · severity: medium ·
  → mitigation: inline pre-phase characterize_merge_union, plus _1's
  no-test-may-be-edited acceptance rule, which turns "zero behaviour change"
  from an intention into a check that can fail
- `## Inbox` placed after `## Gate Runs` would silently swallow every future
  gate block — an invariant enforced by convention, not by the type system ·
  severity: high · → mitigation: inline post-phase pin_section_order
- Three agent trees × three profiles of goldens drift independently ·
  severity: low · → mitigation: existing `test_skill_render_*` + `aitask_skill_verify.sh`
- New body content is destroyed by `aitask_update.sh --desc-file` — a
  pre-existing hazard `## Gate Runs` already shares, not introduced here ·
  severity: low · → mitigation: documented in `aidocs/`, no code change

### Goal-achievement risk: **low**

- The headline requirement — "tell a task nobody is working on yet" — is served
  entirely by the durable lane, which has direct working precedent in
  `aitask_gate_record.sh` and no novel mechanism.
- The live lane's feasibility is settled rather than assumed: the pane-id join
  key is confirmed present in `ListAgents`, and the one enumeration hole is
  closed by an explicit scope decision rather than left silent.
- Widening _4 from "a note delivery step" to a reusable endpoint boundary is a
  scope increase, but not a speculative one: the generic/adapter split is forced
  by Finding 1 (the join can only happen agent-side) rather than chosen, so the
  seam exists either way — _4 only decides whether it is named and documented ·
  severity: low · → mitigation: `aidocs/framework/live_endpoint_resolution.md`
- Residual: the read-receipt model assumes a note consumed on one PC should not
  resurface on another · severity: low · → mitigation: none needed; recorded as
  a decision in `aidocs/`.

### Planned mitigations
- timing: pre-phase | name: characterize_merge_union | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — promoting the load-bearing cross-PC ledger union to an ordered-multi-section seam | desc: Pin aitask_merge.py's current union behaviour, including every bail-to-conflict guard, before changing it
- timing: post-phase | name: pin_section_order | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — `## Inbox` after `## Gate Runs` would silently swallow every future gate block | desc: Append a note then a gate block; assert the gate block lands under `## Gate Runs` and the note stays above it

`characterize_merge_union` is an inline pre-phase of **child t1657_1**, which
owns the union machinery; `pin_section_order` is an inline post-phase of **child
t1657_2**, which owns the `## Inbox` writer. They are carried into those
children's plans when written; this decomposing parent creates no mitigation
tasks.
