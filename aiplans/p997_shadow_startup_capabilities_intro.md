---
Task: t997_shadow_startup_capabilities_intro.md
Base branch: main
plan_verified: []
---

# Plan — t997: Shadow startup capabilities intro

## Context

The `aitask-shadow` skill (`.claude/skills/aitask-shadow/SKILL.md`) is the
advisory companion spawned by minimonitor alongside a followed coding agent.
Today it jumps straight to Step 1 (capture the followed agent's pane) and then
silently waits for a free-form user ask — **nothing tells the user what the
shadow can do**, nor that they can ask it to re-read the followed agent's
screen as that agent keeps working.

This task adds a startup greeting that presents the shadow's own capabilities
(its inline capabilities + the four linked plan sub-procedures) plus a refetch
reminder, makes the proactive "surface a relevant capability when the followed
agent's current state calls for it" behavior explicit, and removes the now
ill-fitting trailing deferred-phase-autodetection note.

**Intended outcome:** a user who launches the shadow immediately sees what it
offers and how to keep its advice current, and the shadow proactively offers
the obviously-relevant capability based on what's on screen — all advisory-only.

## Scope / key finding

- **Only one source file changes:** `.claude/skills/aitask-shadow/SKILL.md`.
- The skill is a plain (non-`.j2`, non-stub) skill — no goldens to regenerate.

### Port scope — explicit decision (a): no port edits needed

The task's acceptance criteria as written require parity edits to the Codex and
OpenCode ports. That requirement was written on the assumption that the ports
duplicate the skill body. **They do not.** Verified:

- `.agents/skills/aitask-shadow/SKILL.md` (Codex) — "Source of Truth" wrapper:
  *"The authoritative skill definition is `.claude/skills/aitask-shadow/SKILL.md`.
  Read that file and follow its complete workflow."*
- `.opencode/skills/aitask-shadow/SKILL.md` and `.opencode/commands/aitask-shadow.md`
  (OpenCode) — same delegation: they `@`-include / point at the Claude source.

Both only carry their own copied `description:` frontmatter (which this task does
not change). The new Step 0, the proactive-surfacing paragraph, and the note
removal all live in the delegated body, so editing the Claude source propagates
to both ports at runtime. **Therefore no port-file edits and no port follow-up
tasks are needed** — consistent with the user's earlier "no port follow-up"
decision.

**Because this contradicts the AC as written, the deviation is made explicit and
the AC is corrected as a first implementation step (see Change 0 below) — it is
NOT silently dropped.**

## Change 0 — Correct task t997's acceptance criteria (done first, during implementation)

Before editing the skill, update t997's description so its AC matches the
verified delegation reality. Replace the AC bullet that requires Codex/OpenCode
parity edits with: *"Codex and OpenCode ports are thin wrappers delegating to the
Claude source — verified — so they require no edits; the change propagates
automatically. No separate port follow-up tasks."* Apply via
`aitask_update.sh --batch 997 --desc-file -` (heredoc) and commit the task file
via `./ait git`. This makes the scope decision explicit and on-record, not a
silent deviation.

## Changes to `.claude/skills/aitask-shadow/SKILL.md`

### 1. Add a startup greeting step (new `## Step 0`, inserted between `## Arguments` and `## Step 1`)

Plain-text greeting, emitted before any capture/fetch (no I/O before it). It
presents the shadow's *own* capabilities and the refetch awareness.

**Single source of truth:** Step 3 ("Serve the request") already enumerates every
capability and maps it to its handling (inline, or the specific
`plan-*.md` sub-procedure file). The greeting must be **derived from that list at
runtime — not a hardcoded second copy** — so adding/renaming a capability in
Step 3 updates the greeting automatically and the two can never drift. (This is
the user's correction: don't duplicate the list; extract it from where the skill
defines the sub-procedure for each capability.)

```markdown
## Step 0 — Greet the user and present your capabilities (do this first)

<!-- MAINTAINER: Do NOT hardcode the capability list here. It is derived at
     runtime from Step 3, which is the single source of truth (each capability +
     its inline handling or plan-*.md sub-procedure). Hardcoding a copy here
     reintroduces the drift this design exists to prevent. -->

The first thing you do on startup — before any capture or fetch — is print a
short greeting so the user knows what you offer. Keep it concise. Do not run any
command before this greeting.

**Build the capability list by reading your own Step 3 below — do not maintain a
separate copy here (see the maintainer note above).** Step 3 is the single
source of truth: it lists every capability and the inline handling or
`plan-*.md` sub-procedure that serves it. Present each one to the user in a
single short phrase (the inline capabilities and the linked plan sub-procedures
alike). Because the greeting is generated from Step 3, it stays in sync
automatically — never hardcode the list in this step.

Then make the user aware of two things:

- They can ask you to **refetch** the followed agent's screen at any time. The
  agent keeps working after you launch, so a later capture reflects its newest
  state — you will re-read it whenever they ask, or whenever fresh state is
  needed to answer well.
- They can just describe what they want in their own words; you will route to
  the right capability.
```

### 2. Make proactive, stage-relevant surfacing explicit

Append a short paragraph to the **end of `## Step 1`** (right after the
existing "pipe it through `aitask_shadow_capture.sh -`" sentence). This is the
new explicit instruction the user asked for; the existing wording is purely
*reactive* (Step 3 routes only on what the user asks; the "Help answer an
AskUserQuestion" bullet fires only when "the user asks for help deciding"), so
nothing today guarantees proactive surfacing — this adds it:

```markdown
**Proactively surface a relevant capability (after the first capture).** Glance
at the captured screen and, if its current state makes one of your capabilities
obviously useful, offer it without waiting to be asked — e.g. the screen shows
an `AskUserQuestion` → offer to help the user decide; a plan is on screen
awaiting approval → offer to explain it, challenge it, or surface its
assumptions. This is a lightweight look at what is *visibly* on screen, not a
workflow-phase classifier, and it never gates what the user can ask: it is one
advisory suggestion they can take or ignore. Stay suggestion-only — never run a
sub-procedure or send anything to the followed agent on your own.
```

### 3. Remove the deferred phase-autodetection note

Delete the entire trailing section (currently the last section of the file):

```markdown
## Note — workflow-phase autodetection (deferred)

Detecting which workflow phase the followed agent is in ...
... Serve any request without it.
```

Change #2's "lightweight look at what is visibly on screen, not a workflow-phase
classifier" wording preserves the non-gating, not-phase-routed intent, so the
deferred note is no longer the right framing to keep at the end of the skill.
The advisory-only Guardrail section remains the file's last load-bearing section.

## Risk

### Code-health risk: low
- Single markdown skill file; no executable code paths touched. Ports delegate
  to this file so there is no parity/duplication risk. Removing a deferred
  informational note is safe. · severity: low · → mitigation: none

### Goal-achievement risk: low
- Requirements fully pinned down by the user (capabilities = shadow's own;
  plain-text greeting; explicit proactive surfacing; remove the note). Straight
  documentation edit. · severity: low · → mitigation: none

## Verification

1. `grep -n '## Step 0' .claude/skills/aitask-shadow/SKILL.md` → greeting step present.
2. `grep -n 'refetch' .claude/skills/aitask-shadow/SKILL.md` → refetch reminder present.
3. `grep -n 'MAINTAINER' .claude/skills/aitask-shadow/SKILL.md` → derive-from-Step-3 guard note present in Step 0.
4. `grep -n 'Proactively surface' .claude/skills/aitask-shadow/SKILL.md` → proactive instruction present.
5. `grep -c 'workflow-phase autodetection' .claude/skills/aitask-shadow/SKILL.md` → `0` (note removed).
6. `grep -n 'advisory' .claude/skills/aitask-shadow/SKILL.md` → Guardrail (advisory-only) intact.
7. `./.aitask-scripts/aitask_skill_verify.sh` → passes.
8. Confirm t997's description AC no longer requires port parity edits (Change 0):
   `grep -i 'port' aitasks/t997_shadow_startup_capabilities_intro.md` reflects the
   delegation/no-edits wording.
9. Read the final skill file top-to-bottom to confirm flow reads cleanly:
   Step 0 (greet) → Step 1 (capture + proactive surfacing) → Step 2 → Step 3 → Guardrail.

## Step 9 (Post-Implementation)

Per the shared task-workflow: review/approve (Step 8), commit code (the skill
file) with `enhancement: ... (t997)`, commit/consolidate the plan via `./ait git`,
then archive via `aitask_archive.sh 997`. No worktree/branch (profile fast,
current branch).
