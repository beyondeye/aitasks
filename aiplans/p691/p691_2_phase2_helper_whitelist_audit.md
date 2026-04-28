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

## Notes for sibling tasks (web docs, t691_3) — planning-time

- After this child lands, the SKILL.md has both phases. Web docs can describe both phases as one cohesive workflow.
- Highlight the discovery → AskUserQuestion → apply → idempotency loop — that is the user-facing UX hook.

## Final Implementation Notes

- **Actual work done:** Added three Phase 2 subcommands to `.aitask-scripts/aitask_audit_wrappers.sh` (~245 LOC growth, shellcheck clean): `discover-helpers`, `audit-helper-whitelist <helper>`, `apply-helper-whitelist <helper> [--touchpoint N]`. Added Phase 2 workflow section (Steps 7–11) to the SKILL.md.

- **Real-world gaps closed by this implementation:** Inserted runtime-only `commandPrefix` rules in `.gemini/policies/aitasks-whitelist.toml` for `aitask_contribution_review.sh`, `aitask_fold_content.sh`, `aitask_fold_mark.sh`, `aitask_fold_validate.sh`, `aitask_plan_externalize.sh` (5 entries inserted alphabetically among existing aitask_* helper rules).

- **Deferred (by design):** `aitask_add_model.sh` is missing from all 5 touchpoints. Not closed in this child because the sibling task t697 (analyze dev-only skill filtering in install tarball) is specifically tasked with deciding whether dev-only helpers should be added to seeds (touchpoints 3, 4, 5) or filtered out at install time. Closing the gap now would either preempt t697's recommendation or have to be reverted by it.

- **Deviations from plan:**
  - Plan's verification said "Phase 2 helper-discovery run on the current tree should report zero MISSING entries". Wrong premise — the audit *correctly* surfaces real drift in the framework that pre-dated t691.
  - Plan referenced sketch awk patterns using `match($0, /.../, m)` (a gawk extension); final implementation uses POSIX-portable `sub()` patterns instead.
  - Plan called for `apply-helper-whitelist` to use `jq` for JSON inserts; final implementation uses inline awk + head/tail splice (matching the Phase 1 TOML insert approach for consistency, and avoiding a `jq` runtime dependency).

- **Issues encountered:**
  1. **First implementation pass put new TOML rules at the top of the runtime gemini policy file.** Root cause: the awk pattern `^commandPrefix = ` matched non-aitask `commandPrefix` lines too (e.g., `commandPrefix = "ls"`), and string compare put `commandPrefix = "ls"` > `aitask_*` so the function selected the very first non-aitask rule as the "alphabetically next" insert anchor. Fix: tightened the awk pattern to `^commandPrefix = "\.\/\.aitask-scripts\/aitask_` so only aitask helper lines participate. Verified with `git checkout` revert and clean re-apply.
  2. **JSON insertion via `-v` passed regex string produced awk escape warnings and zero matches.** Root cause: complex regex strings with `\(`, `\.`, `\*` escapes get re-interpreted by awk's `~` operator with different escape semantics than literal `/regex/` syntax. Fix: refactored from a single parameterized `insert_json_helper_line` into two specialized functions (`insert_claude_settings_helper_line`, `insert_opencode_helper_line`) with inline `/regex/` literals, sharing a generic `splice_line_before` helper. Eliminated all `-v extract_re=...` plumbing.

- **Key decisions:**
  - Helper script grew to ~625 LOC total (Phase 1 + Phase 2). All Phase 2 subcommands honor the same exit-0 / structured-output convention as Phase 1.
  - `apply-helper-whitelist` runs all 5 touchpoints by default; `--touchpoint N` narrows to one (used by negative test and by SKILL.md for selective fixes).
  - Discovery scans not just `aitask-*` skill dirs but also the shared procedure trees (`task-workflow/`, `user-file-select/`, `ait-git/`) — these are reachable from aitask-* skills and any helper they invoke needs whitelisting.

- **Upstream defects identified:** None. The audit revealed 5 runtime-policy gaps and the `aitask_add_model.sh` cross-touchpoint gap, but these are exactly the drift this skill was built to discover; they are not "upstream defects" in the sense of pre-existing bugs in unrelated code.

- **Notes for sibling tasks:**
  - **t691_3 (web docs):** the SKILL.md now has both phases. The "Phase 2 — Helper-Script Whitelist" sections (Steps 7–11) document the per-touchpoint matrix, AskUserQuestion gate, and structured `MISSING:`/`WROTE:` output — useful source material to quote in docs.
  - **t697 (dev-only filtering analysis):** when t697 lands, the recommendation will determine whether `aitask_add_model.sh` (and any future dev-only helpers) get added to touchpoints 3/4/5 or left intentionally absent. Either way, the audit machinery built here is the lever — invoke `apply-helper-whitelist aitask_add_model.sh --touchpoint <N>` to close any subset of touchpoints.

- **Verification results:** shellcheck clean at warning level; Phase 1 idempotency holds (zero `GAP:`/`POLICY_GAP:` lines); Phase 2 audit reports only the 5 deferred `MISSING:*:aitask_add_model.sh` lines; `tests/test_opencode_setup.sh` 31/31 pass; `tests/test_gemini_setup.sh` 57/57 pass; negative test (delete archive helper from touchpoint 1 → audit detects → apply restores → re-audit clean) succeeds.
