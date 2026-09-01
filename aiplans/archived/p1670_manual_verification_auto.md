---
Task: t1670_manual_verification_pre_implementation_resource_admission_ho.md
Worktree: (none — fast profile, current branch)
Branch: main (current branch)
Base branch: main
---

# t1670 — Manual verification of the resource-admission hook (auto-execution record)

Retroactive record of the autonomous auto-verification pass over t1670's
7-item checklist (verifying t1597). Strategy: `autonomous` — approach chosen
per item at execution time.

**Outcome: 6 pass, 1 fail.** The failure (item 7) spawned **t1672**.

Fixtures were built under a scratch directory so the repository's own
`aitasks/metadata/project_config.yaml` was never mutated; the key is
genuinely absent from it, which is what made item 1 directly observable.

## Execution Log

### Item 1

- Item text: With `resource_admission_command` unset, pick a task and reach Step 7:
  nothing is displayed, nothing changes, and no `.aitask-gates/<id>/` appears.
- Approach: CLI invocation + file inspection, on a clean scratch tree.
- Action run: `aitask_resource_admission.sh --task-id 1670 --plan …` from a
  scratch dir holding only `aitasks/metadata/project_config.yaml` (no key);
  `find . -type f` before and after. Wiring checked by grep over the rendered
  `task-workflow-fast-/SKILL.md`.
- Output (trimmed): `VERDICT:admit` / `REASON:none_configured` /
  `LOG:(none)`, exit 0, empty stderr. No `.aitask-gates/` directory and no
  new file of any kind. Run against the *real* repo the same call also
  returned `none_configured`, but `.aitask-gates/1670/` already existed there
  (a `change_baseline` from unrelated machinery), so the clean fixture is what
  discriminates. `resource-admission.md` step 2 mandates displaying nothing;
  the call site is `SKILL.md:402`, inside Step 7, with `test_resource_admission.sh`
  pinning `guard@378 < admission@400 < fork@406` for this profile.
- Verdict: pass

### Item 2

- Item text: hook `exit 2` with an `ADMISSION_REASON` line — park with the reason
  shown, status back to `Ready`, `plan_approved_at` stamped, `ait ls --plan-approved`
  lists it, no branch or worktree.
- Approach: CLI invocation on scratch fixtures + the existing end-to-end park test.
- Action run: four YAML encodings of the same command against the helper;
  `bash tests/test_resource_admission_stop.sh`.
- Output (trimmed): refuse path returns exit 1 / `VERDICT:refuse`, and the
  `ADMISSION_REASON:` extraction works — `DETAIL:no memory`. The park contract
  is proven on a real origin/clone pair by `test_resource_admission_stop.sh`
  (22/22): `Ready`, `assigned_to` cleared, marker stamped, `ait ls --plan-approved`
  returns exactly that task, plan kept **and** committed, no `aitask/<task_name>`
  branch, no `aiwork/` worktree — with a `stop_reason=drift` negative control
  that clears the marker, so the assertions can fail.
- **Caveat recorded, not a failure of t1597's code:** the command *as literally
  written in the checklist* must be encoded in YAML, and the single-quoted form
  `'sh -c ''echo "ADMISSION_REASON: no memory"; exit 2'''` is mis-parsed —
  `project_config_values()` strips one layer of surrounding quotes but does not
  collapse YAML's `''` escape, so the hook runs as
  `sh -c ''echo …''`, exits 2 (still a correct refuse) but prints nothing, and
  `DETAIL` degrades to `no reason given`. The inner-double-quoted form
  `'sh -c "echo ADMISSION_REASON: no memory; exit 2"'` and the recommended
  wrapper-script form both work. This is a pre-existing property of the shared
  config resolver, not of the admission helper.
- Verdict: pass

### Item 3

- Item text: re-pick the parked task under `fast` (`plan_preference: use_current`)
  with the hook now exiting 0 — drift check → worktree fork → implementation,
  no re-planning.
- Approach: source inspection of the rendered fast-profile procedures plus the
  parked-tree section of the stop test.
- Action run: read `planning.md:86-89`, `SKILL.md` Step 7; re-read
  `test_resource_admission_stop.sh` section 3.
- Output (trimmed): `plan_preference: use_current` skips straight to the
  Checkpoint ("Profile 'fast': using existing plan") — no re-planning. Reaching
  Step 7 implies the Checkpoint's Remote Drift Check returned "Continue anyway".
  On the real parked tree an admitting hook returns exit 0 / `VERDICT:admit`
  with the task still `Ready` and still marked, and a refusing hook on the same
  tree still refuses naming its reason — a negative control, so section 3 is not
  merely asserting that the fixture admits everything.
- **Wording inconsistency recorded:** the `fast` profile sets
  `create_worktree: false`, so under it Step 5 resolves "working on current
  branch" and Step 7's deferred fork is a no-op. The item's "worktree fork" step
  cannot occur under the profile the item itself names. The fork *ordering*
  (admission before fork) is separately pinned executably.
- Not driven live: a full re-pick of a parked task end to end.
- Verdict: pass

### Item 4

- Item text: a missing binary (helper exit 2) — park with the "could not be
  evaluated" wording, quoting exit 127 and the log path.
- Approach: CLI invocation on a scratch fixture.
- Action run: `resource_admission_command: /nonexistent/ait_missing_probe_1670`.
- Output (trimmed): exit 2, `VERDICT:error`, `REASON:command_error`,
  `DETAIL:resource_admission_command could not decide (exit 127): bash: line 1:
  /nonexistent/ait_missing_probe_1670: No such file or directory`, and `LOG:`
  naming a log that was really written. `resource-admission.md` renders exit 2 as
  "The resource-admission hook could not be evaluated: <DETAIL>. See <LOG>."
- Verdict: pass

### Item 5

- Item text: a LIST value (helper exit 3, the only path with no `VERDICT:` line)
  — the same park, message built from `DIAG:`.
- Approach: CLI invocation on a scratch fixture.
- Action run: `resource_admission_command: [/bin/true, /bin/false]`.
- Output (trimmed): exit 3; stdout carries **no `VERDICT:` line** —
  `REASON:not_scalar`, `LOG:(none)`, and
  `DIAG:resource_admission_command must be a single command, not a YAML list
  (got a 2-item list in aitasks/metadata/project_config.yaml) — point it at one
  wrapper script instead`. `LOG:(none)` is correct: the shape check runs before
  any log is allocated, so no path is named that the user could not read.
  The human message is separately on stderr, which the caller never parses.
- Verdict: pass

### Item 6

- Item text: the deferred-plan marker survives the `resource_admission` park and
  is consumed on the admitted re-pick; the `stop_reason` grouping in
  `plan-approved-stop.md` is the riskiest edit.
- Approach: the two existing contract tests plus source inspection of the
  consume site's position.
- Action run: `bash tests/test_plan_approved_marker_contract.sh` (33/33);
  `bash tests/test_resource_admission_stop.sh` (22/22); read `SKILL.md:541`.
- Output (trimmed): the park stamps the marker **on disk**, and the drift
  negative control clears it (`ait ls --plan-approved` → 0 tasks), so the
  stamping assertion is falsifiable. The grouping is pinned per-branch:
  `deferred@74 → now@78`, `drift@81 → clear@85`, with `resource_admission@75`
  sitting on the stamping branch, and the mitigation stop reverting with a plain
  `--status Ready` (no clear). Consumption is at `SKILL.md:541`, which is *after*
  the admission call at `:402` — so a park can never reach the clear, which is
  precisely why the marker survives it.
- Verdict: pass

### Item 7

- Item text: verify `settings_app.py` end-to-end in tmux — the
  `resource_admission_command` row renders in `ait settings` → Project Config,
  edits with the plain string editor, and saves back to `project_config.yaml`
  losslessly.
- Approach: TUI interaction. Real Textual app driven in a detached tmux session
  (200x50) with CWD set to a scratch copy of `aitasks/metadata/`, so the
  repository's own config was never written.
- Action run: launch `settings_app.py` under the framework venv → `c` (Project
  Config) → Tab/BTab to focus the row → Enter → type
  `sh -c "echo ADMISSION_REASON: no memory; exit 2"` → Enter → Tab to
  "Save Project Config" → Enter. Then inspect the written YAML, re-parse it,
  and run the admission helper against it.
- Output (trimmed): the row **renders** correctly (between `lint_command` and
  `learn_skill_authoring_guide`, with its schema summary) and Enter **opens the
  plain `EditStringScreen`**, not the multi-line preset editor — both correct.
  The TUI reported "Project config saved". But the file on disk reads:

  ```yaml
  resource_admission_command:
    sh -c "echo ADMISSION_REASON: no memory; exit 2"
  ```

  which `yaml.safe_load` returns as a **dict**,
  `{'sh -c "echo ADMISSION_REASON': 'no memory; exit 2"'}` — not the string.
  Running the helper against that saved config yields
  `VERDICT:admit` / `REASON:none_configured`, **exit 0**: a silent admit for a
  hook the user just configured, with nothing displayed anywhere.

  Root cause is `settings_app.py:2591`, `data[key] = yaml.safe_load(raw_value)`,
  which re-parses the user's typed command as a YAML document; any value
  containing `: ` becomes a mapping. Colon-free values round-trip fine — and this
  key's own documented `ADMISSION_REASON: <text>` convention makes a colon-space
  the normal case. The line is pre-existing; t1597 is what made it reachable.
- Verdict: **fail** → follow-up **t1672** created (diagnosis, reproduction and
  scope note appended there).

## Cleanup

- tmux session `ait1670verify` — killed.
- Scratch fixtures under
  `…/scratchpad/auto_verify_1670/` (`unset`, `refuse`, `missing`, `list`,
  `admit`, `qA`, `qB`, `qC`, `tui`) — session-scoped scratchpad, removed with it.
- No repository file was mutated by the probes: the real
  `aitasks/metadata/project_config.yaml` still carries no
  `resource_admission_command` key.
