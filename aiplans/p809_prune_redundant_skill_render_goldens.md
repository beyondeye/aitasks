---
Task: t809_prune_redundant_skill_render_goldens.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# t809 — Prune redundant skill-render goldens

## Context

The skill-render test suites commit a golden file for every
`(skill × profile × agent)` triple. A drift audit (t805) found a large
fraction store byte-identical content and catch nothing:

- **Agent dimension is dead weight for entry-point goldens.** None of the
  entry-point `.md.j2` templates reference `{{ agent }}` / `{% if agent %}`,
  and the basic render-to-stdout path used to populate goldens does *not*
  apply per-agent reference rewrites (that happens in `aitask_skill_render.sh`
  walk-write, covered separately by **Test 4** in each per-skill test). So
  every `codex`/`gemini`/`opencode` golden is a byte-for-byte copy of the
  `claude` golden.
- **Some procedure goldens are profile-invariant.** Their bodies have a
  profile conditional that no committed profile activates, so all 3 profile
  renders are identical.

**Audit re-confirmed on the current tree** (2026-05-20): all 5 entry-point
skills' per-agent goldens are byte-identical across all 3 profiles; procs
`task-workflow/remote-drift-check`, `aitask-qa/test-execution`, and
`aitask-qa/test-plan-proposal` are profile-invariant.

**Scope note:** the task file lists only 4 skills (pick/explore/review/fold)
because it was written before `aitask-qa` was converted to template+stubs
(commit `dd4b1b4a`). `aitask-qa` has the identical redundancy. Per user
decision, `aitask-qa` is included in full scope.

**Goal:** delete the redundant goldens, replace them with cheap invariance
assertions that fail loudly if a future template introduces an `{% if agent %}`
or profile-conditional divergence, and update the two aidocs that document the
regenerate convention.

## Outcome

`find tests/golden -type f | wc -l` drops **84 → 33** (51 files deleted):
- Entry-point: 60 → 15 (delete 45 per-agent dupes; keep `claude` only)
- Procs: 24 → 18 (collapse 3 profile-invariant procs from 3→1 golden each)

## Step 1 — Re-confirm the audit (pre-deletion gate)

```bash
# Entry-point per-agent byte identity (expect zero output)
for skill in aitask-pick aitask-explore aitask-review aitask-fold aitask-qa; do
  for profile in default fast remote; do
    base="tests/golden/skills/$skill/SKILL-${profile}-claude.md"
    for agent in codex gemini opencode; do
      diff -q "$base" "tests/golden/skills/$skill/SKILL-${profile}-${agent}.md" \
        >/dev/null || echo "DIFF: $skill/$profile/$agent"
    done
  done
done
# Profile invariance for the 3 procs (expect all "==" lines)
for f in task-workflow/remote-drift-check aitask-qa/test-execution aitask-qa/test-plan-proposal; do
  d="tests/golden/procs/${f%/*}"; n="${f#*/}"
  diff -q "$d/$n-default.md" "$d/$n-fast.md"   >/dev/null && echo "$f default==fast"
  diff -q "$d/$n-default.md" "$d/$n-remote.md" >/dev/null && echo "$f default==remote"
done
```
Any `DIFF:` line aborts the plan for that combo. (Already verified clean.)

## Step 2 — Delete the redundant goldens (51 files)

```bash
# 45 per-agent entry-point dupes
for skill in aitask-pick aitask-explore aitask-review aitask-fold aitask-qa; do
  for profile in default fast remote; do
    for agent in codex gemini opencode; do
      git rm tests/golden/skills/$skill/SKILL-${profile}-${agent}.md
    done
  done
done
# 6 profile-invariant proc dupes (keep the -default golden as canonical)
git rm tests/golden/procs/task-workflow/remote-drift-check-{fast,remote}.md
git rm tests/golden/procs/aitask-qa/test-execution-{fast,remote}.md
git rm tests/golden/procs/aitask-qa/test-plan-proposal-{fast,remote}.md
```

## Step 3 — Update the 6 test scripts

### 3a. Entry-point skills: `test_skill_render_aitask_{pick,explore,review,fold}.sh`

These 4 have an identical Test 1 (3×4 nested loop). For each:

**Test 1** — drop the `AGENTS` inner loop, render `claude` only:
```bash
# === Test 1: per-profile golden diffs (claude render is canonical) ===
echo "=== Test 1: golden diffs for entry-point × 3 profiles ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    golden_content="$(cat "$GOLDEN_DIR/SKILL-${profile}-claude.md")"
    assert_eq "golden SKILL × $profile" "$golden_content" "$rendered"
done
```

**New Test 1b** — agent-dimension invariance (replaces the 9 deleted goldens
per skill; fails loudly if a template ever introduces `{% if agent %}`):
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
Tests 2/3/3b/4/5 keep using `AGENTS` and are unchanged (Test 4 is the
walk-write per-agent path-rewrite check — the reason per-agent goldens are
redundant; **keep it**). `TOTAL`/`PASS`/`FAIL` counters auto-increment — no
hardcoded total to adjust.

**Header comment fix:** `# - 12 golden files ... (3 profiles × 4 agents)` →
`# - 3 golden files ... (3 profiles, claude render is canonical)`. The
Coverage note that currently claims "full-path refs ARE rewritten per-agent,
so all 12 combos need distinct goldens" is **factually wrong** — rewrite
the line: per-agent rewrites are a walk-write property covered by Test 4;
the basic stdout render is agent-invariant (asserted by Test 1b).

### 3b. `test_skill_render_aitask_qa.sh`

- **Entry-point (Test 1):** collapse to claude-only + add **Test 1b**, same
  as 3a (aitask-qa entry-point has the same 12→3 redundancy).
- **Procedures (Test 1p):** split `PROC_FILES` into:
  - `PROC_FILES_VARYING=(task-selection)` — keep the existing per-profile
    loop (3 goldens) + per-agent invariance assertions.
  - `PROC_FILES_INVARIANT=(test-execution test-plan-proposal)` — single
    canonical golden + invariance across **all 3 profiles AND 4 agents**:
    ```bash
    for f in "${PROC_FILES_INVARIANT[@]}"; do
        base="$($RENDER ".claude/skills/aitask-qa/$f.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
        assert_eq "golden proc $f (canonical)" "$(cat "$PROC_GOLDEN_DIR/$f-default.md")" "$base"
        for profile in "${PROFILES[@]}"; do
            for agent in "${AGENTS[@]}"; do
                cmp="$($RENDER ".claude/skills/aitask-qa/$f.md" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
                assert_eq "proc $f invariance $profile/$agent" "$base" "$cmp"
            done
        done
    done
    ```
  - Keep `PROC_FILES` (the union, all 3) for Test 2/3/3b — those checks
    don't touch goldens and must still iterate every proc file.
- **Header comment:** `12 entry-point goldens` → `3`; `9 procedure goldens`
  → `5` (task-selection × 3 + test-execution + test-plan-proposal canonical).

### 3c. `test_skill_render_task_workflow.sh`

- Split `WRAPPED_FILES` into:
  - `WRAPPED_FILES_VARYING=(SKILL.md planning.md manual-verification-followup.md satisfaction-feedback.md)`
  - `WRAPPED_FILES_INVARIANT=(remote-drift-check.md)`
- **Test 1** loops `WRAPPED_FILES_VARYING` (4 files × 3 profiles = 12 goldens).
- **New Test 1b** — collapse `remote-drift-check` to 1 canonical golden +
  explicit profile-invariance assertion:
  ```bash
  echo "=== Test 1b: profile-invariant procedure(s) — single golden + invariance ==="
  for file in "${WRAPPED_FILES_INVARIANT[@]}"; do
      stem="${file%.md}"
      base="$($RENDER "$WORKFLOW_DIR/$file" "$PROFILES_DIR/default.yaml" claude 2>&1)"
      assert_eq "golden $stem (canonical)" "$(cat "$GOLDEN_DIR/${stem}-default.md")" "$base"
      for profile in "${PROFILES[@]}"; do
          rendered="$($RENDER "$WORKFLOW_DIR/$file" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
          assert_eq "$stem profile-invariant ($profile==default)" "$base" "$rendered"
      done
  done
  ```
- Tests 2/3/3b/4 are unchanged (Test 2 = SKILL.md agent byte-identity;
  Test 4 = synthetic `remote_drift_check: skip` profile — still valid).
- **Header comment:** `15 golden files` → `13 golden files`.

**Canonical golden naming:** the kept file keeps its `-default` suffix
(`remote-drift-check-default.md`, `test-execution-default.md`,
`test-plan-proposal-default.md`) — matches the task's `rm …{fast,remote}.md`
prescription, avoids a rename, and the test's golden-path logic stays simple.
A one-line comment in each test explains the `-default` golden is the
canonical render for a profile-invariant file.

## Step 4 — Update aidocs

### `aidocs/skill_authoring_conventions.md` — "Regenerate goldens" subsection

- Change the regenerate command (lines ~235-250) from a `3 × 4` loop to
  `3 × claude`:
  ```bash
  for profile in default fast remote; do
    "$PYTHON" .aitask-scripts/lib/skill_template.py \
      "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude \
      > "$GOLDEN_DIR/SKILL-${profile}-claude.md"
  done
  ```
- Add a paragraph stating the conditional rule:
  > Per-agent goldens are kept only for skills whose template references
  > `{% if agent %}` (gates a per-agent block). When introducing such a gate,
  > regenerate goldens for all 4 agents in the same commit; the per-skill
  > Test 1b (agent-invariance check) will fail and remind you.
- Extend the procedure-golden paragraph: a profile-invariant procedure keeps
  a single canonical `-default` golden plus a byte-equality invariance
  assertion across the other profiles.

### `aidocs/stub-skill-pattern.md` — Pilot Finding #3

Extend finding #3 ("Golden-file tests are mandatory") with a paragraph
documenting the per-agent / per-profile golden-dimension rule (t809):
entry-point goldens are `claude`-only because the stdout render path applies
no per-agent rewrites (Test 4 walk-write covers those); profile-invariant
procedures collapse to one canonical golden. Both dimensions are guarded by a
cheap byte-equality invariance assertion (Test 1b) that fails loudly if a
template later introduces a real divergence — at which point the pruned
goldens are re-added surgically for that skill. (Keeps the "five patterns"
numbered list intact — this is an added paragraph, not a 6th finding.)

## Verification

1. **Pre-deletion:** Step 1 audit prints zero `DIFF:` lines and all `==`
   lines.
2. **All 6 render suites green:**
   ```bash
   for t in pick explore review fold qa; do bash tests/test_skill_render_aitask_$t.sh; done
   bash tests/test_skill_render_task_workflow.sh
   ```
   (`test_skill_render_uniform.sh` touches no goldens — unaffected, but run
   it too for safety.)
3. `./.aitask-scripts/aitask_skill_verify.sh` reports OK (it does not read
   goldens — confirmed — so deletions cannot break it).
4. `find tests/golden -type f | wc -l` = **33** (was 84).
5. `du -sh tests/golden/` drops from ~984K to ~390K.
6. `shellcheck tests/test_skill_render_*.sh` clean.

## Out of scope (noted, not done)

- The 5 per-skill test scripts duplicate ~60 lines of `assert_*` helpers and
  near-identical Test 1/1b/3/3b structure. Extracting a shared
  `tests/lib/skill_render_test_lib.sh` is a sensible follow-up but is a
  test-harness refactor distinct from golden pruning — left for a separate
  task.
- No `.md.j2` / closure files are edited, so no goldens need *regenerating*
  (only deleting). The kept `claude` and `-default` goldens are unchanged.

## Step 9 reference

Post-implementation: this runs on the current branch (profile `fast`, no
worktree). After review/commit, archive via
`./.aitask-scripts/aitask_archive.sh 809` and `./ait git push` per
task-workflow Step 9.
