---
Task: t1717_fix_stale_touchpoint_count_in_extension_points.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1717 — Fix the stale touchpoint count in `aitasks_extension_points.md`

## Context

`aidocs/framework/aitasks_extension_points.md:319` tells a planner to "surface
this **7-touchpoint** checklist as an explicit deliverable per helper", while
the table immediately above it (lines 306-312) lists **5** rows. t1657_4 hit
this while allowlisting a new helper: the doc cannot be followed literally.

t1717 asked for two checks before assuming a typo, because the number might be
a stale record of a real gap. Both were run — **neither adds a row**:

| Question | Answer | Evidence |
|---|---|---|
| Should a **runtime** OpenCode config be a touchpoint (Claude and Codex each have runtime + seed; OpenCode has only a seed)? | **No.** The runtime file is `<project>/opencode.json`, and it is *generated*: `aitask_setup.sh:2942-2953` copies or merges `aitasks/metadata/opencode_config.seed.json` into it. The framework repo carries no `opencode.json` (never has — `git log --all -- opencode.json` is empty), so there is no file here to hand-edit. Editing the seed is the whole write path. | `.aitask-scripts/aitask_setup.sh:2942-2953`, `install.sh:870` |
| Does `.agents/` (the shared Codex/agy root) carry a permission surface? | **No.** `.agents/` contains only `skills/` — no rules, settings, config, or toml file anywhere under it. Codex permissions live in `.codex/rules/default.rules`, which is already row 2 of the table. | `find .agents -not -path "*/skills/*"` → `.agents`, `.agents/skills` only |

**Root cause of the "7".** The number is the highest *stable numeric ID*, not a
count. `aitask_audit_wrappers.sh::touchpoint_file()` numbers touchpoints
`1, 3, 4, 6, 7` — IDs **2 and 5 are deliberately vacant**, the retired gemini
runtime/seed policies (`adding_a_new_codeagent.md` §13). When the prose was
written (t802, commit `cec464cd9`, May 2026) gemini was live and there really
were 7 touchpoints. t812_2 retired gemini's two, updated the table, and left the
sentence at 7. So: a stale record of a *removal*, not of a gap. A live
cross-check confirms 5 — `aitask_audit_wrappers.sh` itself is whitelisted in
exactly the five table rows and nowhere else.

**Why it recurred silently.** The add/retire checklist in
`adding_a_new_codeagent.md` never mentions the prose count. §13's "When adding an
agent" ends at "Update the Touchpoints table in `usage()`"; §23c's row for
`aitasks_extension_points.md` names only "Helper-script whitelist touchpoint
table". Fix the number without fixing the checklist and the next agent
add/remove reintroduces the same drift.

`aitasks_extension_points.md:319` is the **only** stale count in the repo. The
`CHANGELOG*` entries say "five" and are correct release history; every other
touchpoint site enumerates without counting.

## Approach

Correct the count, record the two "no row" answers so nobody re-investigates,
close the procedural gap that let it drift, and add an executable guard so it
cannot drift silently again. The count is worth keeping (it is the checkable
quantity a plan deliverable needs, and touchpoint tables are an explicit
literal-enumeration exception in `documentation_conventions.md:50`) — the guard
is what makes keeping it safe.

The guard needs ground truth for "what are the live touchpoints". Per the
confirmed risk mitigations below, that ground truth is a **real introspection
subcommand** on the canonical script rather than a textual slice of its source.

---

### Pre-phase (risk mitigations)

**P1 — `audit_wrappers_touchpoints_subcommand`** (inline pre-phase; confirmed
inline by the user — the procedure's recommendation was to spawn it as an
"after" task, and it is placed **first** rather than last because the guard test
in step 4 consumes it; inlining it as a post-phase would mean writing a
source-slicing probe and deleting it in the same task).

Add an introspection subcommand to `.aitask-scripts/aitask_audit_wrappers.sh`:

```bash
# touchpoints -> emit TOUCHPOINT:<id>:<file> for each live touchpoint.
cmd_touchpoints() {
    local id file
    for id in 1 3 4 6 7; do
        file=$(touchpoint_file "$id") || continue
        printf 'TOUCHPOINT:%s:%s\n' "$id" "$file"
    done
}
```

- Route it in `main()` beside `discover-helpers`.
- Add it to `usage()` under the Phase 2 subcommands block, and note in the
  existing "Touchpoints" section of `usage()` that `touchpoints` prints the list.
- The ID list here is the same literal the two existing
  `for touchpoint in 1 3 4 6 7` loops (lines 469, 605) already carry; assertion 6
  below pins all three against `touchpoint_file()` so they cannot diverge.
- **No new whitelist entries and no `ait` dispatcher case.**
  `aitask_audit_wrappers.sh` is already allowlisted in all five touchpoints, and
  it has no dispatcher entry today (the skill calls it by full path) — adding one
  would violate "The `ait` dispatcher is user-facing only".
- Addresses code-health risk: a source-text probe of `touchpoint_file()` would
  break silently on any reformat of that function.

**P2 — `guard_probe_not_vacuous`** (inline pre-phase).

In the guard test, before **any** comparison runs, assert the probe actually
produced something: the `touchpoints` call exits 0, emits ≥1 `TOUCHPOINT:` line,
and every line parses as `<id>:<path>` naming an existing file. An empty probe
would otherwise make every later assertion a vacuous empty-vs-empty match — the
guard would pass while checking nothing.

---

## Changes

### 1. `aidocs/framework/aitasks_extension_points.md` — the count (line 319)

`this 7-touchpoint checklist` → `this 5-touchpoint checklist`.

### 2. `aidocs/framework/aitasks_extension_points.md` — record the two answers

Add a short current-state note after the table (below line 316, before the
"When splitting a plan…" sentence). No version history in the body — just the
two facts that stop the re-investigation:

- The table rows are the live set; `aitask_audit_wrappers.sh::touchpoint_file()`
  numbers them `1, 3, 4, 6, 7`, with 2 and 5 kept vacant so numeric IDs stay
  stable. **Count rows, not IDs.**
- There is no runtime OpenCode row on purpose: `<project>/opencode.json` is
  generated by `ait setup` merging the seed, so the seed entry is the whole
  write path. `.agents/` holds skills only and carries no permission surface.

### 3. `aidocs/framework/adding_a_new_codeagent.md` — close the checklist gap

- **§13, "When adding an agent"** (after step 5, `~line 812`): add a step naming
  the two `aidocs/` surfaces — the `Current touchpoints:` block in §13 itself,
  and *both* the table **and the `N-touchpoint` count in the prose below it** in
  `aitasks_extension_points.md`.
- **§13, "When retiring"** (`~line 816`): same requirement — the paragraph
  currently says only "zero out the cases … drop the IDs from the iteration
  loops". This is the exact step t812_2 was missing.
- **§23c table row** for `aitasks_extension_points.md` (`~line 1246`): widen the
  Surface cell from "Helper-script whitelist touchpoint table" to name the
  count-carrying prose sentence too.

### 4. `tests/test_touchpoint_count_contract.sh` — the executable guard (new)

Derives the live touchpoint set by running the P1 subcommand — the canonical
source executing itself, no source-text parsing — and asserts every doc surface
agrees. Shape follows `tests/test_plan_approved_marker_contract.sh`
(self-contained, `tests/lib/asserts.sh`, own PASS/FAIL summary; test bodies stay
out of `( … )` subshells so the file-backed counters are not needed).

Assertions, after the P2 probe guard:

1. Live ID set is exactly `1 3 4 6 7` (pins the vacancy contract; a new agent
   touchpoint must consciously update this test).
2. The `aitasks_extension_points.md` table lists exactly the live file paths —
   both directions, so an added row with no source entry fails too.
3. The `N-touchpoint` number in the prose equals the live count.
4. §13's `Current touchpoints:` block in `adding_a_new_codeagent.md` lists
   exactly the live paths.
5. `.claude/skills/aitask-audit-wrappers/SKILL.md`'s touchpoint table lists the
   same IDs and paths.
6. Both `for touchpoint in …` loops (`aitask_audit_wrappers.sh:469,605`) and the
   P1 subcommand's own loop iterate exactly the live ID set — a
   `touchpoint_file()` entry the loops skip is a silently unaudited touchpoint.

---

### Post-phase (risk mitigations)

**P3 — `name_guard_test_in_agent_add_checklist`** (inline post-phase).

Extend the change-3 edits so §13's "When adding an agent" and "When retiring"
steps name, by path, the two sites a touchpoint change must now also touch:
`tests/test_touchpoint_count_contract.sh` (its hard-coded live-ID assertion) and
the `touchpoints` subcommand's ID loop. Without this the guard's assertion 1
surfaces as a surprise failure during an unrelated agent add.

---

## Verification

1. `./.aitask-scripts/aitask_audit_wrappers.sh touchpoints` prints exactly five
   `TOUCHPOINT:` lines with IDs 1, 3, 4, 6, 7.
2. `bash tests/test_touchpoint_count_contract.sh` → PASS, 0 FAIL.
3. **Negative controls** — the guard must be able to fail. One at a time, edit,
   run, confirm FAIL naming the right assertion, revert:
   - put `7-touchpoint` back in the prose → assertion 3 fails;
   - delete the `seed/opencode_config.seed.json` row from the table → 2 fails;
   - drop `7` from one `for touchpoint in` loop → 6 fails;
   - make `touchpoints` print nothing → the P2 probe guard fails (proving the
     other assertions are not passing vacuously).
4. `shellcheck .aitask-scripts/aitask_audit_wrappers.sh` and
   `shellcheck tests/test_touchpoint_count_contract.sh` → clean.
5. `grep -rn "[0-9]-touchpoint" --include="*.md" . | grep -v CHANGELOG` returns
   only the corrected line.
6. No `website/content/` change — the published `aitask-audit-wrappers` page
   states no count and does not enumerate subcommands, so `check_links.py` is not
   needed. Confirm with a final `git status` that nothing under
   `website/content/` is staged.

## Post-implementation

Step 9 (cleanup, archival, merge) per the task-workflow.

## Out of scope (observed, not fixed)

`.claude/skills/aitask-audit-wrappers/SKILL.md:15,181` still points at
`CLAUDE.md "Adding a New Helper Script"`; that section now lives in
`aidocs/framework/aitasks_extension_points.md`. A separate stale-pointer defect
across the skill and its rendered wrapper trees — worth its own task, not this
one's count fix.

## Risk

Reassessed once against the augmented plan, after the three inline mitigations
were confirmed (per `risk-mitigation-followup.md` Part 1 step 4). The
source-slicing fragility that drove the original code-health assessment is gone —
the probe is now a real subcommand — at the cost of one small public surface.

### Code-health risk: low

- The P1 subcommand is a new public surface on `aitask_audit_wrappers.sh` that
  must stay listed in `usage()` and cannot be removed without breaking the guard
  test · severity: low · → mitigation: inline pre-phase audit_wrappers_touchpoints_subcommand
- The guard test hard-codes the live ID set, so a legitimate new agent touchpoint
  makes it fail until updated — intended, but it is one more site an agent-add
  must touch · severity: low · → mitigation: inline post-phase name_guard_test_in_agent_add_checklist
- A probe that returns nothing would make every comparison vacuously true
  · severity: low · → mitigation: inline pre-phase guard_probe_not_vacuous

### Goal-achievement risk: low

- None identified: the defect is a single stale word, both open questions were
  answered from source with direct evidence, and the change is confined to two
  `aidocs/` files, one existing script, and one new test.

### Planned mitigations
- timing: pre-phase | name: audit_wrappers_touchpoints_subcommand | type: enhancement | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: code-health — source-text probe of touchpoint_file() breaks silently on reformat | desc: add a `touchpoints` subcommand emitting TOUCHPOINT:<id>:<file> and have the guard test consume it instead of slicing the script source
- timing: pre-phase | name: guard_probe_not_vacuous | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — an empty probe makes every later assertion vacuous | desc: assert the touchpoints probe exits 0, emits >=1 line, and every line names an existing file, before any comparison runs
- timing: post-phase | name: name_guard_test_in_agent_add_checklist | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the guard's hard-coded live-ID set is a surprise failure during an unrelated agent add | desc: name the guard test and the subcommand ID loop by path in §13's add/retire steps

## Final Implementation Notes

- **Actual work done:** All four planned changes plus the three inline
  mitigations landed as designed.
  1. `aidocs/framework/aitasks_extension_points.md:335` — `7-touchpoint` →
     `5-touchpoint`.
  2. Same file — a "Count rows, not IDs" note after the table, recording that
     `touchpoint_file()` numbers the live rows `1, 3, 4, 6, 7` with 2 and 5 kept
     vacant, plus the two "no row" answers (runtime `opencode.json` is generated
     by `ait setup` from the seed and absent from this repo; `.agents/` holds
     skills only and carries no permission surface).
  3. `aidocs/framework/adding_a_new_codeagent.md` §13 — the add-an-agent list
     grew steps 6-8 (the §13 block, *both* halves of the extension-points
     section including the prose count, and the guard test's live-ID list), the
     "When retiring" paragraph now says those steps apply to it unchanged, and
     the §23c row names the count alongside the table.
  4. `tests/test_touchpoint_count_contract.sh` (new, 165 lines, 11 assertions)
     pins the table, the prose count, the §13 enumeration, the
     `aitask-audit-wrappers` skill table and both iteration loops against the
     live set.
  - Pre-phase P1: `.aitask-scripts/aitask_audit_wrappers.sh` gained a
    `touchpoints` subcommand plus `TOUCHPOINT_ID_MAX`, routed in `main()` and
    documented in `usage()`.
  - Pre-phase P2: the test aborts with a `FATAL:` line when the probe yields no
    usable output, instead of running assertions that would compare empty to
    empty.
  - Post-phase P3: §13 steps 4 and 8 name `cmd_touchpoints()`,
    `TOUCHPOINT_ID_MAX` and the guard test by path.

- **Deviations from plan:** One, in P1's implementation shape. The plan sketched
  `cmd_touchpoints()` iterating a literal `1 3 4 6 7`, which would have made the
  subcommand a *fourth* copy of the ID list. It instead probes
  `touchpoint_file()` over `1..TOUCHPOINT_ID_MAX` (32) and keeps whatever
  answers, so the reported set cannot drift from the map it reports. This
  strengthens the plan's stated intent ("the canonical source executing
  itself"); assertion 6 still pins the two pre-existing loops. No acceptance
  criterion changed.

- **Issues encountered:**
  - The `.aitask-data` worktree is stuck mid-rebase (interactive rebase of
    `aitask-data` onto `875a51732`, conflicted on
    `aitasks/t1705_*.md`, 26 of 37 commits done, stalled since 2026-09-06
    17:41, no syncer process alive). `./ait git` refuses to run while that state
    exists, so the plan-file commit is deferred by the user's explicit choice;
    task-data writes through `task_git` (ownership, gate ledger, risk fields,
    `implemented_with`) all succeeded, only pushes failed. The code commit is
    unaffected — it lands on `main` via plain `git`.
  - `aitask_remote_drift_check.sh` reported
    `OVERLAP:seed/opencode_config.seed.json` for `origin/main`, but neither
    drifted commit (`24f8d010b`, `3160b7d4b`) touches that file — both are
    test-only additions. Treated as a false positive and confirmed by
    inspection before continuing.

- **Key decisions:**
  - **The count stays, and is guarded, rather than being deleted.** Removing
    "5-touchpoint" would also remove the drift, but the count is the checkable
    quantity the surrounding sentence needs ("an explicit deliverable per
    helper"), and touchpoint tables are a named literal-enumeration exception in
    `documentation_conventions.md`. Guarding it keeps the information and
    removes the hazard.
  - **Ground truth is the script executing itself, not a regex over its text.**
    A source-text probe of `touchpoint_file()` would break silently on any
    reformat of that function, which is the same class of failure this task
    exists to fix.
  - **Assertion 1 deliberately hard-codes `1 3 4 6 7`.** The vacancy of IDs 2
    and 5 is a contract, not an incidental fact, so a new touchpoint must be a
    conscious edit — and §13 step 8 now tells the next agent that, by path.
  - **The probe guard aborts the run.** A guard test whose assertions can only
    pass is worse than no guard, so an unusable probe is a hard stop with a
    `FATAL:` explanation rather than a silent green run.

- **Upstream defects identified:**
  - `.claude/skills/aitask-audit-wrappers/SKILL.md:15,181 — points readers at
    CLAUDE.md "Adding a New Helper Script"; that section now lives in
    aidocs/framework/aitasks_extension_points.md, and the same stale pointer is
    replicated across the rendered Codex/OpenCode wrapper trees.` (The identical
    pointer in `aitask_audit_wrappers.sh::usage()` was corrected here, since
    that line was already being edited.)
