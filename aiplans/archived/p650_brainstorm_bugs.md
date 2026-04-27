---
Task: t650_brainstorm_bugs.md
Base branch: main
plan_verified: []
---

# Plan: brainstorm bugs (t650) — parent (split into children)

## Context

Two bugs surfaced while running `agent-initializer_bootstrap` for brainstorm 635:

1. **`ait crew` whitelist gap.** Code agents are prompted on every `ait crew <subcommand>` invocation because the dispatcher entry is missing/malformed across the canonical 5-touchpoint whitelist set documented in `CLAUDE.md` (the "Adding a New Helper Script" section, generalized here to a top-level `ait` verb).

2. **Brainstorm initializer reported DEAD ~5 min in, even though the agent was still working.** The heartbeat in the initializer's `_alive.yaml` was last written at agent startup and never refreshed, so `agentcrew_runner.py` hit the default 5-minute `heartbeat_timeout_minutes` and marked it as Error / DEAD. Confirmed timing: `last_heartbeat: 2026-04-26 09:52:07` → marked dead at 09:57:16 (exactly 300 s).

   **Root cause:** the brainstorm agent templates (`initializer.md` and the 5 sibling `explorer/comparator/detailer/patcher/synthesizer.md`) use pseudo-verb shorthand at each Checkpoint (`report_alive`, `update_progress`, `check_commands`, `update_status`). These are not real skill names and not shell commands — the translation table to real `ait crew status …` calls lives in a *separate* file (`<agent>_instructions.md`), and the agent has to read it, mentally substitute, and run the resulting command. In practice this lookup is unreliable, so heartbeats never fire.

   The same bug latently affects all 6 templates; the user just hit it on `initializer_bootstrap` first.

The user requested splitting the parent's work into child tasks so the heartbeat fix can be attempted in two stages — a less invasive procedure-reference rewrite first, with an explicit-script-call rewrite held in reserve as a follow-up if the first attempt doesn't fix the issue.

---

## Parent role

This parent task does NOT implement any code itself. Per Step 6.1 of `task-workflow/planning.md`, parent status is reverted to `Ready` and the parent lock released after children are created and committed. All implementation work happens in the children below.

## Child tasks (3)

Children auto-depend on siblings (per `CLAUDE.md`), so the order below is the implementation order: t650_1 → t650_2 → t650_3. t650_3 is the conditional fallback for t650_2 — if t650_2 fixes the heartbeat issue end-to-end, t650_3 should be marked Postponed / closed without implementation.

### Child 1 — `t650_1_ait_crew_whitelist.md` (issue_type: bug)

**Scope:** Independent of the heartbeat work. Fix the missing/malformed `ait crew` dispatcher whitelist across the 5 canonical touchpoints (Codex exempt per CLAUDE.md).

**Touchpoints and exact actions:**

| File | Current state | Action |
|---|---|---|
| `.claude/settings.local.json:122` | `"Bash(ait crew *)"` (malformed: missing `./` prefix, wrong colon style) | Replace with `"Bash(./ait crew:*)"` |
| `seed/claude_settings.local.json` | missing | Add `"Bash(./ait crew:*)"` (place near the existing `"Bash(./ait git:*)"` entry) |
| `.gemini/policies/aitasks-whitelist.toml` | missing | Add `[[rule]]` block (place near existing `./ait git` / `./ait codeagent` blocks) |
| `seed/geminicli_policies/aitasks-whitelist.toml` | missing | Mirror the runtime gemini block |
| `seed/opencode_config.seed.json` | missing | Add `"./ait crew *": "allow"` (place near the existing `"./ait git *"` entry) |

**Canonical entry shapes** (verified against neighboring `./ait git` / `./ait codeagent` entries):

- Claude (runtime + seed): `"Bash(./ait crew:*)"`
- Gemini (runtime + seed):
  ```toml
  [[rule]]
  toolName = "run_shell_command"
  commandPrefix = "./ait crew"
  decision = "allow"
  priority = 100
  ```
- OpenCode (seed only): `"./ait crew *": "allow"`

**Verification:** grep all 5 files for `"ait crew"` and confirm exactly the canonical entry per agent and no remaining malformed entry.

**Reference for context:** `CLAUDE.md` "Adding a New Helper Script" section (the dispatcher-verb variant of the same checklist).

---

### Child 2 — `t650_2_brainstorm_heartbeat_procedure_reference.md` (issue_type: bug)

**Scope:** First-attempt heartbeat fix. **Less invasive** — replace pseudo-verbs with explicit references to the procedures already documented in each agent's `_instructions.md`. No new include file, no shell-command duplication, no template substitution engine.

**Files to modify (6 templates):**
- `.aitask-scripts/brainstorm/templates/initializer.md` (4 Checkpoints + Completion)
- `.aitask-scripts/brainstorm/templates/explorer.md` (3 Checkpoints + Completion)
- `.aitask-scripts/brainstorm/templates/comparator.md` (3 Checkpoints + Completion)
- `.aitask-scripts/brainstorm/templates/detailer.md` (3 Checkpoints + Completion)
- `.aitask-scripts/brainstorm/templates/patcher.md` (verify count when editing)
- `.aitask-scripts/brainstorm/templates/synthesizer.md` (verify count when editing)

**Pseudo-verb → procedure-reference map.** The procedures are already documented in `_instructions.md` (written by `aitask_crew_addwork.sh` lines 207–252). Each pseudo-verb maps to one section of that file:

| Pseudo-verb (current) | Procedure section in `_instructions.md` |
|---|---|
| `report_alive: "<msg>"` | "Heartbeat / Alive Signal" |
| `update_progress: <N>` | "Progress Reporting" |
| `check_commands` | "Reading Commands" |
| `update_status: <status>` | "Status Updates" |

**Rewrite pattern.** For every Checkpoint block currently shaped like:
```
### Checkpoint 1
- report_alive: "Phase 1 complete — imported proposal loaded"
- update_progress: 20
- check_commands
```
replace with:
```
### Checkpoint 1
- Execute the **Heartbeat / Alive Signal** procedure from your `_instructions.md` with message: "Phase 1 complete — imported proposal loaded"
- Execute the **Progress Reporting** procedure from your `_instructions.md` with progress: 20
- Execute the **Reading Commands** procedure from your `_instructions.md`
```

For every Completion block currently shaped like:
```
## Completion
- update_status: Completed
- update_progress: 100
- report_alive: "Initialization complete"
```
replace with:
```
## Completion
- Execute the **Status Updates** procedure from your `_instructions.md` with status: Completed
- Execute the **Progress Reporting** procedure from your `_instructions.md` with progress: 100
- Execute the **Heartbeat / Alive Signal** procedure from your `_instructions.md` with message: "Initialization complete"
```

**Why this should work.** The agent already reads `_instructions.md` at startup (it's the lifecycle reference). Replacing the bare pseudo-verb with an explicit "Execute the X procedure from your `_instructions.md`" turns a brittle implicit lookup ("does the agent know what `report_alive` means?") into an explicit instruction with a named target. This is the same pattern `task-workflow/SKILL.md` uses to point downstream procedures at named files (e.g., "Execute the Manual Verification Procedure (see `manual-verification.md`)").

**Verification:**
1. Inspect a written work2do.md after `ait crew addwork`: each Checkpoint should contain "Execute the … procedure from your `_instructions.md`" lines, no `report_alive:` / `update_progress:` / `check_commands` / `update_status:` lines remain.
2. Manual end-to-end: re-run a brainstorm bootstrap on a small imported proposal. Watch `<crew_worktree>/initializer_bootstrap_alive.yaml` → `last_heartbeat` should advance at every Checkpoint (4 advances during work + 1 at completion). The agent should NOT be flagged as Error / "Heartbeat timeout — agent presumed dead" by `agentcrew_runner.py`.
3. If verification step 2 fails (heartbeats still not emitted reliably), do NOT iterate inside this child — close it as inconclusive and pick up t650_3 to apply the more aggressive fix.

**Out of scope (intentionally):**
- No changes to `aitask_crew_addwork.sh` (no template substitution engine).
- No new include files.
- No changes to `_instructions.md` content (the procedures are already documented there).

**Sibling reference:** Sibling t650_3 will apply a more aggressive fix (explicit shell commands with context variables) only if this attempt's verification fails.

---

### Child 3 — `t650_3_brainstorm_heartbeat_explicit_commands.md` (issue_type: bug, status: Postponed initially)

**Scope:** **Fallback only — pick this child only if t650_2's verification step 2 fails** (i.e., agents still don't emit heartbeats after the procedure-reference rewrite). Replace the procedure references in the 6 templates with literal `ait crew status …` shell command lines, using the `${CREW_ID}` / `${AGENT_NAME}` context-variable pattern. This is more verbose but eliminates the implicit `_instructions.md` lookup entirely.

**Approach (mirroring the context-variable pattern used by `task-workflow`):**

1. Create a new shared include `.aitask-scripts/brainstorm/templates/_context_variables.md`:
   ```markdown
   ### Context Variables

   Throughout this template the following placeholders refer to your concrete
   crew identifier and agent name:

   - `${CREW_ID}` — your crew identifier (e.g. `brainstorm-635`)
   - `${AGENT_NAME}` — your agent name (e.g. `initializer_bootstrap`)

   The literal values are written into your `_instructions.md` file. Read it
   first, then substitute the values every time you run a command in the
   "Checkpoint" / "Completion" blocks below.
   ```
2. Add `<!-- include: _context_variables.md -->` near the top of each of the 6 templates (just below the level-1 heading and above `## Input`). The existing `resolve_template_includes` machinery in `aitask_crew_addwork.sh` will inline it at write time — no addwork change needed.
3. Replace the procedure-reference lines from t650_2 with explicit shell commands:
   ```
   ### Checkpoint 1
   - Run: `ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} heartbeat --message "Phase 1 complete — imported proposal loaded"`
   - Run: `ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} set --progress 20`
   - Run: `ait crew command list --crew ${CREW_ID} --agent ${AGENT_NAME}`
   ```
   And similarly for `## Completion`.

**Files to modify:**
- `.aitask-scripts/brainstorm/templates/_context_variables.md` (NEW)
- All 6 templates (add include + rewrite Checkpoint/Completion blocks)

**Verification:**
1. Include-resolution: written work2do.md contains the inlined Context Variables block (not the literal include directive) and explicit `ait crew status …` commands with `${CREW_ID}`/`${AGENT_NAME}` literals.
2. Manual end-to-end: same as t650_2 step 2 — re-run brainstorm bootstrap, watch `_alive.yaml`, confirm heartbeats fire at every Checkpoint and the agent is not marked DEAD.

**Sibling reference:** Picked only if t650_2 fails. If t650_2 succeeds, mark this child Done with a "not needed" plan note and archive without code changes.

---

## Out of scope for the parent (and all 3 children)

- **Codex whitelist files** — exempt per CLAUDE.md (prompt/forbidden permission model).
- **`heartbeat_timeout_minutes` default** — staying at 5 min. Lifting the default is a separate possible follow-up if even t650_3 doesn't fix the long-running-phase case.
- **`brainstorm_app.py` / `agentcrew_runner.py` DEAD detection logic** — the runner-side staleness check is correct; we're fixing the producer.

---

## Files modified — full per-child breakdown

| Child | Files |
|---|---|
| t650_1 | `.claude/settings.local.json`, `seed/claude_settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`, `seed/geminicli_policies/aitasks-whitelist.toml`, `seed/opencode_config.seed.json` |
| t650_2 | `.aitask-scripts/brainstorm/templates/{initializer,explorer,comparator,detailer,patcher,synthesizer}.md` |
| t650_3 | `.aitask-scripts/brainstorm/templates/_context_variables.md` (NEW), `.aitask-scripts/brainstorm/templates/{initializer,explorer,comparator,detailer,patcher,synthesizer}.md` |

t650_2 and t650_3 touch the same 6 template files but with distinct strategies; t650_3 builds on t650_2's structure if it ships, or replaces it if t650_2's verification fails.

---

## Step 9 (Post-Implementation, per child)

Each child runs its own Step 9 (per task-workflow `SKILL.md`): commit, push, archive. The parent t650 archives automatically when its last pending child is archived (per `aitask_archive.sh` parent-completion logic).
