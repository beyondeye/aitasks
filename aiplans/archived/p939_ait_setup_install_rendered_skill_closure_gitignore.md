---
Task: t939_ait_setup_install_rendered_skill_closure_gitignore.md
Worktree: (current branch — profile fast)
Branch: main
Base branch: main
---

# Plan: Install rendered-skill-closure ignore block via `ait setup`

## Context

`ait setup` (`aitask_setup.sh`, `setup_data_branch()` Step 7, "Update .gitignore
on main") writes the data-branch ignore block (`.aitask-data/`, `aitasks`,
`aiplans`) into a consumer project's `.gitignore`, but it does **not** install
the per-profile rendered-skill-closure ignore patterns. As a result, every
consumer project that runs a profile-aware skill (pick/explore/qa/…) accumulates
untracked `.claude/skills/<skill>-<profile>-/` directories (rendered on demand by
`aitask_skill_render.sh`) as `git status` noise.

This repo already carries the working scheme in its own `.gitignore` (lines
28–57), but consumers never receive it because setup doesn't write it. The fix
extends Step 7 to install the same block. As a coupled cleanup, the repo's own
`.gitignore` still carries stale `.gemini/skills/...` lines from when `.gemini`
was a supported agent root; those are dropped here so the canonical block and the
setup-written block stay identical.

## Approach

**Interim option 1 from the task** (unblocks now; one hardcoded block in
`aitask_setup.sh`, kept in sync with this repo's `.gitignore`). The full unifier
— `aitask_regen_gitignore_prerender.sh` auto-generating the negation list — is
t777_29's job and stays out of scope. The block must be embedded in
`aitask_setup.sh` (not a `seed/` file): `install.sh` deletes `seed/` after
install, so a seed file would be unreadable when a consumer runs `ait setup`.

### Change 1 — `aitask_setup.sh` Step 7 (after the `.aitask-data/` block, ~line 1390)

Add a second idempotent block inside `setup_data_branch()`, immediately after the
existing `.aitask-data/`/`aitasks`/`aiplans` append and before `# --- Step 8 ---`.
Sentinel = literal `.claude/skills/*-/` (grep `-qF`); append only if absent; set
`gitignore_changed=true` so the existing Step 9 commit picks it up. Negations
follow the broad `*-/` patterns (order matters). **No `.gemini` lines.**

```bash
    # Install per-profile rendered-skill-closure ignore patterns so a consumer's
    # `git status` stays clean of on-demand rendered closures
    # (.claude/skills/<skill>-<profile>-/ etc.). Mirrors the canonical block in
    # this repo's own .gitignore, minus .gemini (no longer a required agent
    # root). The `!` negations re-include the committed headless prerenders so
    # they stay tracked for Claude Code Web where `ait setup` has not run; they
    # MUST come after the broad `*-/` patterns. Keep this list in sync with the
    # repo .gitignore until t777_29 unifies both via
    # aitask_regen_gitignore_prerender.sh.
    if [[ ! -f "$gitignore" ]] || ! grep -qF ".claude/skills/*-/" "$gitignore" 2>/dev/null; then
        {
            echo ""
            echo "# Per-profile rendered skill variants (on-demand, not committed)"
            echo "# Convention: rendered dirs end with a trailing hyphen; authoring"
            echo "# dirs never do. See .claude/skills/task-workflow/stub-skill-pattern.md."
            echo ".claude/skills/*-/"
            echo ".agents/skills/*-/"
            echo ".opencode/skills/*-/"
            echo ""
            echo "# Pre-rendered headless variants, committed so the skill works where"
            echo "# 'ait setup' has not run (e.g. Claude Code Web). Negations win only"
            echo "# when they follow the broad patterns above."
            echo "!.claude/skills/aitask-pickrem-remote-/"
            echo "!.agents/skills/aitask-pickrem-remote-codex-/"
            echo "!.opencode/skills/aitask-pickrem-remote-/"
            echo "!.claude/skills/aitask-pickweb-remote-/"
            echo "!.agents/skills/aitask-pickweb-remote-codex-/"
            echo "!.opencode/skills/aitask-pickweb-remote-/"
            echo "!.claude/skills/task-workflow-remote-/"
            echo "!.agents/skills/task-workflow-remote-codex-/"
            echo "!.opencode/skills/task-workflow-remote-/"
        } >> "$gitignore"
        gitignore_changed=true
    fi
```

This is consistent with the existing Step 7 append idiom (same
`grep -qF`/heredoc-block/`gitignore_changed=true` shape) and is symlink/clone-safe
(it only adds glob patterns, touches no files).

### Change 2 — this repo's `.gitignore`: drop stale `.gemini` lines

Remove the 4 `.gemini` lines so the canonical block matches what setup writes:
- line 34 `.gemini/skills/*-/`
- line 48 `!.gemini/skills/aitask-pickrem-remote-/`
- line 52 `!.gemini/skills/aitask-pickweb-remote-/`
- line 56 `!.gemini/skills/task-workflow-remote-/`

(The `TODO(t777_29)` comment block stays — it still describes the future
unifier.)

### Change 3 — test coverage (`tests/test_data_branch_setup.sh`)

This test already sources `aitask_setup.sh --source-only` and calls
`setup_data_branch` directly, asserting on the generated `.gitignore` (Test 1,
~line 136). Extend it:
- **Test 1:** add `assert_file_contains` for `.claude/skills/*-/`,
  `.agents/skills/*-/`, `.opencode/skills/*-/`, and a representative negation
  (`!.claude/skills/task-workflow-remote-/`). Add a negative assertion that
  `.gemini/skills` does **not** appear (guards the no-`.gemini` requirement).
- **Test 3** (idempotency, runs `setup_data_branch` twice, ~line 259): assert the
  `.claude/skills/*-/` line appears exactly once (`grep -c` == 1).

## Verification

- `bash tests/test_data_branch_setup.sh` — new assertions pass; existing pass.
- `shellcheck .aitask-scripts/aitask_setup.sh` — clean.
- Manual (matches task Verification): in a fresh consumer repo, run `ait setup`;
  confirm `.gitignore` gains the `*-/` block + negations, no `.gemini` lines.
  Run a profile-aware skill, confirm the rendered closure dir is ignored
  (`git check-ignore .claude/skills/aitask-pick-fast-/` hits) and `git status`
  is clean. Confirm a committed `*-remote-` prerender stays tracked. Re-run
  `ait setup`; confirm no duplication.

## Step 9 (Post-Implementation)

Standard archival per task-workflow Step 9 (current-branch, no worktree to
remove). Commit code (`aitask_setup.sh`, `.gitignore`, test) with
`enhancement: ... (t939)`, then archive.

## Risk

### Code-health risk: low
- Additive, idempotent append guarded by a sentinel; mirrors the existing Step 7
  idiom. Blast radius = one new block in `setup_data_branch()` + 4 deleted stale
  lines in `.gitignore` + test assertions. · severity: low · → mitigation: TBD
- Two hardcoded copies of the negation list (setup + repo `.gitignore`) can drift
  until t777_29 lands; mitigated by an in-code comment pointing at t777_29 and a
  test asserting the block is present. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Plan directly implements the task's "Desired behaviour" (broad patterns +
  negations, minus `.gemini`, idempotent, negations-after-broad,
  `gitignore_changed=true`). Verification mirrors the task's own checklist.
  None material. · severity: low · → mitigation: TBD

## Final Implementation Notes

- **Actual work done:** Added an idempotent rendered-skill-closure ignore block
  to `aitask_setup.sh` Step 7 (`setup_data_branch()`), placed right after the
  existing `.aitask-data/` append and before Step 8. It writes the broad `*-/`
  patterns for `.claude`, `.agents`, `.opencode` plus the `!`-negations for the
  committed `*-remote-` / `*-remote-codex-` headless prerenders, guarded by a
  `grep -qF ".claude/skills/*-/"` sentinel and setting `gitignore_changed=true`.
  Dropped the 4 stale `.gemini` lines from this repo's `.gitignore`. Extended
  `tests/test_data_branch_setup.sh` (Test 1: block present + `.gemini` absent;
  Test 3: idempotency via `grep -c == 1`).
- **Deviations from plan:** One addition beyond the plan — dropping the
  `.gemini/skills/*-/` ignore line exposed ~40 dead, untracked `.gemini/skills/*-/`
  rendered-closure dirs (confirmed `.gemini` is no longer referenced anywhere in
  the render pipeline, so they never regenerate). With the user's explicit
  confirmation, deleted the whole untracked `.gemini/` directory as cleanup. The
  task had not anticipated the on-disk leftovers.
- **Issues encountered:** None. All 66 assertions in
  `test_data_branch_setup.sh` pass. `shellcheck` reports only pre-existing
  info/style findings elsewhere in the file — the new block is clean.
- **Key decisions:** Block embedded directly in `aitask_setup.sh` (not a `seed/`
  file) because `install.sh` deletes `seed/` post-install, so a seed file would
  be unreadable when a consumer runs `ait setup`. Kept this as interim option 1
  (two in-sync hardcoded copies with a `TODO(t777_29)` pointer) rather than
  building the `aitask_regen_gitignore_prerender.sh` unifier, which stays in
  t777_29's scope.
- **Upstream defects identified:** None
