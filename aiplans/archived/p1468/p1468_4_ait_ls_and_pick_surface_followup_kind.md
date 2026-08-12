---
Task: t1468_4_ait_ls_and_pick_surface_followup_kind.md
Parent Task: aitasks/t1468_mark_followup_task_provenance_and_surface_on_board.md
Sibling Tasks: aitasks/t1468/t1468_1_*.md, aitasks/t1468/t1468_2_*.md, aitasks/t1468/t1468_3_*.md, aitasks/t1468/t1468_5_*.md, aitasks/t1468/t1468_6_*.md
Archived Sibling Plans: aiplans/archived/p1468/p1468_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-11 19:54
---

# p1468_4 — `ait ls` and `/aitask-pick` surface the follow-up kind

Context is in `aitasks/t1468/t1468_4_ait_ls_and_pick_surface_followup_kind.md`.

**Precondition:** t1468_1 has landed (verified — `lib/followup_kinds.py` and
`lib/followup_kinds_sh.sh` exist and `followup_kind:` round-trips).

**Re-verified against current source (2026-08-11).** Every structural claim in
the previous revision still holds; the line numbers had drifted ~+16 in the
middle of `aitask_ls.sh` (the t1472 `deps-unblock-batch` rewrite). All line
references below are the re-verified current ones. Three substantive corrections
came out of that verification and are folded in:

1. **Filters validate their values** rather than silently matching nothing
   (user decision — see "Design decisions" below). The previous revision's
   verification step 5 said the opposite; it is rewritten.
2. **`--no-followup-kind` is added** so the queue can be filtered down to
   genuine new work — the parent task's headline motivation (user decision).
3. **`aitask-pick` has NO force-tracked rendered variants.** The task file and
   the previous plan revision both claim "the three `remote` rendered copies are
   force-tracked and must be committed". That is false for this skill:
   `.gitignore:47-49` ignores every `*-/` rendered dir and the un-ignore list at
   `:60-68` names only `aitask-pickrem`, `aitask-pickweb` and `task-workflow`.
   `git ls-files | grep -- '-remote-' | grep -i pick` returns no
   `aitask-pick-remote-` entry. The only tracked artifacts of a `.j2` edit here
   are the template itself and the three goldens.

---

## Design decisions

**D1 — Display format.** The `-v` line gains two fields in the existing optional
suffix zone, after `Effort:` and before `Assigned:`:

```
t1468_4_foo.md [Status: Ready, Priority: High, Effort: Medium, Type: feature, Follow-up: risk_mitigation]
```

- `Type:` is **always** shown in `-v` (the parser defaults `issue_type_text` to
  `feature`, so there is no "absent" state to represent).
- `Follow-up:` appears **only** when the field is present — absent means "not a
  follow-up", per t1468_1's no-tombstone contract. Never assert `== None`.
- The value printed is the **raw canonical token** (`risk_mitigation`), not
  t1468_3's human label ("risk mitigation"), so it can be pasted straight into
  `--followup-kind`. t1468_3's glyph/label vocabulary is for the board's
  space-constrained card and group roll-up; a plain-text list line has room for
  the real token and gains copy-pasteability from it.

**Safe for existing consumers — verified.** The only code that reads this line is
`aitask_create.sh:382,1298` and `aitask_update.sh:1258,1341` (fzf pickers), and
both extract only the leading `^t[0-9]+`. Nothing parses the bracket contents
positionally.

**D2 — Filters reject unknown values.** `--followup-kind` and `--type` both
validate and `die` on an unrecognised value, listing the valid set. Rationale: a
silent zero-match is indistinguishable from "no such tasks", which is exactly the
failure mode a typo produces. `--followup-kind` validates through
`lib/followup_kinds_sh.sh` (the bridge is lazy, so nothing is paid unless the
flag is used) and **fails closed** when the vocabulary cannot be resolved — the
contract t1468_1's sibling notes hand to this child. That failure is scoped to
invocations that actually pass the flag; a plain `ait ls` never touches Python
for this.

**D3 — `--no-followup-kind` is a separate boolean flag**, not a `none` sentinel
inside `--followup-kind`'s closed vocabulary (no magic values). It needs no
vocabulary lookup, so it works even when the bridge cannot resolve. Passing both
`--followup-kind` and `--no-followup-kind` is an error.

**D4 — Display-only, NOT a sort dimension.** Follow the explicit `risk`
precedent at `aitask_ls.sh:245` ("risk is display-only — NOT a sort dimension
(no r_score)"). Sorting would require a 4th field in the `:524` echo *and* a
`-k4,4n` at `:592`; leave both alone.

**D5 — One shared issue-type reader instead of a fourth copy.**
`get_valid_task_types` exists **three** times today (`aitask_create.sh:1147`,
`aitask_update.sh:883`, `aitask_stats_legacy.sh:53`), each repeating the same
`bug/feature/refactor` fallback. Rather than adding a fourth for `ait ls`, add
one pure reader to `lib/task_utils.sh` and have all three delegate. The
side-effecting `ensure_task_types_file` call stays in the two write-path
scripts — a read-only lister must not create files in the user's repo. This is
a small down-payment on **t720** (`issue_type_list_single_source_of_truth`), not
a substitute for it; note that in the comment.

---

## Implementation steps

### Pre-phase (risk mitigations)

1. `[negctrl_display_line]` Create `tests/test_ls_display_and_filters.sh` with
   its fixture repo and write the **display-line assertions in their final
   form** — `t11`'s `-v` line contains `Type: feature` and
   `Follow-up: risk_mitigation`, `t10`'s contains `Type: bug` and
   `assert_not_contains "Follow-up"` — then run the file against **unmodified**
   `aitask_ls.sh` and confirm it goes RED. Record the failing test id and the
   exact failure message in Final Implementation Notes. At the end the same
   assertions, **byte-unchanged**, must pass. Asserting today's (field-less)
   line instead would go green against unchanged source and prove nothing.

### 1. `lib/task_utils.sh` — pure issue-type vocabulary reader

Add beside the other task-metadata helpers:

```bash
# read_valid_task_types [file]
# Pure reader for the issue-type vocabulary — prints one type per line, sorted.
# Unlike the callers' get_valid_task_types wrappers it does NOT call
# ensure_task_types_file: a read-only lister (aitask_ls.sh) must never create
# files in the user's repo. Folding the whole vocabulary onto one seam across
# the 32+ duplication sites is t720's job; this is only the shell-side reader.
read_valid_task_types() {
    local f="${1:-${TASK_TYPES_FILE:-aitasks/metadata/task_types.txt}}"
    if [[ -s "$f" ]]; then
        sort -u "$f"
    else
        printf '%s\n' "bug" "feature" "refactor"
    fi
}
```

Then collapse the three existing copies to delegate, preserving each one's
`ensure_task_types_file` side effect exactly where it is today:

| file | line | new body |
|---|---|---|
| `aitask_create.sh` | `:1147` | `ensure_task_types_file; read_valid_task_types` |
| `aitask_update.sh` | `:883` | `ensure_task_types_file; read_valid_task_types` |
| `aitask_stats_legacy.sh` | `:53` | `read_valid_task_types` (has no `ensure_` call today — do not add one) |

All three already `source lib/task_utils.sh` (verified: `:11`, `:11`, `:9`) and
all three set `TASK_TYPES_FILE` before use.

### 2. `aitask_ls.sh` — parse

2.1 Source the bridge beside the existing lib sources at `:5-7`:

```bash
# shellcheck source=lib/followup_kinds_sh.sh
source "$SCRIPT_DIR/lib/followup_kinds_sh.sh"
```

It is lazy and memoising — sourcing costs nothing until `followup_kinds_pipe`
is called. `die` is already in scope (`task_utils.sh` → `terminal_compat.sh`).

2.2 Add `TASK_TYPES_FILE="$TASK_DIR/metadata/task_types.txt"` beside
`TASK_DIR="aitasks"` at `:9`.

2.3 Add a `followup_kind)` arm to the `case "$key"` in `parse_yaml_frontmatter`,
immediately after the `issue_type)` arm at `:326-328`:

```bash
                followup_kind)
                    followup_kind_text="$value"
                    ;;
```

`^([a-z_]+):` (`:285`) accepts the key — verified.

2.4 **All three sites, or the value leaks between files:** the module-level
default `followup_kind_text=""` beside `issue_type_text="feature"` at `:251`,
**and** the per-file reset in `parse_task_metadata` beside `:420`. The reset is
what stops one task's kind appearing on the next task's line.

### 3. `aitask_ls.sh` — display

In the `VERBOSE` block, following the uniform
`local X_info=""` → conditional → interpolate idiom already used by
`assigned_info` / `issue_info` / `risk_info` at `:496-518`:

```bash
        local type_info=""
        if [[ -n "$issue_type_text" ]]; then
            type_info=", Type: $issue_type_text"
        fi
        local followup_info=""
        if [[ -n "$followup_kind_text" ]]; then
            followup_info=", Follow-up: $followup_kind_text"
        fi
```

and extend the single `display=` assembly at `:519`:

```bash
        display="${indent_prefix}$filename [Status: $display_status, Priority: $p_text${risk_info}, Effort: $e_text${type_info}${followup_info}${assigned_info}${issue_info}${pr_info}${contributor_info}]"
```

`issue_type_text` was parsed at `:327` and **never read** — `grep -n
issue_type_text` returns exactly `:251`, `:327`, `:420`, all writes. This is the
edit that makes it live.

### 4. `aitask_ls.sh` — flags and validation

4.1 Declare beside `LABELS_FILTER` at `:80`:

```bash
LABELS_FILTER=""
TYPE_FILTER=""
FOLLOWUP_KIND_FILTER=""
NO_FOLLOWUP_KIND=false
```

4.2 Parse in the arg `case` at `:86-133`. **Mandatory, not cosmetic:** the
fallthrough at `:117-131` treats a bare numeric as `LIMIT` and hard-fails
(`show_help; exit 1`) on anything else, so an unregistered long flag kills the
command.

```bash
        --type)
            TYPE_FILTER="$2"
            shift 2
            ;;
        --followup-kind)
            FOLLOWUP_KIND_FILTER="$2"
            shift 2
            ;;
        --no-followup-kind)
            NO_FOLLOWUP_KIND=true
            shift
            ;;
```

4.3 Validate **after** the parse loop, before the `TASK_DIR` existence check at
`:136` — so a bad flag is rejected before any scanning work:

```bash
if [[ -n "$FOLLOWUP_KIND_FILTER" && "$NO_FOLLOWUP_KIND" == true ]]; then
    die "--followup-kind and --no-followup-kind are mutually exclusive."
fi

if [[ -n "$FOLLOWUP_KIND_FILTER" ]]; then
    kinds="$(followup_kinds_pipe)" \
        || die "cannot resolve the follow-up kind vocabulary (lib/followup_kinds.py unreachable) — --followup-kind cannot be validated."
    is_valid_followup_kind "$FOLLOWUP_KIND_FILTER" \
        || die "Invalid follow-up kind: $FOLLOWUP_KIND_FILTER (must be one of: ${kinds//|/, })"
fi

if [[ -n "$TYPE_FILTER" ]]; then
    grep -qFx "$TYPE_FILTER" <(read_valid_task_types) \
        || die "Invalid type: $TYPE_FILTER (must be one of: $(read_valid_task_types | tr '\n' ',' | sed 's/,$//'))"
fi
```

Two distinct death messages for `--followup-kind` — "invalid value" vs "cannot
verify" — because "unverifiable" is its own state, not a negative result. Note
`--no-followup-kind` deliberately triggers **no** vocabulary lookup, so it keeps
working when Python is unavailable.

### 5. `aitask_ls.sh` — apply the filters

Inside `process_task_file`, using the **early-`return`** idiom of the labels
filter at `:463-479`, immediately after it. Filters run before display
construction, and this one function serves all four listing modes (children /
tree / all-levels / normal), so a single edit covers every mode:

```bash
    # Apply issue-type filter
    if [[ -n "$TYPE_FILTER" && "$issue_type_text" != "$TYPE_FILTER" ]]; then
        return
    fi

    # Apply follow-up-kind filters (mutually exclusive; validated at parse time)
    if [[ -n "$FOLLOWUP_KIND_FILTER" && "$followup_kind_text" != "$FOLLOWUP_KIND_FILTER" ]]; then
        return
    fi
    if [[ "$NO_FOLLOWUP_KIND" == true && -n "$followup_kind_text" ]]; then
        return
    fi
```

`--type feature` also matches a file with no `issue_type:` at all, because the
parser defaults to `feature`. Document that in the help text rather than
inventing an unset state.

### 6. `aitask_ls.sh` — help text

6.1 Flags block `:36-50`, beside `-l, --labels`:

```
  --type TYPE   Filter by issue type (see aitasks/metadata/task_types.txt).
                A task with no issue_type: field counts as 'feature'.
  --followup-kind KIND  Filter to auto-spawned follow-ups of one kind.
  --no-followup-kind    Only tasks that are NOT auto-spawned follow-ups
                (genuine new work). Mutually exclusive with --followup-kind.
```

6.2 Frontmatter reference `:52-66`: add a `followup_kind:` line with its
vocabulary, and **fix the pre-existing gap at `:60`** — the `issue_type` value
list omits `manual_verification`, which *is* in
`aitasks/metadata/task_types.txt`.

### 7. `/aitask-pick` presentation

`.claude/skills/aitask-pick/SKILL.md.j2` (line refs here are exact and current):

7.1 `:157-160` — the `-v` output-format note; update it to the new line so the
skill's description of the tool stays true:

```
t<number>_<name>.md [Status: <status>, Priority: <priority>, Effort: <effort>, Type: <issue_type>, Follow-up: <followup_kind>]
```
plus a sentence saying `Follow-up:` is present only on auto-spawned follow-ups
and absent means genuine new work.

7.2 `:173-180` — the Step 2b presentation template; add the kind:

```
<filename> [Priority: <priority>, Effort: <effort>, Status: <status>, Type: <issue_type>]
<brief summary of task content>
Follow-up: <followup_kind> (omit this line entirely if the task is not a follow-up)
Children: <N children pending> (or "None")
```

7.3 `:194-196` — Step 2c builds each option's description as "brief summary with
metadata"; state explicitly that the description must carry the follow-up kind
when present, since that is the text the human actually reads when choosing.

These three sites are outside every `{% if %}` gate, so the edit lands
identically in all three profile goldens.

### 8. Regeneration

The rendered `aitask-pick-*-/` closures are **gitignored** for every profile
(see correction 3 above) and self-heal at invocation via the stub's
skip-if-fresh render, so no rendered copy needs staging. Refresh them anyway so
a live session picks the change up immediately:

```bash
./.aitask-scripts/aitask_skill_rerender.sh default
./.aitask-scripts/aitask_skill_rerender.sh fast
./.aitask-scripts/aitask_skill_rerender.sh remote
```

Regenerate the three tracked goldens — this is what the suite compares:

```bash
PY="$(.aitask-scripts/lib/python_resolve.sh >/dev/null 2>&1; echo)"   # see the test for the exact resolver call
for p in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/aitask-pick/SKILL.md.j2 \
    aitasks/metadata/profiles/$p.yaml claude \
    > tests/golden/skills/aitask-pick/SKILL-$p-claude.md
done
```

(`$PYTHON` = `require_ait_python` from `lib/python_resolve.sh`, exactly as
`tests/test_skill_render_aitask_pick.sh:34-37` resolves it.)

Stage with an explicit path allowlist — a rerender touches many gitignored
targets and `git add -A` would be wrong here.

### 9. Website docs

`website/content/docs/commands/task-management.md`, `## ait ls` section:

- the `-v` row (`:101`) currently reads "show status, priority, effort,
  assigned, issue" — add type and follow-up kind;
- three new option rows for `--type`, `--followup-kind`, `--no-followup-kind`;
- one worked example line, e.g. `ait ls -v --no-followup-kind 15   # genuine new
  work only`.

Current-state prose only — no version history, per
`aidocs/framework/documentation_conventions.md`.

### Post-phase (risk mitigations)

1. `[pin_task_type_validation]` With the `get_valid_task_types` delegation in
   place, pin its behaviour **through the real entry points**, not through the
   helper: in the new test file assert that
   `aitask_create.sh --batch --name x --type bogus` exits non-zero with
   `Invalid type:`, that the same command with `--type manual_verification`
   succeeds, and that pointing `TASK_TYPES_FILE` at an empty file still yields
   exactly `bug`, `feature`, `refactor`. Run these **before** the step-1 edit to
   record the baseline, and again after — the outputs must be identical.

---

## Verification

New test file `tests/test_ls_display_and_filters.sh`, modelled on
`tests/test_xdeps_blocking.sh` — build a real fixture repo under `mktemp -d`,
`cd` into it, and run the **real** `$PROJECT_DIR/.aitask-scripts/aitask_ls.sh`
against it (no scaffold copy needed: `SCRIPT_DIR` resolves back to the real
`lib/`, so the bridge is found). Source `tests/lib/asserts.sh`; test bodies stay
in the main shell, so the in-process `PASS`/`FAIL` counters are correct without
the file-backed opt-in. Assertion style copied from
`test_xdeps_blocking.sh:114-125` — capture the `-v` line and `assert_contains`,
with `assert_not_contains` negative controls.

**This is the first test coverage `aitask_ls.sh`'s display line and `-l/--labels`
have ever had** — verified: no test asserts the `[Status: …, Priority: …,
Effort: …]` line as a whole, and every `--labels` hit under `tests/` belongs to
`aitask_create.sh` / `aitask_update.sh`, never the `ls` filter.

Fixture: `t10` (bug, `labels: [ui]`, no kind), `t11` (feature,
`followup_kind: risk_mitigation`, `labels: [backend]`), `t12` (test,
`followup_kind: qa_test_gap`, `labels: [ui, backend]`), `t13` (feature parent
with `children_to_implement`), `t13/t13_1` (enhancement,
`followup_kind: upstream_defect`), `t13/t13_2` (chore, no kind).

1. **Display line.** `-v` on `t11` contains `Type: feature` **and**
   `Follow-up: risk_mitigation`; `-v` on `t10` contains `Type: bug` and
   `assert_not_contains "Follow-up"` (negative control). Assert the whole
   bracket for at least one task so the field order is pinned, not just
   substrings.
2. **Positive filters, by hit count.** `--followup-kind risk_mitigation` →
   exactly 1 line and it is `t11`; `--type bug` → exactly 1 and it is `t10`.
   Assert `wc -l`, not exit status — a silent zero-match reads as clean.
3. **`--no-followup-kind`** → exactly `t10` + `t13` in the default (parents)
   mode; `assert_not_contains` for `t11` and `t12`.
4. **Every listing mode.** `--followup-kind upstream_defect` returns `t13_1` in
   `--children 13`, `--tree` and `--all-levels`, and returns **zero** lines in
   the default parents-only mode (`t13_1` is a child). Same for `--type chore`.
5. **Composition.** `--type feature --followup-kind risk_mitigation` → `t11`;
   `--type test --followup-kind risk_mitigation` → 0 lines; `-l ui --type bug` →
   `t10`; `-l ui` alone → `t10` + `t12` (the first-ever `-l` coverage).
6. **Rejection.** `--followup-kind bogus` exits non-zero and names the valid
   kinds; `--type bogus` exits non-zero and names the valid types;
   `--followup-kind risk_mitigation --no-followup-kind` exits non-zero; an
   unknown long flag (`--nope`) still hard-fails with the pre-existing
   "Unknown argument" + help path (do not accidentally loosen the `case`).
7. **Fail-closed, with a positive control.** With
   `AIT_FOLLOWUP_KINDS_DIR=<empty dir>`, `--followup-kind risk_mitigation` dies
   with the "cannot resolve" message (not the "invalid value" one — assert the
   distinct text); with the same env and **no** kind flag, plain `-v` still
   succeeds and still prints `Follow-up: risk_mitigation` for `t11` (the lazy
   bridge is never consulted for display).
8. `bash tests/test_skill_render_aitask_pick.sh` — goldens match after
   regeneration.
9. `bash tests/test_xdeps_blocking.sh` and `bash tests/test_draft_finalize.sh` —
   the two existing suites that read `aitask_ls.sh` output and `--type`
   respectively, both must pass unchanged.
10. `/aitask-pick` shows the kind in its Step 2c options — verify by reading the
    regenerated `fast` golden's Step 2b/2c block (the rendered prose *is* the
    deliverable for this surface; there is no executable path to assert).
11. `./.aitask-scripts/aitask_skill_verify.sh` — clean.
12. `shellcheck .aitask-scripts/aitask_ls.sh .aitask-scripts/lib/task_utils.sh
    .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_update.sh
    .aitask-scripts/aitask_stats_legacy.sh`
13. `bash tests/run_all_python_tests.sh` — read the **last** line for the
    verdict (`set -o pipefail` if piping).

Post-implementation cleanup, archival and merge are handled by task-workflow
**Step 9 (Post-Implementation)**.

---

## Risk

### Code-health risk: medium

- The `-v` display line changes shape for **every** task (`Type:` is
  unconditional), and it is a user-facing surface read by `/aitask-pick`,
  `ait create`'s and `ait update`'s fzf pickers, and humans. The two code
  consumers were verified to extract only `^t[0-9]+`, so the risk is
  presentational rather than a parse break · severity: low (residual —
  addressed by inline pre-phase `negctrl_display_line`) · → mitigation: inline
  pre-phase negctrl_display_line
- `get_valid_task_types` is folded onto a new shared reader in **three** scripts,
  two of which (`aitask_create.sh`, `aitask_update.sh`) are the framework's
  load-bearing write paths. The bodies are behaviourally identical, but a
  regression here would surface as a wrongly-accepted or wrongly-rejected
  `--type` on task creation · severity: medium (residual — addressed by inline
  post-phase `pin_task_type_validation`) · → mitigation: inline post-phase
  pin_task_type_validation
- `aitask_ls.sh` gains its first `die` on a bad flag *value*, alongside the
  existing `show_help; exit 1` for a bad flag *name* — two error shapes in one
  arg parser · severity: low · → mitigation: none (both are correct for their
  case and pinned by verification step 6)

### Goal-achievement risk: low

- The `/aitask-pick` half of the deliverable is agent-read prose, so "the human
  choosing work can see the kind" is verifiable only by inspecting the rendered
  golden, never by executing the skill · severity: low · → mitigation: none
  (verification step 10 pins the rendered text, which is the actual artifact)
- Everything else is a closed, mechanically checkable change with the design
  questions already settled with the user · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: negctrl_display_line | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: the -v display line changing shape for every task | desc: write the display-line assertions in final form and confirm RED against unmodified aitask_ls.sh before any edit
- timing: post-phase | name: pin_task_type_validation | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: regression in aitask_create.sh / aitask_update.sh from the get_valid_task_types delegation | desc: pin --type acceptance/rejection and the empty-file fallback through the real entry points, baselined before the delegation and re-run after

---

## Post-Review Changes

### Change Request 1 (2026-08-11 23:35)

- **Requested by user:** Step 7.1's `-v` output-format code block presented
  `Follow-up: <followup_kind>` as an unconditional field, while the prose right
  below it and the Step 2b template both make it conditional. An agent reading
  the code block as the schema could expect the field on every line, or emit a
  placeholder for a genuine-new-work task.
- **Verification:** Confirmed. The block listed one shape only, and it was the
  *rare* one — on the live corpus 257 of 261 Ready parents carry no kind, so the
  documented schema was wrong for 98% of lines. The Step 2b template already
  said "(omit this line entirely if the task is not a follow-up)", so the two
  halves of the same skill disagreed.
- **Changes made:** The block now shows **both** shapes explicitly — genuine new
  work first (labelled the common case), then the follow-up form that appends
  one further segment. The prose was tightened to say `Type:` is always present
  and that the `, Follow-up: <followup_kind>` segment never appears as an empty
  or placeholder value, so its *absence* is the signal. Both rendered shapes were
  then checked byte-for-byte against real `ait ls -v` output.
- **Files affected:** `.claude/skills/aitask-pick/SKILL.md.j2`,
  `tests/golden/skills/aitask-pick/SKILL-{default,fast,remote}-claude.md`
  (rerendered + regoldened; `test_skill_render_aitask_pick.sh` 97/97,
  `aitask_skill_verify.sh` clean).
- **Disposition note:** raised as "follow-up", fixed inline instead — this block
  *is* this child's deliverable for the pick surface, and correcting it cost one
  edit plus a regolden that the change already required.

## Final Implementation Notes

- **Actual work done:** All nine implementation steps landed as planned.
  `lib/task_utils.sh` gained `read_valid_task_types`; the three
  `get_valid_task_types` copies (`aitask_create.sh`, `aitask_update.sh`,
  `aitask_stats_legacy.sh`) now delegate to it. `aitask_ls.sh` parses
  `followup_kind`, always displays `Type:` and conditionally `Follow-up:`, and
  gained `--type` / `--followup-kind` / `--no-followup-kind` with fail-closed
  value validation. `aitask-pick/SKILL.md.j2` carries the kind at all three
  sites; three profiles rerendered and three goldens regenerated. Website
  `ait ls` docs updated. New `tests/test_ls_display_and_filters.sh` — 61
  assertions, all passing.

- **Deviations from plan:** Three, all small.
  1. `read_valid_task_types` is called with an **explicit** `"$TASK_TYPES_FILE"`
     argument at all four wrapper/validation sites rather than relying on the
     function's default-arg fallback. The fallback is retained, but the implicit
     form made shellcheck report `TASK_TYPES_FILE appears unused` (SC2034) in
     `aitask_ls.sh` and `aitask_stats_legacy.sh` — a false positive, since the
     variable is consumed indirectly. Passing it explicitly removes the warning
     without a suppression directive and makes the dependency visible at the
     call site.
  2. The plan's verification step 5 fixture list omitted
     `aitasks/metadata/task_types.txt`. Without it `--type` validates against the
     empty-file fallback (`bug/feature/refactor`) and correctly rejects the
     fixture's `chore` / `test` / `enhancement` tasks. The fixture now writes the
     real vocabulary.
  3. Two extra assertions were added to verification step 6 pinning that the
     rejection messages name an invalid **value** (`Invalid follow-up kind:
     bogus`, `Invalid type: bogus`) — the distinction from the "cannot resolve"
     message was otherwise only asserted on the fail-closed path.

- **Issues encountered:**
  - The test's `run_ls_rc` helper originally set `RC` and returned output on
    stdout. Called inside a command substitution it ran in a subshell, so the
    exit-code assignment died there and **every** rejection assertion silently
    saw `rc=0`. Rewritten to publish `LS_OUT` / `LS_RC` as globals and never be
    called in a substitution; a comment records why.
  - The first baseline-capture attempt ran `git show` from the scratchpad
    directory (not a repo), so every baseline file came out empty and the
    shellcheck diff showed a bogus uniform `SC2148 no shebang` delta. Redone
    from the repo root with an explicit failure echo.
  - `--batch` requires `--desc`; the post-phase pin's `aitask_create.sh`
    invocations initially omitted it and failed for a fixture reason rather than
    a behavioural one.

- **Key decisions:** Kept every design decision D1–D5 as written. In particular
  `Type:` stays unconditional and `Follow-up:` conditional, the raw canonical
  token is printed (not t1468_3's human label), and neither field became a sort
  dimension.

- **Verification evidence:**
  - **Pre-phase `negctrl_display_line`:** the display-line assertions were
    written in final form and run against unmodified `aitask_ls.sh` → **RED**,
    45/59 failing, e.g. `FAIL: t11 full display line (field order pinned)
    (expected 't11_mitigation.md [Status: Ready, Priority: Medium, Effort:
    Medium, Type: feature, Follow-up: risk_mitigation]', got 't11_mitigation.md
    [Status: Ready, Priority: Medium, Effort: Medium]')`. Re-run after the
    fixture was finalised, against a pristine copy of `HEAD`'s `aitask_ls.sh`:
    **37 failures**, including all five pinned display-line assertions, with the
    assertions byte-unchanged. The same file passes 61/61 against the
    implementation.
  - **Post-phase `pin_task_type_validation`:** six `aitask_create.sh --type`
    probes (valid / bogus / `manual_verification` / empty-vocabulary fallback)
    driven through the real CLI against a pre-delegation copy of
    `aitask_create.sh` and against the delegated one — **byte-identical** exit
    codes and `Invalid type:` messages.
  - Real-repo partition check: 261 Ready parents = 257 `--no-followup-kind` + 4
    across all eight kinds (1 `risk_mitigation`, 3 `upstream_defect`) — the
    filters partition the corpus exactly.
  - `shellcheck` diffed against `HEAD` per file: the only deltas are one new
    informational `SC1091` (the added `source` line, same class as the two
    existing ones) and the **removal** of `issue_type_text appears unused` —
    the dead metadata this child was meant to revive. No new warnings.
  - `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED (runner=pytest,
    exit=0)`.
  - `./.aitask-scripts/aitask_skill_verify.sh` → OK (13 templates, 3 agents,
    4 stub surfaces; wrapper parity clean).
  - `bash tests/test_skill_render_aitask_pick.sh` → 97/97.
  - All 50 bash tests referencing `get_valid_task_types` / `validate_task_type` /
    `task_types.txt` / `aitask_ls.sh` were run: 49 pass.
    `tests/test_boardcol_update.sh` fails, but **identically at clean `HEAD`** in
    a throwaway worktree (same rc, byte-identical output) — pre-existing, not
    caused by this change.
  - Verification step 10 (`/aitask-pick` shows the kind): confirmed by reading
    the regenerated goldens — the diff is identical in all three profiles, as
    predicted, since the three edited sites sit outside every `{% if %}` gate.

- **Upstream defects identified:**
  - `tests/test_boardcol_update.sh:81-83 — scaffold copy list omits
    record_protocol.py, so every --boardcol validation fails inside the
    scaffold`. The scaffold copies only `board_columns board_ordering
    config_utils task_yaml`, but `.aitask-scripts/lib/board_columns.py:73` does
    `from record_protocol import (...)`. Importing `board_columns` in the
    scaffold therefore raises `ModuleNotFoundError: No module named
    'record_protocol'`, and `aitask_update.sh --boardcol c1` dies with
    `Error: board column 'c1': could not read the configured column list.` The
    test masks the cause by redirecting the call's output to `/dev/null 2>&1`,
    so under `set -e` the file aborts after printing only its first test header
    and exits 1 with no diagnostic. Reproduced on a clean `HEAD` worktree
    (identical rc and byte-identical output), so it is entirely independent of
    t1468_4. Same class as the general "a selectively-copied build keeps users
    of excluded definitions" hazard.

- **Notes for sibling tasks:** see the section below.

## Notes for sibling tasks

- **`aitask-pick` has no force-tracked rendered variants.** `.gitignore:60-68`
  un-ignores only `aitask-pickrem`, `aitask-pickweb` and `task-workflow`. A
  `.j2` edit here stages the template plus
  `tests/golden/skills/aitask-pick/SKILL-{default,fast,remote}-claude.md` and
  nothing else. Do not copy the "three remote copies are force-tracked"
  sentence from the t1468_4 task file — it is wrong for this skill.
- This child adds the first real test coverage for `aitask_ls.sh`'s display line
  and for **all** its filters (`-l`, `--type`, `--followup-kind`,
  `--no-followup-kind`). t1468_6 can lean on it to verify backfilled tasks
  appear correctly — `ait ls --followup-kind <kind>` hit counts are a direct
  check on a backfill run.
- `lib/task_utils.sh::read_valid_task_types` is now the shell-side reader for
  the issue-type vocabulary. Any new shell surface needing the list should call
  it rather than adding a fourth copy of the `bug/feature/refactor` fallback.
  Full de-duplication across the 32+ sites remains **t720**.
- The `ait ls` filters treat an **absent** `followup_kind` as "not a follow-up"
  (t1468_1's no-tombstone contract) — `--no-followup-kind` is the flag for that,
  and no code path compares against `None`.
