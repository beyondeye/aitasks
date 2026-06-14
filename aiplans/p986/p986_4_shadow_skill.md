---
Task: t986_4_shadow_skill.md
Parent Task: aitasks/t986_shadow_agent.md
Sibling Tasks: aitasks/t986/t986_1_*.md, aitasks/t986/t986_2_*.md, aitasks/t986/t986_3_*.md, aitasks/t986/t986_5_*.md, aitasks/t986/t986_6_*.md
Archived Sibling Plans: aiplans/archived/p986/p986_*_*.md
Worktree: (none — current branch, profile 'fast')
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-14 22:43
---

# Plan: t986_4 — `/aitask-shadow` user-invocable command (dispatcher + per-analysis sub-procedures + capture helper)

## Context

t986_4 is the **brain** of the `shadow` agent (parent t986): the skill, fed a
followed coding agent's captured tmux output, that serves the user's free-form
request in one instruction-driven flow.

This pick **corrects two premises of the original task** after investigating how
spawned agents are actually triggered and fed data:

### Correction 1 — the skill must be **user-invocable** (not `user-invocable: false`)

The framework triggers a freshly-spawned agent CLI by passing a **slash command
on argv** (verified in `aitask_codeagent.sh` + `agent_launch_utils.py`):
- Claude: `claude --model <id> "/aitask-pick <args>"`
- OpenCode: `opencode --model <id> --prompt "/aitask-pick <args>"`
- Codex: PTY `sendline("/plan <args>")` / direct argv

A `user-invocable: false` skill is **not discoverable as a slash command** — it can
only be `read-and-followed` by a parent skill *in the same session*. The shadow
runs in a **separate spawned session** with no parent skill, and the user has
ruled out `claude -p` headless. Therefore the skill must be a **user-invocable
command** so the t986_5 launcher can spawn it with `/aitask-shadow <args>` (the
`shadow` codeagent-op t986_5 already plans emits exactly that). **Name: `aitask-shadow`**
(user decision). **Style: invocable + static** — `user-invocable: true`, a single
`SKILL.md` plus sub-procedure `.md` files, **no** profile machinery / `.j2` / stub /
goldens (modeled on `.claude/skills/aitask-contribute/`, which is user-invocable
and static). Shadow has no profile-divergent behavior, so the aitask-pick
stub+template treatment is not warranted.

### Correction 2 — captured output flows via an **on-demand capture helper** (stdout), not argv or a snapshot

Captured pane content is ~200 lines / 100+ KB with ANSI (`PaneSnapshot.content`,
in-memory) — too large/unescapable to pass as an argv string, but trivial to read
as **command stdout**. Design (user decision): t986_5 passes only the **pane id**
(small, argv-safe); the skill calls a **new bash helper** that captures + cleans
that pane to stdout **on demand**, so the shadow always reads the followed agent's
*current* screen rather than a frozen launch-time snapshot. All tmux access goes
through the gateway (`lib/tmux_exec.sh`), per `tests/test_no_raw_tmux.sh`.

### Correction 3 — phase autodetection is dropped (already known)

t986_2 (phase autodetection) is **Postponed**; `phase_detect.py` does not exist
(verified). Parent t986 mandates the shadow **must NOT be phase-gated**. Phase is
a one-line deferred/advisory note only — never a flow step or prerequisite.

### Dependency status (verified)
- t986_3 `aitask_shadow_context.sh [--siblings] <task_id>` **landed** — emits
  `TASK_FILE:`/`PLAN_FILE:`/`SIBLING:` lines (all exit 0; parse lines). Deeper
  history via `aitask_explain_context.sh` on demand.
- t986_5 (launcher) is a later sibling and **consumes** this command's contract.

## Argument contract (t986_4 ↔ t986_5)

```
/aitask-shadow <followed_pane_id> [<source_task_id>]
```
- `<followed_pane_id>` (required): tmux pane id of the agent being shadowed. The
  skill captures it via the new helper.
- `<source_task_id>` (optional): the task the followed agent is working. When
  present, used for context fetch; when absent, infer from the captured output /
  window name, else ask the user once, else work from the captured screen alone.

## Files to create

```
.claude/skills/aitask-shadow/
  SKILL.md            # user-invocable: true — main dispatcher
  plan-explain.md     # non-expert plan explainer (technical-subject analysis)
  plan-challenge.md   # adversarial challenge
  plan-socratic.md    # Socratic questioning
  plan-assumptions.md # assumption surfacing
.aitask-scripts/aitask_shadow_capture.sh   # pane id -> cleaned stdout (gateway-only)
tests/test_shadow_capture.sh               # unit test for the capture helper
```

## Implementation steps

1. **`aitask_shadow_capture.sh` (capture helper).** `#!/usr/bin/env bash`,
   `set -euo pipefail`, source `lib/terminal_compat.sh` + `lib/tmux_exec.sh`.
   Usage: `aitask_shadow_capture.sh <pane_id>`. Capture via the gateway
   (`ait_tmux capture-pane -p -e -t <pane_id> -S -<N>`), strip ANSI escape
   sequences to clean text, trim trailing blank lines, print to stdout. Mirror
   the capture flags used in `monitor_core.py:_capture_args` (`-p -e -S -<N>`) and
   reuse the ANSI-strip approach. Validate the pane arg (die on empty). Keep it a
   thin, pure headless unit.
   - **Test** `tests/test_shadow_capture.sh`: self-contained (assert_eq style);
     exercise ANSI-strip / arg-validation on a fixture string (no live tmux
     dependency — factor the strip/format into a testable function or test via a
     fake capture). Follow `aidocs/framework/shell_conventions.md`.
   - **Whitelist the helper (7-touchpoint allowlist).** Because
     `aitask_shadow_capture.sh` is invoked from the `aitask-shadow` SKILL.md
     closure, it MUST be added to the helper-script allowlist across all active
     touchpoints (1,3,4,6,7): `.claude/settings.local.json`,
     `.codex/rules/default.rules`, `seed/claude_settings.local.json`,
     `seed/codex_rules.default.rules`, `seed/opencode_config.seed.json`
     (`aidocs/framework/aitasks_extension_points.md` "Adding a new helper
     script"). Apply via the canonical tool:
     ```bash
     ./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_shadow_capture.sh
     ```
     The skill dir `aitask-shadow` matches the `aitask-*` discovery glob, so the
     auditor picks it up automatically. (No whitelist entry is needed for
     `aitask_shadow_context.sh` — landed/whitelisted in t986_3 — or
     `aitask_explain_context.sh`, an established public helper.)

2. **`SKILL.md` — main dispatcher** (`user-invocable: true`):
   ```yaml
   ---
   name: aitask-shadow
   description: <one line — companion that explains/interrogates a followed agent's output; spawned by minimonitor>
   user-invocable: true
   ---
   ```
   Body documents:
   - **Inputs / arguments:** the `<followed_pane_id> [<source_task_id>]` contract.
   - **Read the followed agent's screen:** run
     `./.aitask-scripts/aitask_shadow_capture.sh <followed_pane_id>` to get the
     current cleaned output (re-run any time for fresh state).
   - **Resolve source context on demand** (esp. an `AskUserQuestion` shown
     without its task/plan): if a task id is known/inferable, fetch task +
     most-recent plan via `./.aitask-scripts/aitask_shadow_context.sh <task_id>`
     (`--siblings` only when clearly relevant). Deeper/archived history via
     `./.aitask-scripts/aitask_explain_context.sh --max-plans N <files…>` only on
     demand. Degrade gracefully when no task id resolves.
   - **Dispatch (instruction-driven, no mode enum):** route on the user's ask:
     - **Inline:** explain raw output / "what is the agent doing" / help reason
       about an `AskUserQuestion` and suggest an answer (user types it).
     - **Structured analyses (read-and-follow the sub-procedure file):** plan
       explanation → `plan-explain.md`; adversarial → `plan-challenge.md`;
       Socratic → `plan-socratic.md`; assumptions → `plan-assumptions.md`. Run
       several in sequence when the ask spans them (e.g. "review this plan").
   - **Advisory-only guardrail (load-bearing):** read-only w.r.t. the source
     agent; NEVER send keystrokes/answers into the source pane — present
     everything to the user. State explicitly.
   - **Phase (deferred):** one-line note — workflow-phase autodetection (t986_2,
     Postponed) is a future advisory-only enhancement, never a gate.

3. **`plan-explain.md` — non-expert plan explainer.** (a) read the plan (captured
   output and/or fetched plan file); (b) identify the **technical subjects/
   concepts the plan rests on**; (c) **offer the user a choice** to get, per
   subject, a short **introduction** ("what it is") + **motivation** ("why the
   plan leans on it") — present the detected-subjects list, let the user pick
   all/some/none; (d) plain-language walkthrough weaving in the chosen intros.

4. **`plan-challenge.md` — adversarial challenge.** Actively try to break the
   plan: regressions, failure modes, missed edge cases, "what if someone edits
   this unaware?". Output a prioritized list of concrete weaknesses.

5. **`plan-socratic.md` — Socratic questioning.** Pose open-ended, non-leading
   questions guiding the user to examine the plan's own reasoning/trade-offs.

6. **`plan-assumptions.md` — assumption surfacing.** Enumerate hidden/unstated
   assumptions and preconditions; flag which are load-bearing vs unverified.

   Each sub-procedure consumes the same inputs (captured screen + fetched
   plan/task context) and restates the advisory-only constraint.

## Coordination & follow-ups (executed during implementation / suggested)

- **t986_5 (launcher):** update its task/plan so it passes `<pane_id> [<task_id>]`
  to `/aitask-shadow` and does **not** pre-capture content (the skill captures on
  demand via `aitask_shadow_capture.sh`). Add a reverse coordination note (commit
  task edits via `./ait git`).
- **Parent t986:** correct the "non-user-invocable" design note to user-invocable
  `/aitask-shadow` (commit via `./ait git`).
- **Cross-agent ports (Claude now + follow-ups):** suggest/create two follow-up
  tasks to port the `aitask-shadow` command wrapper to Codex (`.agents/skills/`)
  and OpenCode (`.opencode/commands/` + `.opencode/skills/`). Not built here.
- **t986_6 (docs):** note that user-facing docs must describe `/aitask-shadow` as
  a command (its scope, not this task's).

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` passes (static `.md`, no `.j2`; must
  not introduce a closure/stub failure).
- `bash tests/test_shadow_capture.sh` passes; `shellcheck
  .aitask-scripts/aitask_shadow_capture.sh` clean;
  `bash tests/test_no_raw_tmux.sh` stays green (capture via gateway).
- **Whitelist coverage:**
  `./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_shadow_capture.sh`
  emits no `MISSING:` lines (all 5 active touchpoints present); `bash
  tests/test_skill_verify.sh` stays green.
- `head` SKILL.md → valid frontmatter (`name: aitask-shadow`,
  `user-invocable: true`); confirm all four sub-procedure files exist and are
  referenced by name.
- **Dry-run the dispatch narrative** against captured-transcript scenarios:
  buried/over-technical plan → `plan-explain.md`; `AskUserQuestion` without
  context → inline context fetch + suggested answer; "poke holes" →
  `plan-challenge.md`; "ask me questions" → `plan-socratic.md`; "what is this
  assuming?" → `plan-assumptions.md`.
- Confirm **no path** sends input to the source pane (advisory-only).

## Risk

### Code-health risk: low
- Adds a new static skill dir (5 `.md` files) + one thin, tested bash helper; the
  only edits to existing files are single-line allowlist inserts across the 5
  whitelist touchpoints (applied by the canonical `aitask_audit_wrappers.sh`
  tool). Capture goes through the tmux gateway (no raw-tmux violation) ·
  severity: low · → mitigation: TBD
- Reuses landed helpers (`aitask_shadow_context.sh`, `aitask_explain_context.sh`)
  and the established capture flags rather than forking logic · severity: low ·
  → mitigation: TBD

### Goal-achievement risk: medium
- The skill body is LLM-consumed prose, not executable code — "does the dispatcher
  route correctly and does each sub-procedure deliver?" is validated by the
  dry-run narrative + the live manual-verification sibling (t986_7), not an
  automated test · severity: medium · → mitigation: TBD
- The contract (`<pane_id> [<task_id>]`, on-demand capture) is consumed by the
  not-yet-built t986_5 launcher; a mismatch would only surface at integration.
  Mitigated by pinning the contract here and recording the t986_5 coordination
  update · severity: medium · → mitigation: TBD

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9 (child-task path:
archive to `aitasks/archived/t986/` + `aiplans/archived/p986/`; parent t986
archives only when all children complete).
