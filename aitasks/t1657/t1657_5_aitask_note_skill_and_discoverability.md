---
priority: high
effort: medium
depends: [t1657_2, t1657_4]
issue_type: feature
status: Ready
labels: [framework, claudeskills, skills, agents_md, codeagent]
gates: [risk_evaluated]
anchor: 1657
created_at: 2026-09-01 12:36
updated_at: 2026-09-01 12:37
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
