---
Task: t1657_5_aitask_note_skill_and_discoverability.md
Parent Task: aitasks/t1657_task_note_mailbox_with_live_delivery.md
Sibling Tasks: aitasks/t1657/t1657_1_*.md, aitasks/t1657/t1657_2_*.md, aitasks/t1657/t1657_3_*.md, aitasks/t1657/t1657_4_*.md, aitasks/t1657/t1657_6_*.md
Base branch: main
Output branch: main
---

# p1657_5 — Discoverability: the `aitask-note` skill and always-loaded surfaces

## Goal

Make the capability **reachable**, and own the **single composition point** that
binds writer + resolver + adapter. A helper no agent knows to reach for is dead
weight.

## Main steps

### 1. `.claude/skills/aitask-note/SKILL.md` (new)

Static, `user-invocable: true`, modeled on `.claude/skills/ait-git/SKILL.md`.

The **description is the discoverability hook** and must convey the *when*, not
just the what — e.g. "Send a durable note to an existing aitask — context it
needs that is not itself work."

Two entry paths, an **explicit mode selector** rather than an inferred signal:

- **explicit target** — `/aitask-note 357 --from 1657 --text ...`; zero prompts,
  so it is usable headlessly and callable from another skill;
- **discovery** — reuse the existing **Related Task Discovery Procedure**
  (`.claude/skills/task-workflow/related-task-discovery.md`) to answer "which
  existing task should hear this?" rather than reinventing task matching.

Judgement the helper cannot carry:

- **note vs. spawn a task** — a note is for *context about work that already
  exists*; if the content is itself work, create a task. Notes do not replace
  follow-up creation.
- **trust posture** — advisory, attributed, never auto-actioned; `from=` is a claim.
- **staleness hygiene for senders** — `base`/`at`/`dirty` only help if the sender
  hedges *moment-relative* claims rather than stating them as fact. Both notes in
  the t349→t357→t353 chain that motivated this work were confidently wrong.

### 2. The composition contract — this skill owns it

Exactly ONE thing composes the pieces. Every caller — the trigger points below
and any future consumer — invokes **this skill**, never the pieces, so there is
no second caller-side join to drift.

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

**Step 2 completes before step 3 begins.** **Two results, one authority**: the
durable result is authoritative; `LIVE_NONE:<reason>` after `NOTE_APPENDED:` is a
**success**, reported as one. `LIVE_QUEUED` means enqueued, never read.

### 3. Always-loaded surfaces

Add `## Sending Notes to Other Tasks` to
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

`AGENTS.md` regenerates via `update_agentsmd`. `CLAUDE.md` is hand-maintained —
edit directly.

This layer is what keeps the **cross-agent** story true: the durable lane is
agent-agnostic by design, so a Codex agent must be able to *send* even before it
has the skill.

### 4. Trigger points — a few high-value sites, not everywhere

A **one-line offer** (never automatic) where a finding belongs to a task that
**already exists** — the repo's existing "hand findings to the owning task"
convention, which today has no mechanism to act on:

- `task-workflow` Step 8d (follow-up creation)
- `aitask-qa`
- `aitask-review`

Regenerate goldens for any template whose render closure changes.

### 5. Follow-ups to spawn

- Codex / OpenCode ports of the `aitask-note` skill (per CLAUDE.md, Claude Code
  version first; `ait-git` is the precedent for a Claude-only static skill).

## Verification

- **Discoverability check** — in a fresh session that has NOT read the plan,
  confirm `ait note` is reachable from the always-loaded instructions alone, and
  that `aitask-note` appears in the skill listing with a description conveying
  *when* to use it. This is the point of the child; a skill that exists but is
  never reached for has failed.
- **Composition + authority** — forced adapter failure after a successful write is
  reported as *success with live delivery unavailable*; the live payload names
  the same `<note-id>` present in the target's `## Inbox`.
- `bash tests/test_agent_instructions.sh` (T25–T27 compare all three tracked
  surfaces byte-for-byte against the live generator)
- `./.aitask-scripts/aitask_skill_verify.sh`
- `bash tests/run_all_python_tests.sh --test-dir tests`

## Step 9 (Post-Implementation)

Cleanup, archival and merge per `task-workflow` Step 9.

## Risk

### Code-health risk: **low**

- Seed edits silently drift the two mirrors on a machine without Codex/OpenCode
  installed (`_is_agent_installed` gates the regeneration) · severity: medium ·
  → mitigation: `tests/test_agent_instructions.sh` T25–T27 turn drift into a
  failing test rather than an accident
- Trigger points could grow into noise if wired everywhere · severity: low ·
  → mitigation: scope limited to three named sites, offer-only

### Goal-achievement risk: **medium**

- "Discoverable" is the one acceptance criterion that cannot be asserted by a
  unit test — it is a property of a fresh agent's context · severity: medium ·
  → mitigation: the fresh-session discoverability check, and the always-loaded
  layer as the guarantee that does not depend on the agent choosing to look
