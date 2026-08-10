---
Task: t1468_4_ait_ls_and_pick_surface_followup_kind.md
Parent Task: aitasks/t1468_mark_followup_task_provenance_and_surface_on_board.md
Sibling Tasks: aitasks/t1468/t1468_1_*.md, aitasks/t1468/t1468_2_*.md, aitasks/t1468/t1468_3_*.md, aitasks/t1468/t1468_5_*.md, aitasks/t1468/t1468_6_*.md
Archived Sibling Plans: aiplans/archived/p1468/p1468_*_*.md
Base branch: main
Output branch: main
---

# p1468_4 — `ait ls` and `/aitask-pick` surface the follow-up kind

Context is in `aitasks/t1468/t1468_4_ait_ls_and_pick_surface_followup_kind.md`.

**Precondition:** t1468_1 has landed.

## Implementation steps

### 1. `aitask_ls.sh` — parse

1.1 Add a `followup_kind)` arm beside the `issue_type)` arm at `:310-312`, plus
the module-level default (`:235` area) and the per-file reset inside
`parse_task_metadata` (`:404` area). **All three** — the reset is what stops one
task's value leaking into the next file.

### 2. `aitask_ls.sh` — display

2.1 Build `local followup_info=""` and set it conditionally, then append to the
single `display=` assembly at `:503`. Copy the uniform idiom already used by
`risk_info` / `assigned_info` / `issue_info` at `:479-502`.

2.2 **Also surface `issue_type`.** It is parsed at `:311` into `issue_type_text`
and then **never read** — `grep -n issue_type_text` returns exactly `:235`,
`:311`, `:404`, all writes. It is dead metadata, and the parent task explicitly
names this surface as needing type display *and* filtering.

2.3 **Display-only — do not make either a sort dimension.** Follow the explicit
`risk` precedent at `:229` ("risk is display-only — NOT a sort dimension (no
r_score)"). Sorting would require a 4th field in the `:508` echo *and* `-k4,4n`
at `:576`; leave both alone.

### 3. `aitask_ls.sh` — filters

3.1 Declare `FOLLOWUP_KIND_FILTER=""` and `TYPE_FILTER=""` beside
`LABELS_FILTER` at `:76-82`.
3.2 Parse `--followup-kind` and `--type` in the arg `case` at `:84-133`. This is
mandatory, not cosmetic: the fallthrough at `:112-131` treats a bare numeric as
`LIMIT` and **hard-fails** (`show_help; exit 1`) on anything else, so an
unregistered flag kills the command.
3.3 Apply both inside `process_task_file` with the **early-`return`** idiom used
by the labels filter at `:450-466` — filters run before display construction, and
this one function serves all four listing modes (children / tree / all-levels /
normal), so a single edit covers every mode.

### 4. `aitask_ls.sh` — help

4.1 Flags block `:35-50` (beside `-l, --labels`).
4.2 Frontmatter reference `:52-66` — add `followup_kind` with its vocabulary.
Note `:60` already lists the `issue_type` values and omits `manual_verification`;
fix that while here.

### 5. `/aitask-pick` presentation

`.claude/skills/aitask-pick/SKILL.md.j2`:

5.1 `:157-160` — the `-v` output-format note; update to match the new `ait ls`
line so the skill's description of the tool stays true.
5.2 `:173-180` — the Step 2b presentation template
(`<filename> [Priority: …, Effort: …, Status: …]`); add the kind.
5.3 `:182-196` — Step 2c builds each option's description as "brief summary with
metadata"; make sure the kind reaches it, since that is the text the human
actually reads when choosing.

Use terminology consistent with t1468_3's `GroupHeader` roll-up wording.

### 6. Regeneration

```bash
./.aitask-scripts/aitask_skill_rerender.sh default
./.aitask-scripts/aitask_skill_rerender.sh fast
./.aitask-scripts/aitask_skill_rerender.sh remote
```

Regolden `tests/golden/skills/aitask-pick/SKILL-{default,fast,remote}-claude.md`.
The three `remote` rendered copies are force-tracked and must be committed; stage
with an explicit path allowlist.

## Verification

1. `ait ls -v` shows the kind on a marked task, and shows **no** extra field on
   an unmarked one (negative control).
2. `ait ls --followup-kind risk_mitigation` and `ait ls --type bug` each return
   only matching tasks. **Check hit counts, not exit status** — a silent
   zero-match reads as clean and would pass a naive test.
3. Both filters behave in every listing mode: default, `--children N`, `--tree`,
   `--all-levels`.
4. Filters compose with `-l/--labels` and with each other.
5. An unknown *value* returns an empty result without erroring; an unknown *long
   flag* still hard-fails as before (do not accidentally loosen the `case`).
6. `/aitask-pick` shows the kind in its Step 2c selection options — drive it far
   enough to see them.
7. **New coverage — none exists today.** No test asserts the
   `[Status: …, Priority: …, Effort: …]` line as a whole, and **nothing exercises
   `-l/--labels` at all**. Add a shell test covering the display line and all
   three filters, copying the assertion style of `tests/test_xdeps_blocking.sh:114-125`
   (`assert_contains` on the captured `-v` line, with `assert_not_contains`
   negative controls at `:116`, `:125`, `:184`). Source `tests/lib/asserts.sh`.
8. `./.aitask-scripts/aitask_skill_verify.sh` — clean.
9. `shellcheck .aitask-scripts/aitask_ls.sh`
10. `bash tests/run_all_python_tests.sh` — read the **last** line.

## Notes for sibling tasks

- This child adds the first real test coverage for `aitask_ls.sh`'s display line
  and filters. t1468_6 can lean on it to verify backfilled tasks appear correctly.
