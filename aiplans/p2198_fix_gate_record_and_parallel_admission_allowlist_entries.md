---
Task: t2198_fix_gate_record_and_parallel_admission_allowlist_entries.md
Base branch: main
Output branch: main
---

# t2198 — Fix gate_record and parallel_admission allow-list entries

## Context

t2175_4's helper-whitelist audit found two gaps in the agents' permission
allow lists, which have five touchpoints (`aitask_audit_wrappers.sh touchpoints`
→ ids 1,3,4,6,7):

1. `aitask_gate_record.sh` is called by task-workflow `gate-recording.md`, but
   the repo's own `.claude/settings.local.json` (touchpoint 1) has no allow
   entry for it. The other four touchpoints have one.
2. All five `aitask_parallel_admission` entries use the stem **without `.sh`**,
   but `parallel-admission.md` runs `./.aitask-scripts/aitask_parallel_admission.sh`.

Here is how each agent matches the stem entry (the task asked for this before
any change):
- **Codex** `prefix_rule(pattern = [...])` compares argv tokens by exact
  equality. The token `./.aitask-scripts/aitask_parallel_admission` is not equal
  to `…_admission.sh`, so the rule **never matches**.
- **OpenCode** `"<cmd> *"` is a wildcard glob. The pattern needs a literal space
  right after the stem, and the real command has `.sh` there, so it **never matches**.
- **Claude** `Bash(<prefix>:*)` is the legacy prefix syntax. The documentation
  says it is equivalent to a trailing ` *` with a word boundary, so it most
  likely **does not match** `…_admission.sh` either. I have not tested this live.
  The fix does not depend on the answer, because the exact `.sh` entry matches
  under every reading.

The stem was not a deliberate catch-all. `.aitask-scripts/` holds exactly one
`aitask_parallel_admission*` file, `aitask_parallel_admission.sh`, so the stem
covers no sibling helpers. It came from 2384e4a64 (t1569_4), and the commit
message says only "helper whitelist across all five touchpoints".

While checking every path, I found one more dead entry of the same kind:
`aitask_brainstorm_apply_patcher.sh` is allowed in touchpoints 1 and 3
(`.claude/settings.local.json:90`, `.codex/rules/default.rules:12`), but t891_2
(8943882c7) retired that helper. It is listed in
`retired_scripts_manifest.txt`, and nothing in the skills or scripts references
it. Removing these two lines is in scope: the new test (step 3) rejects
allow-list paths that do not exist, so it would fail without the removal.

## Implementation steps

1. **Replace the parallel-admission stem with the `.sh` name in all five touchpoints.**
   Each entry is one line, edited in place so its ordering position is unchanged:
   - `.claude/settings.local.json:40` and `seed/claude_settings.local.json:44`:
     `"Bash(./.aitask-scripts/aitask_parallel_admission.sh:*)",`
   - `.codex/rules/default.rules:44` and `seed/codex_rules.default.rules:43`:
     `prefix_rule(pattern = ["./.aitask-scripts/aitask_parallel_admission.sh"], …)`
   - `seed/opencode_config.seed.json:33`:
     `"./.aitask-scripts/aitask_parallel_admission.sh *": "allow",`

2. **Add `"Bash(./.aitask-scripts/aitask_gate_record.sh:*)",`** to
   `.claude/settings.local.json` directly after the `aitask_gate.sh` line
   (line 138). That matches where the seed file puts it (seed lines 97–98).
   **Remove** the retired `aitask_brainstorm_apply_patcher.sh` entries
   (`.claude/settings.local.json:90`, `.codex/rules/default.rules:12`).
   Check that the JSON still parses (`python3 -m json.tool`).

   Out of scope, but noted: the runtime `.claude/settings.local.json` also
   lacks the `aitask_gate_<verifier>.sh` entries that the seed carries. Those
   verifiers are launched by the gate orchestrator, not called from a skill,
   so `discover-helpers` does not report them. Under the "whitelist only
   skill-invoked helpers" rule (`aitasks_extension_points.md`), they are not a
   gap for this task.

3. **New regression test `tests/test_helper_whitelist_coverage.sh`.** It runs
   against the real repository and follows the `test_touchpoint_count_contract.sh`
   pattern (scratch cwd, then `cd` to the project, `tests/lib/asserts.sh`, and
   no subshell bodies, so no file-backed counters are needed):
   - **Coverage:** `aitask_audit_wrappers.sh discover-helpers` must return a
     non-empty list, so an empty list cannot pass by default. For every helper
     it lists, `audit-helper-whitelist <helper>` must print nothing; on failure
     the test shows the `MISSING:` lines. This is the real audit, not a copy of
     its matching logic.
   - **No dead or extensionless entries:** extract every
     `./.aitask-scripts/<path>` token from each touchpoint file (the file list
     comes from `aitask_audit_wrappers.sh touchpoints`) and assert that the path
     is a regular file. A stem entry such as `aitask_parallel_admission` and a
     retired helper both fail this check. The token count must be above zero.
   - **Claim boundary (stated in the test header, verified 2026-11-04):** the
     coverage check proves an entry *naming* each helper exists in each
     touchpoint, as `helper_present_in_touchpoint()` matches it — **not** that
     the entry is an effective allow. For touchpoints 3/6 that matcher checks
     only the `pattern = [...]` text and ignores `decision` (reproduced: a
     scratch fixture with seed Codex's `aitask_gate_record.sh` rule flipped to
     `decision = "forbidden"` still audited clean for touchpoint 6); for 1/4 it
     greps the whole file, so a `permissions.deny` entry would also satisfy it
     (latent — neither Claude file has a `deny` key today). Touchpoint 7 does
     require `": "allow"`. Making the matcher decision-aware belongs in the
     shared audit, not re-implemented in this test, and is handed off as a
     follow-up (see step 4).
   - **Negative controls**, to show each check can fail:
     (a) `audit-helper-whitelist aitask_no_such_helper_t2198.sh` prints exactly
     5 `MISSING:` lines (the touchpoint count, taken from `touchpoints`);
     (b) the dead-entry extractor runs on a scratch copy of the pre-fix
     parallel-admission line and must flag the stem path, which proves the
     extractor recognises the bug's exact shape.

4. **Follow-up for the decision-blind audit matcher (review finding, disposition: follow-up).**
   Record in the plan's Final Implementation Notes → *Upstream defects identified*:
   `.aitask-scripts/aitask_audit_wrappers.sh:474-487 — helper_present_in_touchpoint() ignores the decision for Codex touchpoints 3/6 (a decision = "forbidden" rule audits as covered) and matches Claude touchpoints 1/4 anywhere in the file (a permissions.deny entry would audit as covered)`.
   Step 8b then offers the standalone task. Its suggested scope: require
   `decision = "allow"` for 3/6 and membership of `permissions.allow` for 1/4
   (parse the JSON rather than grep), with negative controls for an explicit
   `forbidden` Codex rule and a Claude `deny` entry; note that
   `apply-helper-whitelist` short-circuits on the pattern match, so it would
   not "repair" a forbidden rule either. Once landed, `test_helper_whitelist_coverage.sh`
   inherits the stronger check without change, since it calls the real audit.

## Verification

- `bash tests/test_helper_whitelist_coverage.sh` passes. Before the fix it
  fails; check this by running the coverage loop once before editing.
- The coverage loop that found the bug, run again, prints nothing:
  `for h in $(./.aitask-scripts/aitask_audit_wrappers.sh discover-helpers | sed 's/^HELPER://'); do ./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist "$h"; done`
- `python3 -m json.tool` succeeds on both Claude JSON files and on the OpenCode seed.
- The neighbouring tests still pass: `bash tests/test_touchpoint_count_contract.sh`,
  `bash tests/test_opencode_setup.sh`, `bash tests/test_audit_wrappers_render_opencode_command.sh`.
- `shellcheck tests/test_helper_whitelist_coverage.sh`.

## Step 9 (Post-Implementation)

This task works on the current branch (`main`, fast profile), so there is no
merge. Archive with `./.aitask-scripts/aitask_archive.sh 2198`, then run
`./ait git push`.

## Risk

### Code-health risk: medium
- Editing the allow-list lines by hand could break JSON syntax in the Claude
  settings or OpenCode seed files. If the repo's own settings file breaks, every
  agent session in this checkout is affected. · severity: low · → mitigation:
  inline post-phase json-validate (already the `json.tool` step in
  Verification)
- The new test runs against the live tree. A future skill that calls a helper
  which is not yet allow-listed will make the test fail; that failure is the
  test doing its job, not a flake. · severity: low · → mitigation: None needed
- The coverage test inherits the audit's decision-blind matcher: an explicitly
  forbidden (Codex) or denied (Claude) entry naming the helper would pass it.
  · severity: medium · → mitigation: spawned follow-up via Step 8b (step 4); the
  test header states the boundary so the test's claim is not overstated

### Goal-achievement risk: low
- I am inferring Claude's `:*` behaviour from the documentation, not from a
  live test. The exact `.sh` entry is correct under every reading, so the
  outcome does not depend on it. · severity: low · → mitigation: None needed
