---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Done
labels: [testing, claudeskills, skill_optiomizations]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7
created_at: 2026-05-19 23:55
updated_at: 2026-05-20 12:09
completed_at: 2026-05-20 12:09
---

## Context

The skill-rendering test suites (`tests/test_skill_render_aitask_pick.sh`,
`aitask_explore`, `aitask_review`, `aitask_fold`, and
`test_skill_render_task_workflow.sh`) currently commit a golden file for
every `(skill × profile × agent)` triple — 48 entry-point goldens (4
skills × 3 profiles × 4 agents) plus 15 procedure goldens (5 procs × 3
profiles) = 63 files, 852KB total.

Drift audit during t805 surfaced that a large fraction of these goldens
store byte-identical content, catching nothing:

- **Agent dimension is dead weight for entry-point goldens.** Across all
  4 entry-point skills (pick / explore / review / fold) and all 3
  profiles, the per-agent goldens are byte-identical: `diff
  SKILL-<profile>-claude.md SKILL-<profile>-<other>.md` = 0 for every
  combination tested. Reason: none of the entry-point `.md.j2` templates
  currently reference `{{ agent }}` or `{% if agent %}` in their
  rendered body. The basic render-to-stdout path used to populate
  goldens does not apply per-agent reference rewrites — that happens
  inside `aitask_skill_render.sh` walk-write, which is tested
  separately by **Test 4** in each per-skill test script
  (`assert_contains` on `.claude/skills/` vs `.agents/skills/` vs
  `.gemini/skills/` vs `.opencode/skills/` markers in the on-disk
  output).

  Net: 36 of 48 entry-point goldens (75%) are exact duplicates of the
  `claude` golden and detect no regression that the `claude` golden
  doesn't already catch.

- **`remote-drift-check` proc goldens are profile-invariant.** All 3
  `remote-drift-check-{default,fast,remote}.md` files are byte-identical
  — the procedure body has no profile-conditional content.

- **Per-profile dimension is genuinely necessary elsewhere.** `aitask-pick`
  shows 30 diff lines between default and fast (email resolution, plan
  preference, post-plan action); `planning.md` shows 66 diff lines;
  `SKILL.md` (proc) shows 12-24. Dropping the profile dimension would
  lose real regression coverage.

## Related work

- **t803** (`gate_agent_specific_blocks_in_skills_via_jinja`) proposes
  introducing `{% if agent == "claude" %}` gating for `aitask-wrap`.
  Per-agent goldens become meaningful for any skill that adopts
  template-level agent gating. **The pruning rule must therefore be
  conditional, not blanket** (see Implementation Plan below). This
  task lands first; t803 (or its successors) re-introduce per-agent
  goldens surgically per-skill as the gating lands.

- **t805** (`document_golden_regen_on_template_edit`, completed
  2026-05-19) added the workflow rule "regenerate goldens after any
  `.md.j2` or closure edit" to `aidocs/skill_authoring_conventions.md`.
  The regenerate command in that subsection currently shows a 3×4 loop;
  it should be revised to the post-pruning convention (see Step 4
  below).

## Key Files to Modify

- `tests/golden/skills/aitask-pick/SKILL-*-{codex,gemini,opencode}.md`
  — delete (9 files; keep the 3 claude goldens).
- `tests/golden/skills/aitask-explore/SKILL-*-{codex,gemini,opencode}.md`
  — delete (9 files).
- `tests/golden/skills/aitask-review/SKILL-*-{codex,gemini,opencode}.md`
  — delete (9 files).
- `tests/golden/skills/aitask-fold/SKILL-*-{codex,gemini,opencode}.md`
  — delete (9 files).
- `tests/golden/procs/task-workflow/remote-drift-check-{fast,remote}.md`
  — delete (2 files; keep the `default` golden as the canonical).
- `tests/test_skill_render_aitask_pick.sh` — Test 1 loop: drop the
  `AGENTS` inner loop, render `claude` only for Test 1 golden diff;
  keep Test 4 (per-agent path rewrites) unchanged. Adjust the test
  count.
- `tests/test_skill_render_aitask_explore.sh` — same as above.
- `tests/test_skill_render_aitask_review.sh` — same as above.
- `tests/test_skill_render_aitask_fold.sh` — same as above.
- `tests/test_skill_render_task_workflow.sh` — collapse
  `remote-drift-check` to a single golden plus an explicit byte-equality
  assertion across all 3 profile renders (to enforce the invariant).
- `aidocs/skill_authoring_conventions.md` — update the "Regenerate
  goldens after any `.md.j2` or closure edit" subsection (added by
  t805) to reflect the new canonical convention (claude-only per skill
  unless agent-gating is present; document the rule).
- `aidocs/stub-skill-pattern.md` — add or extend Pilot Finding #3 (or
  add a new finding) documenting the per-agent golden conditional rule.

## Implementation Plan

### Step 1: Verify the byte-identity premise on a clean tree

Before touching anything, re-confirm the audit:

```bash
for skill in aitask-pick aitask-explore aitask-review aitask-fold; do
  for profile in default fast remote; do
    base="tests/golden/skills/$skill/SKILL-${profile}-claude.md"
    for agent in codex gemini opencode; do
      cmp="tests/golden/skills/$skill/SKILL-${profile}-${agent}.md"
      diff -q "$base" "$cmp" >/dev/null || echo "DIFF: $skill/$profile/$agent"
    done
  done
done
```

Any output line means an agent-divergent golden exists and the
pruning rule MUST exclude that combo. (Expected: zero output.)

For procs, verify `remote-drift-check` invariance the same way.

### Step 2: Delete the redundant goldens

```bash
for skill in aitask-pick aitask-explore aitask-review aitask-fold; do
  for profile in default fast remote; do
    for agent in codex gemini opencode; do
      rm tests/golden/skills/$skill/SKILL-${profile}-${agent}.md
    done
  done
done
rm tests/golden/procs/task-workflow/remote-drift-check-{fast,remote}.md
```

### Step 3: Update test scripts

For each per-skill test script (`test_skill_render_aitask_*.sh`),
modify **Test 1**:

```bash
# === Test 1: per-profile golden diffs (claude render is canonical) ===
echo "=== Test 1: golden diffs for entry-point × 3 profiles ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    golden_path="$GOLDEN_DIR/SKILL-${profile}-claude.md"
    golden_content="$(cat "$golden_path")"
    assert_eq "golden SKILL × $profile" "$golden_content" "$rendered"
done
```

Add a new **Test 1b** asserting byte-equality across the 4 agent
renders (this is the cheap check that the agent dimension is still
truly inert — if a template introduces `{% if agent %}` in the future,
this test fails LOUDLY and prompts re-adding per-agent goldens):

```bash
# === Test 1b: agent dimension invariance ===
echo "=== Test 1b: agent renders are byte-identical (no {% if agent %} in template) ==="
for profile in "${PROFILES[@]}"; do
    base="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    for agent in codex gemini opencode; do
        cmp="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        assert_eq "agent invariance $profile/$agent" "$base" "$cmp"
    done
done
```

This single assertion replaces the 36 deleted goldens while still
catching any future agent divergence.

For `test_skill_render_task_workflow.sh`, collapse `remote-drift-check`
similarly — one golden + an invariance check across the 3 profiles.

Adjust the totals (test counts, etc.) and re-run each suite.

### Step 4: Update aidocs

In `aidocs/skill_authoring_conventions.md`, revise the regenerate
command in the "Regenerate goldens after any `.md.j2` or closure edit"
subsection from a 3×4 loop to a 3×1 (claude-only) loop. Add a new
paragraph stating the conditional rule:

> Per-agent goldens are kept only for skills whose template references
> `{% if agent %}` (gates a per-agent block). When introducing such a
> gate, regenerate goldens for all 4 agents in the same commit; the
> per-skill Test 1b (agent-invariance check) will fail and remind you.

In `aidocs/stub-skill-pattern.md`, add a new Pilot Finding (or extend
the existing #3) documenting the same rule.

### Step 5: Verify and commit

- Run all 5 test suites — expected: all green, with reduced golden
  counts in Test 1 and a new Test 1b invariance check.
- Run `./.aitask-scripts/aitask_skill_verify.sh` — expected: OK.
- Confirm `find tests/golden -type f | wc -l` drops from 63 to ~24.

## Verification Steps

1. Pre-deletion: re-confirm byte identity audit (Step 1) shows zero
   divergence.
2. Post-deletion + test updates: all 5 test scripts pass.
3. `aitask_skill_verify.sh` reports OK.
4. Disk usage: `du -sh tests/golden/` drops from ~852KB to ~300KB.
5. Read aidocs subsection: a fresh contributor adding a `{% if agent %}`
   gate should know they need to add per-agent goldens for that skill.

## Reference Files for Patterns

- `tests/test_skill_render_aitask_review.sh:80-90` — current Test 1 loop
  (3×4 nested) — model for the new 3×1 loop.
- `tests/test_skill_render_aitask_review.sh:145-159` — Test 4
  (walk-write per-agent path rewrite check) — this is what makes
  per-agent goldens redundant for current templates; KEEP unchanged.
- `aidocs/skill_authoring_conventions.md` "Regenerate goldens after
  any `.md.j2` or closure edit" subsection (added by t805) — modify
  the regenerate command.
- `aidocs/stub-skill-pattern.md` Pilot Finding #3 — model for the new
  conditional rule.

## Notes

- Defer adding `aitask-wrap` golden coverage until t803 establishes
  the per-agent gating pattern; at that point the new rule applies and
  wrap's goldens are added with 4 agents from day one.
- The disk savings (~552KB) are minor; the real win is reduced
  surface area for stale-golden drift incidents like the t800/t805 cycle.
