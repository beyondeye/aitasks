---
Task: t1761_manual_verification_scope_ait_git_commit_in_skill_procedures.md
Base branch: main
Output branch: main
---

# Auto-Verification Execution Record — t1761

Strategy: **autonomous** (chosen at `manual-verification.md` step 1.5).
Profile: `fast`. Run on the current branch, no worktree — a
`manual_verification` task skips the Step 7 fork by design.

Verifies t1748 ("Scope the `./ait git commit` sites at the instruction layer",
commit `7e54ce865`).

## Execution Log

### Item 1 — plan-externalization commit reaches `aitask_task_commit.sh`

- Item text: Run `/aitask-pick` on any task under the fast profile; confirm the
  plan-externalization commit reaches `aitask_task_commit.sh` and reports
  `COMMITTED:`, with no permission prompt.
- Approach: file inspection of the **shipping rendered** fast-profile procedure
  + repo-wide guard run + live invocation inside this very `/aitask-pick` run.
- Actions run:
  - `grep -n 'aitask_task_commit\|COMMITTED\|SKIPPED' .claude/skills/task-workflow-fast-/plan-externalization.md`
  - `grep -rn './ait git commit' .claude/skills/task-workflow-fast-/{planning.md,plan-externalization.md,SKILL.md}`
  - `bash tests/test_no_unscoped_task_commit.sh`
  - `./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_task_commit.sh`
  - live: `./.aitask-scripts/aitask_task_commit.sh -m "ait: Record verification state for t1761" aitasks/t1761_*.md`
- Output (trimmed):
  - `plan-externalization.md:134,136` route both the `EXTERNALIZED` and
    `OVERWRITTEN` commits to `./.aitask-scripts/aitask_task_commit.sh`, and
    `:143` states `aiplans/<plan_file>` is **required** with the
    `SKIPPED:unknown:` rule.
  - `./ait git commit` in the fast-profile planning path: **NONE**.
  - Guard: `PASS: no unscoped ./ait git commit instruction in the skill / doc
    trees` — `Results: 69 passed, 0 failed, 69 total`.
  - Whitelist audit: **empty output** (present in all five touchpoints).
  - Live helper: `COMMITTED:1:ait: Record verification state for t1761`, exit 0,
    no permission prompt.
- Verdict: **pass**
- Caveat recorded on the item: a `manual_verification` task skips Step 6, so the
  live invocations were the manual-verification and auto-verification commit
  sites, not planning's own. The routing half of the claim is established by the
  shipping instruction text plus the repo-wide guard, which is the artefact
  t1748 actually changed.

### Item 2 — abort with a never-externalized plan

- Item text: Abort a task whose plan was never externalized (`task-abort.md`);
  confirm the agent reports the optional `SKIPPED:unknown:<plan_file>` correctly
  and does not read exit 0 as a partial failure.
- Approach: instruction inspection + real helper driven in an **isolated scratch
  git repo** (legacy mode, `ait git` → plain `git`), so the shared
  `.aitask-data` index was never involved.
- Actions run (scratch repo, `.aitask-scripts` symlinked to the real tree):
  - `./.aitask-scripts/aitask_task_commit.sh -m "ait: Abort t99: revert status to Ready" aitasks/t99_probe.md aiplans/p99_probe.md`
  - negative control A: required task file missing, plan file present
  - negative control B: both paths missing
- Output (trimmed):
  ```
  SKIPPED:unknown:aiplans/p99_probe.md
  COMMITTED:1:ait: Abort t99: revert status to Ready
  EXIT:0        → git show --name-only: aitasks/t99_probe.md   (only)

  control A: SKIPPED:unknown:aitasks/t98_missing.md
             COMMITTED:1:ait: Abort t98        EXIT:0
  control B: SKIPPED:unknown:aitasks/t97_missing.md
             SKIPPED:unknown:aiplans/p97_missing.md
             NOCHANGE                          EXIT:2
  ```
- `task-abort.md:63-73` names `<task_file>` required and `<plan_file>` optional,
  and says a `SKIPPED:` naming the plan file "is expected and needs no action".
- Control A is what makes this non-vacuous: a **required**-path miss *also*
  exits 0 with `COMMITTED:`, so "read the last line" would report success having
  dropped the task file. The per-path required/optional split is therefore
  necessary, not decorative.
- Verdict: **pass**

### Item 3 — concurrent staged task-data files

- Item text: With a second session holding staged task-data files, run a
  converted site; confirm `git show --name-only` on the resulting commit lists
  only this task's paths.
- Approach: live probe against the **real shared `.aitask-data` index**, plus a
  two-arm scratch-repo control for the pre-conversion command shape (the old
  shape was never run against the real repo).
- Actions run (real repo):
  - staged `aitasks/.probe_t1761_foreign_staged` via `./ait git add`
  - ran the converted site from `manual-verification.md:273`
  - `./ait git show --name-only HEAD`; `./ait git status --short`
  - unstaged and deleted the probe file
- Output (trimmed):
  ```
  COMMITTED:1:ait: Record verification state for t1761   EXIT:0
  git show --name-only HEAD →
      aitasks/t1761_manual_verification_scope_ait_git_commit_in_skill_procedures.md
  foreign entry after the commit → "A  aitasks/.probe_t1761_foreign_staged"
  another live session's dirty files → " M aiplans/p1759_…", " M aitasks/t1759_…"
  ```
- Two-arm scratch control:
  ```
  ARM A  pre-conversion `git commit -m …` (no pathspec)
         → commit contains ONLY aitasks/t51_theirs.md   (the foreign staged file;
           the intended t50 edit was not even included)
  ARM B  aitask_task_commit.sh -m … aitasks/t50_mine.md
         → commit contains ONLY aitasks/t50_mine.md
           foreign entry survives as "M  aitasks/t51_theirs.md"
  ```
- Verdict: **pass**

### Item 4 — Codex / OpenCode permission touchpoints (3, 6, 7)

- Item text: Confirm `aitask_task_commit.sh` runs without a permission prompt
  under the Codex and OpenCode trees — touchpoints 3, 6 and 7 were written but
  only the Claude one (touchpoint 1) was exercised during t1748.
- Approach: config inspection (independent of the audit tool), then live
  `codex exec` probes with a forced-`prompt` negative control.
- Actions run:
  - `./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_task_commit.sh` → **empty** (all five present)
  - direct read of every touchpoint (numbering confirmed against
    `aitask_audit_wrappers.sh:428-435`):

    | # | file | entry |
    |---|---|---|
    | 1 | `.claude/settings.local.json:47` | `Bash(./.aitask-scripts/aitask_task_commit.sh:*)` |
    | 3 | `.codex/rules/default.rules:74` | `prefix_rule(pattern = [".../aitask_task_commit.sh"], decision = "allow", …)` |
    | 4 | `seed/claude_settings.local.json:85` | `Bash(…:*)` |
    | 6 | `seed/codex_rules.default.rules:73` | `prefix_rule(…, decision = "allow", …)` |
    | 7 | `seed/opencode_config.seed.json:74` | `"./.aitask-scripts/aitask_task_commit.sh *": "allow"` |

  - `codex exec -s read-only "…aitask_task_commit.sh --help…"` → ran, printed the
    usage line, no prompt.
  - **negative control**: same run with
    `-c 'rules.prefix_rules=[{pattern=[{token="./.aitask-scripts/aitask_task_commit.sh"}],decision="prompt",…}]'`
    → **also ran**, unblocked.
- Why this is not a pass: the control did not discriminate, so the positive
  result is not evidence that the allowlist entry is what permits the command.
  Codex v0.153.4 reports `approval: never` for every `codex exec` run, and
  interactive `-a/--ask-for-approval` now offers only `on-request` / `never` —
  the `untrusted` policy was removed ("no longer supported"). There is no
  available surface under which a *non*-allowlisted helper would be prompted for,
  so "runs without a permission prompt" is currently unfalsifiable through Codex.
- OpenCode: this checkout has **no live OpenCode permission config** —
  `.opencode/` holds only `instructions.md`, `commands/`, `skills/`, and there is
  no root `opencode.json`. Touchpoint 7 is the **seed**, which only takes effect
  in a project bootstrapped by `ait setup`. So the OpenCode arm cannot be
  exercised in this repo at all.
- Verdict: **defer** — needs (a) a Codex version or surface with an approval
  policy that can actually refuse, and (b) a freshly seeded scratch project for
  the OpenCode arm.

## Cleanup

- `${TMPDIR:-/tmp}/…/scratchpad/auto_verify_1761_2/` — scratch git repo (item 2)
- `${TMPDIR:-/tmp}/…/scratchpad/auto_verify_1761_3/` — scratch git repo (item 3 control)
- `aitasks/.probe_t1761_foreign_staged` — unstaged and deleted; data worktree
  verified back to its prior state (only the other session's `t1759` /
  `p1759` edits remain dirty)
- No tmux sessions were created.
