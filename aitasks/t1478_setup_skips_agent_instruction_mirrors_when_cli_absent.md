---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [bash_scripts, task_metadata]
gates: [risk_evaluated]
anchor: 1468
followup_kind: upstream_defect
created_at: 2026-08-10 19:06
updated_at: 2026-08-10 19:06
---

## Origin

Spawned from t1468_1 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:2352-2358,2502-2509 — setup regenerates the
  tracked, marker-wrapped .codex/instructions.md and .opencode/instructions.md
  only when the corresponding agent CLI is installed locally; otherwise it prints
  "No … staging files found — skipping" and leaves them stale, so a seed change
  silently reaches AGENTS.md alone.`

## Diagnostic context

t1468_1 added a `followup_kind:` line to the "## Task File Format" YAML block in
`seed/aitasks_agent_instructions.seed.md`, then ran `ait setup` to regenerate the
mirrors, as `aidocs/framework/aitasks_extension_points.md` §5 (layer 5) instructs.

`AGENTS.md` was regenerated correctly (and auto-committed by setup as
`ait: Add aitask framework`). But `.codex/instructions.md` and
`.opencode/instructions.md` were left untouched, because `setup_code_agents()`
gates `setup_codex_cli` / `setup_opencode` on `_is_agent_installed` and neither
CLI is installed on this machine. Setup reported:

    No Codex CLI staging files found — skipping
      Re-run 'ait setup' to restore Codex CLI support files
    No OpenCode staging files found — skipping

Both files are **tracked in git** and **`>>>aitasks`-marker-wrapped**, so they
are generated artifacts that silently drifted from the seed. Nothing failed and
nothing warned about drift — the only symptom is that two committed files no
longer match their source. It was caught only because the field was grepped in
all three mirrors afterwards.

The failure is silent and repeats for **every** future frontmatter field or
instruction change made on a machine without both CLIs installed. t1468_1 worked
around it by copying the generated block out of `AGENTS.md` verbatim and
documenting the trap in `aitasks_extension_points.md`, but the skip itself is
unfixed.

## Suggested fix

Decouple *regenerating a tracked, marker-wrapped instructions file* from
*installing that agent's support files*. The instruction mirror is repo content,
not a local tool integration — it should regenerate whenever the marker block
exists on disk, regardless of whether the CLI is installed. Failing that, emit a
loud drift warning (or a non-zero check mode) when a tracked marker-wrapped
mirror is skipped, so the omission cannot pass unnoticed.
