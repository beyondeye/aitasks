---
priority: high
effort: medium
depends: [t1657_2, t1657_4]
issue_type: feature
status: Implementing
labels: [framework, claudeskills, skills, agents_md, codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1657
created_at: 2026-09-01 12:36
updated_at: 2026-09-06 17:28
---

# Discoverability: the `aitask-note` skill and the always-loaded surfaces

## Context

Parent plan: `aiplans/p1657_task_note_mailbox_with_live_delivery.md`.
**Depends on t1657_2 (writer) and t1657_4 (resolver + adapter)** — not t1657_3,
which is the independent read side.

A helper no agent knows to reach for is dead weight. The parent task specifies
the mechanism but says nothing about how an agent *learns* `ait note` exists.
This child closes that, and it is also **the single composition point** that
binds writer + resolver + adapter.

## Three discoverability layers, each a different guarantee

| layer | surface | reaches |
|---|---|---|
| **always-loaded** | `seed/aitasks_agent_instructions.seed.md` → `AGENTS.md`, `.codex/instructions.md`, `.opencode/instructions.md` (generated), plus hand-maintained `CLAUDE.md` | **every agent, every session, no invocation** |
| **listed skill** | `.claude/skills/aitask-note/` — its *description* is the hook | Claude, on demand, with depth |
| **trigger points** | the workflow moments where noting is the right move | the agent at the decision |

`ait-git` (`.claude/skills/ait-git/SKILL.md`) is the precedent for layer 2: a
small static skill that exists purely to teach a CLI convention. Note it lives in
`.claude/skills/` **only** — so per CLAUDE.md ("do the Claude Code version first;
suggest separate aitasks for the other agents") this skill is Claude-first with a
port follow-up. **Layer 1 is what keeps the cross-agent story true meanwhile**:
the durable lane is agent-agnostic by design, so a Codex agent must be able to
*send* even before it has the skill.

## The composition contract — this skill owns it

Exactly ONE thing composes the three pieces. Every caller — including the trigger
points below and any future consumer — invokes **this skill**, never the pieces,
so there is no second caller-side join to drift.

```text
1. resolve target task id     (explicit arg, else Related Task Discovery)
2. ait note <target> --from <id> --text …
       → NOTE_APPENDED:<note-id>|<path>   ← durable, committed, AUTHORITATIVE
3. aitask_live_endpoint.sh <target>
       → LIVE_PANE:…|agent=<family>  |  LIVE_NONE:<reason>
4. adapter(agent, pane, note-id, body)          [only on LIVE_PANE]
       → LIVE_QUEUED:<session>|<note-id>  |  LIVE_NONE:<reason>
5. report both outcomes
```

**Step 2 completes before step 3 begins** — the note is on disk and committed
before any live attempt exists.

**Two results, one authority.** The CLI reports only the durable write; live
outcomes come from the adapter. **The durable result is authoritative**:
`LIVE_NONE:<reason>` after `NOTE_APPENDED:` is a **success**, not a partial
failure, and must be reported as one. `LIVE_QUEUED` means *enqueued*, never
*read*.

## `.claude/skills/aitask-note/SKILL.md`

Static, `user-invocable: true`, modeled on `ait-git`.

The **description is the discoverability hook** and must convey the *when*, not
just the what — e.g. "Send a durable note to an existing aitask — context it
needs that is not itself work."

Two entry paths, an **explicit mode selector** rather than an inferred signal:

- **explicit target** (`/aitask-note 357 --from 1657 --text ...`) — zero prompts,
  so the skill is usable headlessly and callable from another skill;
- **discovery** — reuse the existing **Related Task Discovery Procedure**
  (`.claude/skills/task-workflow/related-task-discovery.md`) to answer "which
  existing task should hear this?" rather than reinventing task matching.

It also carries the judgement no helper can:

- **note vs. spawn a task** — a note is for *context about work that already
  exists*; if the content is itself work, create a task. Notes do not replace
  follow-up creation.
- **the trust posture** — notes are advisory, attributed, and never auto-actioned;
  `from=` is a claim.
- **staleness hygiene for senders** — a note carries `base`/`at`/`dirty`, but
  those only help if the sender hedges *moment-relative* claims (a `git status`
  reading) rather than stating them as fact. Both notes in the t349→t357→t353
  chain that motivated this task were confidently wrong rather than hedged.

## Always-loaded surfaces

Add a short `## Sending Notes to Other Tasks` section to
`seed/aitasks_agent_instructions.seed.md`, then regenerate the three mirrors.

**Drive the generator — never copy the block out of `AGENTS.md`**, which carries
the shared layer only and would destroy each mirror's per-agent
`## Agent Identification` tail:

```bash
source .aitask-scripts/aitask_setup.sh --source-only
for agent in codex opencode; do
  case "$agent" in
    codex)    target=.codex/instructions.md ;;
    opencode) target=.opencode/instructions.md ;;
  esac
  content="$(assemble_aitasks_instructions . "$agent")"
  insert_aitasks_instructions "$target" "$content"
done
```

`CLAUDE.md` is hand-maintained — edit it directly.

Guarded by `tests/test_agent_instructions.sh` T25–T27, which compare all three
tracked surfaces byte-for-byte against the live generator. Run it after any seed
edit; seed-vs-mirror drift is a failing test, not something found by accident.

## Trigger points — a few high-value sites, not everywhere

Wire a **one-line offer** (never automatic) where a finding belongs to a task
that **already exists** — the repo's existing "hand findings to the owning task,
not the current one" convention, which today has no mechanism to act on:

- `task-workflow` Step 8d (follow-up creation)
- `aitask-qa`
- `aitask-review`

## Follow-ups to spawn

- Codex / OpenCode ports of the `aitask-note` skill.

## Verification

- **Discoverability check** — in a fresh session that has NOT read the plan,
  confirm `ait note` is reachable from the always-loaded instructions alone, and
  that `aitask-note` appears in the skill listing with a description that conveys
  *when* to use it. This is the point of the whole child; a skill that exists but
  is never reached for has failed.
- **Composition + authority** — a forced adapter failure after a successful write
  is reported as *success with live delivery unavailable*; and the live payload
  names the same `<note-id>` present in the target's `## Inbox`.
- `bash tests/test_agent_instructions.sh` (T25–T27)
- `./.aitask-scripts/aitask_skill_verify.sh`
- `bash tests/run_all_python_tests.sh --test-dir tests`

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1657_4** id=2026-09-06T10:31:51Z.735d5174ae0697c82769afcc from=t1657_4 from_verified=yes at=2026-09-06T10:31:51Z base=caf24385d30a7786bbdc65f3019dc906cafbc6df base_branch=main dirty=yes host=omg16
>
> | Two acceptance criteria from t1657_4 were RELOCATED to this task, deliberately.
> | They are not gaps in t1657_4 — they are assertions only your composition test can
> | make, and t1657_4's plan records the same decision under "Deviation from the
> | task's stated AC".
> | 
> | Why they moved: `aitask_live_endpoint.sh` takes a task id and returns a result
> | code. It never appends a note and it never calls SendMessage. So it cannot
> | observe durable-first ordering; testing that needs `ait note` + resolver +
> | adapter in one place, which is the single composition point THIS task owns.
> | Building a second copy of that composition inside t1657_4 would have created a
> | drifting duplicate of your contract.
> | 
> | The two items, to fold into t1657_5's own verification:
> | 
> | 1. WRITE-BEFORE-LIVE. For EVERY `LIVE_NONE:<reason>` the resolver can return,
> |    `ait note` has already emitted `NOTE_APPENDED:<id>|<path>` and committed
> |    before the resolver is invoked at all. Step 2 completes before step 3 begins.
> |    The reason codes to cover: unlocked, remote_host, holder_dead, holder_unknown,
> |    agent_unknown, agent_unsupported:<agent>, no_pane (resolver) and
> |    no_session_match (adapter).
> | 
> | 2. POST-WRITE ADAPTER FAILURE. A forced adapter failure AFTER a successful
> |    durable write must be reported as *success with live delivery unavailable* —
> |    never as a partial failure, and never as a reason to retry the write. The
> |    durable result is authoritative.
> | 
> | What already exists for you to build on (all landed in t1657_4):
> | 
> | - `.aitask-scripts/aitask_live_endpoint.sh <task-id>` — one stdout line:
> |   `LIVE_PANE:<%pane>|<session>:<@win>.<%pane>|<pid>|agent=<family>` or
> |   `LIVE_NONE:<reason>` (both exit 0 — a degradation is a successful resolution),
> |   or `LIVE_ERROR:<reason>` exit 2 when the resolver itself could not run. The
> |   LIVE_ERROR set is disjoint from LIVE_NONE on purpose, so "no endpoint" and
> |   "resolver broke" are never confusable.
> | - `.aitask-scripts/live_delivery/agents.txt` — the adapter manifest. A family
> |   absent from it yields `agent_unsupported:<family>`; the resolver holds no agent
> |   literal of its own. `AIT_LIVE_DELIVERY_DIR` overrides it for tests.
> | - `.aitask-scripts/live_delivery/claudecode.md` — the Claude adapter procedure.
> |   It returns `LIVE_QUEUED:<session>|<note-id>` or `LIVE_NONE:<reason>`, joins on
> |   the PANE ID alone, and is required to say which pane it searched for when it
> |   reports `no_session_match`.
> | - Tests: tests/test_live_endpoint_degradation.sh (result codes + lock_record),
> |   tests/test_live_endpoint_tmux_live.sh (real pane correlation),
> |   tests/test_live_endpoint_no_sendkeys.sh (transport prohibition).
> | 
> | One correction worth carrying into your own work: the agent-session listing
> | renders a pane as `<session>:@<window_id>.%<pane_id>`, where the middle number is
> | tmux's `#{window_id}` and NOT `#{window_index}` — measured, they differ for the
> | same pane. Join on the pane id; the prefix is display context.

> **👁 note:read** id=2026-09-06T14:27:55Z.e0fec7f77379e073af96b67d by=t1657_5 at=2026-09-06T14:27:55Z mode=explicit ids=2026-09-06T10:31:51Z.735d5174ae0697c82769afcc
