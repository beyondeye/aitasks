---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [workflow, skills]
gates: [risk_evaluated]
anchor: 1536
followup_kind: upstream_defect
created_at: 2026-08-18 11:59
updated_at: 2026-08-18 12:50
---

## Origin

Spawned from t1558 during Step 8b review.

## Defect

`.aitask-scripts/aitask_skill_rerender.sh:60-65` prints one message for two
materially different states:

```bash
template="$(agent_authoring_template "$skill")"
if [[ ! -f "$template" ]]; then
    info "Skipping orphaned rendered dir (no template at $template): $dir"
    continue
fi
```

- **Genuinely orphaned** — a rendered dir left behind by a skill that was
  deleted. This is the state the code comment describes ("Skip rendered dirs
  whose authoring template has been removed") and the only one the wording fits.
- **Healthy closure member** — a skill whose authoring file is a Jinja-inline
  `SKILL.md` rather than a `SKILL.md.j2`. `agent_authoring_template()`
  (`.aitask-scripts/lib/agent_skills_paths.sh:79-82`) hardcodes the `.j2` path,
  so these always miss.

Both emit byte-identical output. A real orphan is therefore **invisible**, and a
live skill is reported as broken.

## Scope

Two skills are affected — `task-workflow` and `user-file-select`, the only two
`user-invocable: false` closure members with rendered dirs:

**2 skills × 3 profiles × 3 agent roots = 18 skip lines per full sweep**
(6 per profile, across `.claude/skills/`, `.agents/skills/`, `.opencode/skills/`).

No entry-point skill is affected: all 13 (`aitask-pick`, `aitask-explore`,
`aitask-qa`, …) ship a `SKILL.md.j2` and re-render normally.

## What is NOT the defect

**The skip is architecturally correct.** `task-workflow` is not an entry-point
templated skill: it has no `.md.j2`, no stub, and `user-invocable: false`, and
nothing dispatches to `task-workflow-<profile>-` directly. The framework's own
definition of "templated skill" is "has a `SKILL.md.j2`" —
`tests/test_skill_dispatch_contract.sh` discovers them that way, "never a
hardcoded list". Rendering it standalone would be meaningless. Do **not** "fix"
this by making the rerender loop treat closure members as entry points.

**Stale rendered variants are not a live risk.** Closure members are refreshed
by the dep-walker (`skill_template.py walk-write`) whenever an entry point that
references them is rendered. All 13 entry-point skills reference
`task-workflow`, so 13 independent paths keep it fresh; the guarantee is
incidental rather than structural, but it is over-determined in practice.
Verified empirically in t1558: the three tracked `task-workflow-remote-`
variants were updated by the sweep even though the direct pass skipped them.
Worth a sentence in the fix's rationale, not a mechanism.

## Suggested fix

Make the two states distinguishable. Either:

- teach `agent_authoring_template()` (or a new sibling predicate) to accept a
  Jinja-inline `<skill>/SKILL.md` as a valid authoring form, and have the loop
  emit a distinct, non-alarming line for closure members (e.g.
  `Skipping closure member (rendered via its entry points): <dir>`); or
- keep the probe as-is but branch the message on whether
  `.claude/skills/<skill>/SKILL.md` exists — present ⇒ closure member,
  absent ⇒ genuinely orphaned.

Either way, reserve the word "orphaned" for a rendered dir with **neither**
authoring form, so that line becomes actionable (it means: delete this dir).

## Verification

- Run `./.aitask-scripts/aitask_skill_rerender.sh default` and confirm
  `task-workflow` / `user-file-select` produce the closure-member line, not the
  orphan line — 6 lines per profile.
- Create a throwaway rendered dir for a non-existent skill
  (e.g. `.claude/skills/zz-nonexistent-default-/`), re-run, and confirm it —
  and only it — is reported as orphaned. This is the negative control: the
  current code cannot tell it apart from `task-workflow`.
- Confirm `RERENDERED:<N>` is unchanged (this is a message fix, not a
  behavior change: closure members must still not be rendered directly).
