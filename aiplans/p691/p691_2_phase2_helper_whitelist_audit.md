---
Task: t691_2_phase2_helper_whitelist_audit.md
Parent Task: aitasks/t691_audit_and_port_aitask_wrappers_across_code_agents.md
Sibling Tasks: aitasks/t691/t691_1_phase1_skill_wrapper_audit_port.md, aitasks/t691/t691_3_website_docs_audit_wrappers.md
Archived Sibling Plans: aiplans/archived/p691/p691_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-28 11:41
---

# Plan: t691_2 — Phase 2 helper-script whitelist audit

## Summary

Extend `aitask_audit_wrappers.sh` and `aitask-audit-wrappers/SKILL.md` (created in t691_1) with helper-script whitelist auditing across the 5 touchpoints from CLAUDE.md "Adding a New Helper Script". Discover which `.aitask-scripts/aitask_*.sh` helpers are referenced from `.claude/skills/aitask-*/SKILL.md`, verify each appears in all 5 permission systems, auto-fix gaps with user approval.

## Depends on

- t691_1 (Phase 1 must be complete; the helper script and SKILL.md exist).
- Read `aiplans/archived/p691/p691_1_*.md` once available for full Phase 1 implementation context.

## The 5 touchpoints

| # | File | Entry shape |
|---|---|---|
| 1 | `.claude/settings.local.json` | `"Bash(./.aitask-scripts/<name>.sh:*)"` in `permissions.allow` |
| 2 | `.gemini/policies/aitasks-whitelist.toml` | `[[rule]]` block with `commandPrefix = "./.aitask-scripts/<name>.sh"` |
| 3 | `seed/claude_settings.local.json` | mirror of #1 |
| 4 | `seed/geminicli_policies/aitasks-whitelist.toml` | mirror of #2 |
| 5 | `seed/opencode_config.seed.json` | `"./.aitask-scripts/<name>.sh *": "allow"` |

Codex exception: `.codex/config.toml` is prompt-only; no entry needed.

## Step 1 — Extend the helper script

Add three subcommands to `.aitask-scripts/aitask_audit_wrappers.sh`:

### `discover-helpers`

```bash
discover_helpers() {
  grep -hroE '\.aitask-scripts/aitask_[a-z_]+\.sh' .claude/skills/aitask-*/ \
    | sort -u \
    | sed 's|.*/||' \
    | while read -r helper; do
        printf 'HELPER:%s\n' "$helper"
      done
}
```

Output: one `HELPER:<basename>` per line. Always exit 0.

### `audit-helper-whitelist <helper>`

```bash
audit_helper_whitelist() {
  local helper="$1"
  local present_1 present_2 present_3 present_4 present_5

  grep -qF "Bash(./.aitask-scripts/${helper}:*)" .claude/settings.local.json    && present_1=1 || present_1=0
  grep -qF "commandPrefix = \"./.aitask-scripts/${helper}\""  .gemini/policies/aitasks-whitelist.toml && present_2=1 || present_2=0
  grep -qF "Bash(./.aitask-scripts/${helper}:*)" seed/claude_settings.local.json && present_3=1 || present_3=0
  grep -qF "commandPrefix = \"./.aitask-scripts/${helper}\""  seed/geminicli_policies/aitasks-whitelist.toml && present_4=1 || present_4=0
  grep -qF "\"./.aitask-scripts/${helper} *\": \"allow\""    seed/opencode_config.seed.json && present_5=1 || present_5=0

  for n in 1 2 3 4 5; do
    eval "p=\$present_$n"
    [[ "$p" == "0" ]] && printf 'MISSING:%d:%s\n' "$n" "$helper"
  done
}
```

(Real implementation will use a small loop instead of `eval`; sketch only.)

### `apply-helper-whitelist <helper> [--touchpoint N]`

Format-aware insert:
- Touchpoints 1, 3, 5: JSON — use `jq` to add the entry to the relevant array/object, preserving ordering as much as possible.
- Touchpoints 2, 4: TOML — reuse the alphabetical-insert awk helper from Phase 1 with a different rule template (`commandPrefix` instead of `argsPattern`).

Emit `WROTE:<touchpoint>:<helper>:<file>` for each successful insert. If `--touchpoint N` is given, only that touchpoint is targeted (useful for negative-test recovery).

## Step 2 — Extend the SKILL.md

Append a new "Phase 2 — Helper-Script Whitelist Audit" section after the Phase 1 commit step. Workflow:

1. Run `discover-helpers`. Loop calling `audit-helper-whitelist <helper>` for each. Collect all `MISSING:` lines.
2. If no `MISSING:` output: print "Phase 2 — no helper-whitelist gaps. ✓" and skip.
3. Else: present a per-helper × per-touchpoint matrix to the user.
4. `AskUserQuestion`: "Apply Phase 2 helper-whitelist fixes?" with options "Apply all", "Apply selected", "Skip Phase 2".
5. On "Apply selected": multiSelect AskUserQuestion with one option per `MISSING:<touchpoint>:<helper>` pair.
6. Call `apply-helper-whitelist <helper> --touchpoint <N>` for each selected entry. Collect `WROTE:` lines.
7. Commit (separate commit from Phase 1 — touches different files, follows the convention "one commit per logical phase"):
   - Commit message: `feature: Audit helper-script whitelist coverage across 5 touchpoints (t691_2)`.

## Step 3 — Update Phase-1+Phase-2 confirmation flow

Order in the SKILL.md:
1. Run Phase 1 discovery → AskUserQuestion gate → optional Phase 1 apply + commit.
2. Run Phase 2 discovery → AskUserQuestion gate → optional Phase 2 apply + commit.

User can skip Phase 1, accept only Phase 2, or vice versa. If both skipped, exit cleanly with no changes.

## Step 4 — Verification

1. `bash .aitask-scripts/aitask_audit_wrappers.sh discover-helpers` — outputs at least 10 helper names (e.g., `aitask_archive.sh`, `aitask_create.sh`, `aitask_pick_own.sh`, `aitask_query_files.sh`, etc.).
2. For each helper from step 1: `bash .aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist <helper>` produces zero `MISSING:` lines on the current tree (after t691_1 closes Phase 1 gaps and whitelists `aitask_audit_wrappers.sh` itself).
3. **Negative test:**
   - Save `.claude/settings.local.json`.
   - Remove the `Bash(./.aitask-scripts/aitask_archive.sh:*)` line.
   - Run `audit-helper-whitelist aitask_archive.sh` → must surface `MISSING:1:aitask_archive.sh`.
   - Run `apply-helper-whitelist aitask_archive.sh --touchpoint 1` → emits `WROTE:1:...`.
   - Re-audit → empty.
   - Restore the original file.
4. `bash tests/test_opencode_setup.sh` and `bash tests/test_gemini_setup.sh` — still pass.
5. `shellcheck .aitask-scripts/aitask_audit_wrappers.sh` — clean.

## Step 9 — Post-implementation

- Code commit (regular `git`): helper-script extension (Phase 2 subcommands) + SKILL.md Phase 2 section.
- Plan commit (`./ait git`): this plan file with Final Implementation Notes.
- Archive via `./.aitask-scripts/aitask_archive.sh 691_2`.

## Notes for sibling tasks (web docs, t691_3)

- After this child lands, the SKILL.md has both phases. Web docs can describe both phases as one cohesive workflow.
- Highlight the discovery → AskUserQuestion → apply → idempotency loop — that is the user-facing UX hook.
