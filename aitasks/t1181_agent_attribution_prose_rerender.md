---
priority: low
effort: low
depends: []
issue_type: documentation
status: Implementing
labels: [claudeskills, codexcli]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1171
created_at: 2026-07-20 12:20
updated_at: 2026-07-20 12:41
---

## Origin

Risk-mitigation ("after") follow-up for t1171, created at Step 8d after
implementation landed.

## Risk addressed

- addresses: diff-widening from the ~12-variant rerender
- `Fixing the now-wrong agent-attribution.md exemplar rerenders ~12 skill variants, widening the diff beyond the Codex launch path · severity: low`

This was deliberately carved out of t1171 during risk-mitigation design so that
change stayed scoped to the Codex launch path. It is a known-stale doc line, not
a newly discovered issue.

## Goal

`.claude/skills/task-workflow/agent-attribution.md:5` currently reads:

> **When to execute:** At the start of implementation, after plan mode has been
> exited. This timing is critical because some code agents (e.g., **Codex CLI**)
> run initial workflow steps in plan mode, which is read-only and cannot write
> metadata.

After t1171, the framework no longer launches Codex in plan mode, so the Codex
exemplar is wrong. **The general claim remains true** — Claude Code's planning
phase genuinely is read-only plan mode, and the deferred-write timing this
procedure describes is still required. So this is an exemplar fix, not a removal:
generalize the parenthetical (or swap in Claude Code) rather than deleting the
sentence or the timing rationale.

## Steps

1. Edit the canonical source only: `.claude/skills/task-workflow/agent-attribution.md:5`.
   Per CLAUDE.md, `.claude/skills/` is the source of truth; do not hand-edit the
   rendered copies under `.agents/` or `.opencode/`.
2. Rerender: `./.aitask-scripts/aitask_skill_rerender.sh` — the line appears in
   ~12 rendered variants across `.claude/`, `.agents/`, `.opencode/`.
3. Verify: `./.aitask-scripts/aitask_skill_verify.sh`.
4. Regenerate any affected goldens **in the same commit** (see "Regenerate
   goldens after any `.md.j2` or closure edit" in
   `aidocs/framework/skill_authoring_conventions.md`).
5. Run `bash tests/test_skill_parity_runtime_vs_rendered.sh`.

## Do NOT touch

`tests/fixtures/skills/task-workflow/agent-attribution.md.pre-rewrite` is a
deliberate **historical baseline** for the t777_27 parity test, not a live copy.
`tests/test_skill_parity_runtime_vs_rendered.sh:76` hard-asserts a fixture count
of exactly 25, and the fixture's whole purpose is to preserve the pre-rewrite
text for branch comparison. Editing it would corrupt the baseline.

## Note

This is a shared sub-procedure that auto-renders into every agent tree, so no
separate per-agent port task is needed — the rerender covers Codex and OpenCode.
