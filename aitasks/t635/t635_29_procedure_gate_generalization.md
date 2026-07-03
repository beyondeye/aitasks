---
priority: medium
effort: medium
depends: [t635_19]
issue_type: feature
status: Ready
labels: [gates]
anchor: 635
created_at: 2026-07-01 10:46
updated_at: 2026-07-03 00:00
---

## Context

t635_19 shipped `docs_updated` as the FIRST concrete procedure-backed gate
(`kind: procedure`) with a MINIMAL attended-dispatch seam. This task generalizes
procedure-backed gates — but scoped to the **ripe core** only. The original task
bundled five concerns; three were split out by coordination boundary (see
**Split note** below): per-gate agent/model + settings-TUI (→ t635_31, blocked on
t635_24 + t635_30), and remote/comment-signal integration (→ t635_32, blocked on
t635_16). External/plugin `kind` resolution is deferred as a documented extension
point (YAGNI — no external gate exists). This task keeps the two concerns that
have **no hard blocker** and make procedure gates first-class beyond the attended
Step-8 path.

## Scope (narrow core)

1. **Async / headless procedure-gate dispatch across autonomous lanes + resume.**
   Today procedure gates run **only** in the attended task-workflow Step 8; the
   autonomous lanes (`aitask-pickrem` / `aitask-pickweb`) skip Step 8 and run gates
   via the headless orchestrator, which **defers** procedure gates as `needs-agent`
   — so `docs_updated` never fires in an autonomous run and the task is left
   in-flight. Make the autonomous lanes (and `aitask-resume` re-entry) **auto-run**
   an unmet procedure gate **non-interactively**, via the gate skill's existing
   non-interactive branch (apply per the project spec, or record a deferral) — see
   the settled policy below. `aitask-gate-docs-updated` already documents this
   non-interactive branch.

2. **Agent-aware dispatch resolution.** Formalize the task-workflow Step-8/Step-9
   seam to resolve a procedure gate's verifier skill via
   `agent_skill_dir <running-agent> aitask-gate-<name>`
   (`.aitask-scripts/agent_skills_paths.sh`) in the **running agent's** tree, instead
   of the soft "in your agent's skill tree" prose. **Soft-coordinate t635_23** (which
   ports the wrapper FILES to Codex/OpenCode) — do NOT hard-depend on it.
   **Pre-t635_23 missing-skill behavior (fail-safe):** if the resolved SKILL.md is
   **absent** in the running agent's tree (the case for Codex/OpenCode until t635_23
   lands), **degrade gracefully** — report the gate unmet with a distinct reason
   ("procedure gate `<name>`: verifier skill not available in the `<agent>` tree —
   run under Claude or land t635_23") and **never silently pass/skip** it (archival
   stays blocked, consistent with the existing `needs-agent` reporting). Claude ships
   the skills today, so Claude behavior is unchanged; other trees light up once
   t635_23 lands. **No cross-agent fallback** (spawning a Claude sub-agent from a
   Codex session is per-gate agent selection — t635_31's territory). Test both the
   present-skill path and the missing-skill path (negative control).

3. **Out of scope — documented extension point only:** external / plugin `kind`
   resolution (project-local gate skills, plugin-provided gates). Document how
   `kind: external` / `kind: plugin` would resolve; **build nothing** (no such gate
   exists yet). Spin off a task when a concrete external/plugin gate is needed.

## Settled design decisions (from t635_29 planning, 2026-07-03)

- **Autonomous-lane policy:** auto-run the unmet procedure gate non-interactively
  (apply per spec, or record a deferral) — NOT "leave in-flight".
- **External/plugin gates:** deferred as a documented extension point (YAGNI).
- **t635_23:** soft coordination, not a hard dependency (keeps this core pickable).

## Split note (explicit AC re-scope — not a silent drop)

The original five-concern scope was split by coordination boundary so the ripe core
is not locked behind unrelated blockers:

- **This task (core):** async/headless dispatch + agent-aware resolution. No hard
  blocker beyond t635_19.
- **t635_31** (per-gate code-agent/model selection + settings-TUI) — `depends:
  [t635_24, t635_30]`.
- **t635_32** (remote/comment-signal integration for procedure gates) — `depends:
  [t635_16]`.

## Coordination

Depends on t635_19 (first concrete procedure gate). Soft-coordinate agent-aware
dispatch with t635_23 (wrapper FILES). Downstream siblings t635_31 / t635_32 build
on this core.

## Pre-explored design map (2026-07-03)

Planning explored the engine; the abstraction is already largely in place — the
core is mostly wiring the autonomous lanes + formalizing resolution:

- `read_registry` parses `kind` generically — `.aitask-scripts/lib/gate_ledger.py:573`
  (default `""`); `SATISFIED_STATUSES = {pass, skip}` at `:54`;
  `unmet_procedure_gates` at `:695`.
- `gate_orchestrator.py:474` excludes `kind: procedure` from headless machine
  dispatch; `blocked_reason` returns the "needs agent (procedure-backed gate…)"
  string at `:251-253`; `resolve_verifier` at `:275-287` maps `aitask-gate-<name>`
  → `.aitask-scripts/aitask_gate_<name>.sh` (procedure gates are Read-and-followed as
  a skill, not shell-executed).
- `aitask_gate.sh`: `begin-procedure` (`:488`, allocates run-id/attempt + opens the
  running block), `procedure-gates` (`:409`), `append --only-if-running`.
- Attended dispatch seam: `.claude/skills/task-workflow/SKILL.md` Step 8 procedure
  block (Jinja-gated on `profile.record_gates`) resolves the skill "in your agent's
  skill tree" (soft prose — the seam to formalize) + Step-9 archival gate-guard.
- Autonomous gap: `aitask-pickrem` / `aitask-pickweb` skip Step 8 entirely; their
  headless gate run defers procedure gates. `aitask-resume` hands off to
  task-workflow Step 3 → Re-entry Routing (Step 8 runs only if it re-enters there).
- Agent-tree resolver already exists: `agent_skill_dir <agent> <skill> [profile]`
  in `.aitask-scripts/agent_skills_paths.sh`; gate skills currently ship ONLY in
  `.claude/skills/` (t635_23 ports them).
- Editing task-workflow's `.md.j2` → re-render `{default,fast,remote}` variants +
  regenerate `tests/golden/procs/task-workflow/` + committed remote prerenders;
  `aitask_skill_verify.sh` must pass.
