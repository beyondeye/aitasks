---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t1468_3]
issue_type: feature
status: Done
labels: [bash_scripts, task_workflow]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1468
implemented_with: claudecode/opus5
created_at: 2026-08-10 16:29
updated_at: 2026-08-12 08:24
completed_at: 2026-08-12 08:24
---

## Context

Parent: t1468 — mark auto-spawned follow-up tasks with a machine-readable kind.
Depends on **t1468_1** (the `followup_kind:` field).

`ait ls` and `/aitask-pick` are where a human actually chooses the next task, and
today neither can see whether a task is new work or a follow-up. This child makes
the kind visible and filterable in both.

Read the parent plan
`aiplans/p1468_mark_followup_task_provenance_and_surface_on_board.md`.

## Key files to modify

### `.aitask-scripts/aitask_ls.sh`

**Add `followup_kind` display + filter:**
- parse arm beside the `issue_type` arm at `:310-312` (defaults at `:235` and
  reset at `:404` — both needed)
- display suffix in the assembly at `:503`; copy the uniform
  `local X_info=""` → conditionally `X_info=", Label: $x_text"` → interpolate
  idiom at `:479-502`
- a `--followup-kind` filter inside `process_task_file` using the **early-`return`
  idiom** at `:450-466` (the labels filter). Filters run *before* display
  construction, and this one function serves all four listing modes
  (children / tree / all-levels / normal), so one edit covers everything.
- help text `:35-50` (flags) and `:52-66` (frontmatter reference)

**Display-only — NOT a sort dimension.** Follow the explicit `risk` precedent at
`:229` ("risk is display-only — NOT a sort dimension (no r_score)"). Making it a
sort key would mean adding a 4th field to the `:508` echo *and* a `-k4,4n` at
`:576`; do not.

**Fix the dead metadata while here.** `issue_type_text` is parsed at `:311` and
**never read** — `grep -n issue_type_text` returns exactly `:235`, `:311`, `:404`,
all writes. The parent task names this surface as needing display *and* filter.
Surface the type and add a `--type` filter alongside `--followup-kind`.

**Unknown long flags hard-fail** at `:112-131` (a bare numeric becomes `LIMIT`;
anything else hits `show_help; exit 1`), so both new flags must be added to the
`case` or the script dies on them.

### `.claude/skills/aitask-pick/SKILL.md.j2`

- `:157-160` — the `-v` output-format note; update it to match the new `ait ls`
  line.
- `:173-180` — the Step 2b presentation template
  (`<filename> [Priority: …, Effort: …, Status: …]`); add the kind so the human
  choosing work can see it.
- Step 2c option-building `:182-196` — the option *description* is "brief summary
  with metadata"; make sure the kind reaches it.

This is a `.md.j2`: rerender per profile and regolden.

```bash
./.aitask-scripts/aitask_skill_rerender.sh default
./.aitask-scripts/aitask_skill_rerender.sh fast
./.aitask-scripts/aitask_skill_rerender.sh remote
```

Goldens: `tests/golden/skills/aitask-pick/SKILL-{default,fast,remote}-claude.md`.
The three `remote` rendered copies are force-tracked and must be committed;
stage with an explicit path allowlist.

## Reference files for patterns

- `tests/test_xdeps_blocking.sh:114-125` — the display-line assertion style to
  copy: capture the `-v` line and `assert_contains "Status: Blocked (by …)"`,
  with `assert_not_contains` negative controls (`:116`, `:125`, `:184`). Sources
  `tests/lib/asserts.sh`.
- `tests/test_xdeps_parser.sh:80-91` — "parser must not crash on new frontmatter
  fields" round-trip.

## Verification steps

1. `ait ls -v` shows the kind on a marked task and shows nothing extra on an
   unmarked one (negative control).
2. `ait ls --followup-kind risk_mitigation` returns only matching tasks;
   `ait ls --type bug` likewise. Verify **hit counts**, not just exit status — a
   silent zero-match reads as clean.
3. Both filters work in every listing mode: default, `--children N`, `--tree`,
   `--all-levels`.
4. An unknown value for either flag is rejected (or returns empty) rather than
   erroring confusingly; an unknown *long flag* still hard-fails as before.
5. `/aitask-pick` lists the kind in its selection prompt (drive it far enough to
   see the Step 2c options).
6. **New test coverage — there is currently none for either:** no test asserts
   the `[Status: …, Priority: …, Effort: …]` line as a whole, and **nothing
   exercises `-l/--labels` at all**. Add coverage for the display line and for
   all three filters (`-l`, `--type`, `--followup-kind`).
7. `./.aitask-scripts/aitask_skill_verify.sh` — clean.
8. `shellcheck .aitask-scripts/aitask_ls.sh`
9. `bash tests/run_all_python_tests.sh` (read the LAST line for the verdict).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-11T19:06:23Z status=pass attempt=1 type=human
>
> Note: drift

> **✅ gate:plan_approved** run=2026-08-11T20:00:24Z status=pass attempt=2 type=human

> **✅ gate:review_approved** run=2026-08-11T20:35:09Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-12T05:24:10Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:4a313559d65cc41b

> **✅ gate:risk_evaluated** run=2026-08-12T05:24:10Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1468_4/risk_evaluated_2026-08-12T05:24:10Z-risk_evaluated-a1.log`
