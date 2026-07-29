---
Task: t1321_characterize_batch_label_frontmatter.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1321 — Characterize `--batch --labels` frontmatter output

## Context

t1321 is the confirmed **"before" risk mitigation** for **t1312** (label
auto-add + profile-gated confirmation for `/aitask-explore`). t1312 will make
`aitask_create.sh --batch` normalize the `--labels` CSV (trim, lowercase,
sanitize invalid chars, **dedupe**) before it reaches `format_yaml_list`, and
will start writing new labels into `aitasks/metadata/labels.txt`. Both changes
alter observable output that nothing currently pins.

This task writes the characterization test that pins **today's** behavior, so
t1312's change lands against a known baseline and its diff to this file becomes
the reviewable record of exactly what changed. t1312 is blocked on it.

### Current behavior (verified by reading the source)

- `format_yaml_list()` — `.aitask-scripts/lib/task_utils.sh:414-421` — is a pure
  `s/,/, /g` + bracket wrap on the raw string. Empty input → `[]`. **No split,
  no trim, no case-fold, no sanitize, no dedupe.**
- All three batch creation paths emit `labels:` unconditionally through it:
  - **parent** — `create_task_file` (`aitask_create.sh:1791`), batch call site `:2066`
  - **child** — `create_child_task_file` (`:462`), batch call site `:2035`
  - **draft** — `create_draft_file` (`:580`), batch call site `:2093`
- `add_label_to_file()` (`:1089`) and `sanitize_label()` (`:1069`) exist in
  `aitask_create.sh` but have **no callers** — the only labels.txt append is
  inlined in the *interactive* fzf loop (`:1219-1221`). So no batch path writes
  labels.txt today. The `task_git add "$LABELS_FILE"` calls at `:2048` / `:2080`
  stage an *unchanged* file and are therefore no-ops in the commit.
- `task_git commit` commits **staged paths only** (no `-a`) — which is precisely
  why the fixture baseline below must be clean before the first create runs.

## Plan

### 0. Widen the task's acceptance criteria first

The AC table in `aitasks/t1321_characterize_batch_label_frontmatter.md` lists
four inputs. It omits **deduplication** and **sanitizes-to-empty**, both of
which t1312 explicitly changes — a t1312 implementation could get those wrong
with no before/after record. Update the task file's table to the six-row matrix
in §3 below (and the "When t1312 lands" paragraph's example transformations)
**before** writing the test, so the scope change is explicit rather than silent.

### 1. Fixture

Create **`tests/test_characterize_batch_label_frontmatter.sh`** — a
self-contained bash test in the house style (own `PASS`/`FAIL`/`TOTAL`, own
results summary, `exit 1` on failure).

Copy `setup_project()` from `tests/test_anchor_create.sh:82-118` (bare remote +
clone + `setup_fake_aitask_repo` + `aitask_claim_id.sh --init` +
`task_types.txt` + `.gitignore` for `aitasks/new/`), with **one change** — at
the position of the existing `: > aitasks/metadata/labels.txt` (line 109), i.e.
**above** the `git add -A` / `git commit` pair at 112-113:

```bash
# Discriminating sentinel: none of the labels this test passes appear here, so
# ANY write by the batch path (append + `sort -u`) changes the file.
# MUST stay above the `git add -A` / `git commit` below — see the precondition.
printf 'zzz_sentinel_preexisting\n' > aitasks/metadata/labels.txt
```

Seeding a non-empty file that does not intersect the test inputs is what makes
the "labels.txt untouched" assertion discriminating — an empty file would pass
vacuously for some write shapes.

**Fixture-clean precondition (asserted, not assumed).** Immediately after
`setup_project` returns, and *before* capturing any baseline:

```bash
assert_eq "fixture baseline is committed and clean" "" "$(git status --porcelain)"
```

This is load-bearing, not decoration. `aitask_create.sh` unconditionally runs
`task_git add "$LABELS_FILE"` on the parent and child commit paths. If the
sentinel write were left uncommitted (e.g. a future edit moves it below the
`git add -A`), the *first* `--batch --commit` would sweep labels.txt into its
commit — the §4 commit-content assertion would then fail on a **fixture
artifact** rather than on real behavior, and the child path (whose parent is
created during setup) could absorb the stray file and hide it entirely. The
precondition converts that implicit ordering requirement into a checked one.
`aitask_claim_id.sh --init` writes only to the separate `aitask-ids` branch, so
it leaves the worktree clean.

Only after that precondition passes, capture `labels_cksum` and `head_sha`.

Source `tests/lib/test_scaffold.sh` then `tests/lib/asserts.sh` (`assert_eq`,
`assert_file_exists`). Reuse `test_anchor_create.sh`'s `CLEANUP_DIRS` +
`teardown_all` EXIT trap and its `pushd`/`popd` `teardown()`.

### 2. Local helpers

```bash
labels_line()   { grep -m1 '^labels:' "$1"; }          # exact emitted line
labels_cksum()  { cksum < aitasks/metadata/labels.txt; }
head_files()    { git show --name-only --pretty=format: HEAD | grep -v '^$' | sort | tr '\n' ' '; }
head_subject()  { git log -1 --pretty=format:%s; }
head_sha()      { git rev-parse HEAD; }

# Task id token from a created path: aitasks/t7_p_case1.md -> t7
parent_id_of()  { local b; b=$(basename "$1" .md); printf '%s' "${b%%_*}"; }
# Child id token: aitasks/t7/t7_1_c_case1.md -> t7_1
child_id_of()   { basename "$1" .md | cut -d_ -f1,2; }
```

**The commit-subject check must be `assert_contains`, not `assert_eq`.**
`assert_eq` (`tests/lib/asserts.sh:28-37`) is exact string equality — a prefix
test written with it would fail on every case. And the subject differs by path:
`aitask_create.sh:2084` emits `ait: Add task <id>: <humanized name>` for
parents but `:2052` emits `ait: Add child task <id>: <humanized name>` for
children, so a single shared needle cannot serve both. Each path therefore uses
its own **id-bearing** needle, which pins the exact creation commit without
depending on the `tr '_' ' '` humanization of the task name:

- parent: `assert_contains … "ait: Add task $(parent_id_of "$f"):" "$(head_subject)"`
- child:  `assert_contains … "ait: Add child task $(child_id_of "$f"):" "$(head_subject)"`

These also discriminate against each other: the parent needle `ait: Add task t7:`
is not a substring of `ait: Add child task t7_1: …`.

### 3. The pinned matrix (6 cases × 3 creation paths)

Expected values are the **current** pass-through output — a pure `s/,/, /g` on
the raw CSV. Rows 5-6 are the additions from §0.

| # | input | expected emitted line | why it is pinned |
|---|---|---|---|
| 1 | `--labels "ui,backend"` | `labels: [ui, backend]` | canonical — must NOT change under t1312 |
| 2 | `--labels "ui, backend"` | `labels: [ui,  backend]` | double space preserved (no trim) |
| 3 | `--labels "UI Stuff,foo-bar!"` | `labels: [UI Stuff, foo-bar!]` | verbatim (no case-fold, no sanitize) |
| 4 | `--labels ""` | `labels: []` | empty-input branch of `format_yaml_list` |
| 5 | `--labels "foo,FOO,foo"` | `labels: [foo, FOO, foo]` | **no dedupe today** — exact-dup *and* case-fold-dup both survive |
| 6 | `--labels "!!!"` | `labels: [!!!]` | **sanitizes to empty** under t1312's rule (`tr a-z` + strip `[^a-z0-9_-]` → `""`); today it passes through verbatim |

Row 5 is the dedupe baseline: it carries an exact duplicate (`foo`…`foo`) and a
case-fold-equivalent (`FOO`) in one input, so t1312's diff must show what each
collapses to. Row 6 is the degenerate-sanitize baseline — the case where
t1312's normalizer produces an empty token and has to decide whether the label
is dropped, kept, or yields `labels: []`.

### 4. Test functions

**`test_parent_path`** — fresh fixture + precondition. For each of the six inputs:
```bash
f=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
      --name "p_case$i" --desc x --labels "$input")
```
- `assert_file_exists` on `$f` (guards against a vacuous pass on a failed create)
- `assert_eq` on `labels_line "$f"`
- `assert_contains` `head_subject` ⊇ `ait: Add task <parent_id_of $f>:` (pins
  that we assert on this creation commit, not a stray one)
- `assert_eq` `head_files` == `<task file> ` — **only** the task file;
  `aitasks/metadata/labels.txt` absent
- `assert_eq` `labels_cksum` unchanged vs. the baseline captured after setup

**`test_child_path`** — fresh fixture + precondition. Create one parent
(`--batch --commit --silent --name par --desc x`, `assert_file_exists` on it),
extract its id from the returned path, then for each input create a child with
`--parent <id>`. Five assertions per case, matching the parent path's shape with
**two path-specific substitutions**:
- the subject needle is `ait: Add child task <child_id_of $f>:` (§2) — children
  do **not** emit `ait: Add task`;
- `head_files` is expected to be **child file + parent file**
  (`update_parent_children_to_implement` legitimately rewrites the parent;
  `aitask_create.sh:2047` stages it) — `labels.txt` still absent.

> Deviation note vs. the task's shorthand "the commit contains only the task
> file": that holds exactly for the parent path. For the child path the parent
> file is a legitimate co-committed artifact, so the child assertion pins
> `{child, parent}` and separately asserts `labels.txt` absent. Pinning the
> literal shorthand would have made the child case fail against correct current
> behavior.

**`test_draft_path`** — fresh fixture + precondition. For each input:
```bash
f=$(bash .aitask-scripts/aitask_create.sh --batch --silent --name "d_case$i" --desc x --labels "$input")
```
- draft lands in gitignored `aitasks/new/`; `assert_file_exists` + `assert_eq`
  on `labels_line`
- `assert_eq` `head_sha` unchanged vs. the baseline (the draft path creates
  **no** commit at all)
- `assert_eq` `labels_cksum` unchanged

### 5. Assertion-count tripwire (repeatable wiring guard)

The negative control (§Verification 2) is one-time evidence: it proves the
wiring works on the day it is run, but a later refactor that deletes or
short-circuits assertions would still print a green `0 failed`. Pin the count
in the script itself:

```bash
EXPECTED_ASSERTIONS=88   # 6 cases × (5 parent + 5 child + 4 draft) + 3 preconditions + 1 parent-create
```

After the results summary, outside the `PASS`/`FAIL`/`TOTAL` counters (so it is
not self-referential):

```bash
if [[ "$TOTAL" -ne "$EXPECTED_ASSERTIONS" ]]; then
    echo "FAIL: assertion-count tripwire — ran $TOTAL assertions, expected $EXPECTED_ASSERTIONS"
    echo "      (assertions were added or removed; update EXPECTED_ASSERTIONS deliberately)"
    exit 1
fi
```

Derivation: parent 6×5=30, child 6×5=30 +1 parent-create, draft 6×4=24,
preconditions 3 → 30+30+1+24+3 = **88**. The constant is set to the **observed** `TOTAL` at
implementation time; if it disagrees with this arithmetic, the discrepancy is
investigated before the constant is written (a silent adjustment would defeat
the guard).

### 6. Forward-pointer comment

Head the file with a comment block stating it is a **characterization** test for
t1312, that rows 2/3/5/6 are expected to change, and that those expectations
must be updated **in the same commit** as t1312's normalization — naming the two
side-effect facts (`labels.txt` write, commit contents) that also flip, and the
`EXPECTED_ASSERTIONS` constant that must be re-derived if assertions change.

## Verification

1. **Normal run:** `bash tests/test_characterize_batch_label_frontmatter.sh`
   → **exit 0**, summary line reads `Results: 88/88 passed, 0 failed`, and the
   assertion-count tripwire is silent. All three must hold; exit 0 alone is not
   sufficient evidence (a suite that ran zero assertions also exits 0).
2. **Negative control — one-time implementation validation** (records that the
   assertion wiring discriminates; not a permanent guard, which is §5's job):
   - Flip a frontmatter expectation (`labels: [ui,  backend]` →
     `labels: [ui, backend]`), re-run → expect a `FAIL:` line and **exit 1**;
     restore by reverting that single edit (not `git checkout`).
   - Flip a side-effect expectation (compare `labels_cksum` against a
     deliberately wrong value), re-run → expect `FAIL:` + **exit 1**; restore
     the same way.
   - Both outcomes recorded verbatim in the plan's Final Implementation Notes
     and explicitly labelled one-time implementation validation.
3. **Tripwire self-check:** temporarily set `EXPECTED_ASSERTIONS` to `87`,
   re-run → expect the tripwire `FAIL:` line and exit 1; restore. This proves
   the repeatable guard from §5 actually fires.
4. `shellcheck tests/test_characterize_batch_label_frontmatter.sh` → clean
   (info-level baseline acceptable, matching the rest of `tests/`).
5. The task file's AC table (§0) matches the six-row matrix in §3.

## Risk

### Code-health risk: low

- New, self-contained test file; **no production code is touched**. The only
  non-test edit is the AC-table update to the task's own markdown file. ·
  severity: low · → mitigation: none needed

### Goal-achievement risk: low

- A characterization test can pass **vacuously** — asserting on a file the
  create command never produced, on the wrong commit, or with assertions that
  silently stopped running. · severity: low · → mitigation: covered in-task
  (`assert_file_exists` / `head_subject` guards, the §1 fixture-clean
  precondition, the §5 assertion-count tripwire, and the §Verification 2-3
  negative controls)
- The pinned expectations could be wrong (hand-derived rather than observed). ·
  severity: low · → mitigation: covered in-task (Verification 1 runs the test
  against the real script — a wrong expectation fails immediately)
- The baseline could miss a behavior t1312 changes, leaving that change with no
  review record. · severity: low · → mitigation: covered in-task (§0 widens the
  matrix to dedupe and sanitize-to-empty, the two transformations t1312's plan
  names that the original AC omitted)

No follow-up mitigation tasks are proposed: every identified risk is discharged
by verification steps mandated by this plan, so a separate before/after task
would be redundant.

## Step 9 (Post-Implementation)

Current-branch mode — no worktree/branch cleanup. Gate orchestrator runs the
declared `risk_evaluated` gate, then `aitask_archive.sh 1321`. Archiving t1321
unblocks t1312 (`depends:` edge), which is then re-picked with its plan force
re-verified.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, in plan order.
  1. Widened the AC table in `aitasks/t1321_characterize_batch_label_frontmatter.md`
     from 4 to 6 rows (added the dedupe row `foo,FOO,foo` and the
     sanitizes-to-empty row `!!!`), added a note recording *why* the rows were
     added, and updated the "When t1312 lands" paragraph to name rows 2/3/5/6 and
     their expected transformations. The commit-content sentence was also
     corrected to state the honest per-path expectation (see Deviations).
  2. Wrote `tests/test_characterize_batch_label_frontmatter.sh` — 88 assertions:
     6 inputs × 3 creation paths, plus 3 fixture-clean preconditions and 1
     parent-create assertion.
- **Deviations from plan:** None in substance. One clarification carried from the
  plan into the task file: the task's original shorthand "the task-creation
  commit contains only the task file" is true only for the **parent** path. The
  child commit legitimately also contains the parent file
  (`update_parent_children_to_implement` rewrites it; `aitask_create.sh:2047`
  stages it), and the draft path creates no commit at all. Pinning the literal
  shorthand would have made every child case fail against *correct* current
  behavior, so each path asserts its own exact commit contents and all three
  assert `labels.txt` **absent**.
- **Issues encountered:** Three defects were caught in plan review before any
  code was written, all confirmed against source and fixed in the plan:
  1. `assert_eq` (`tests/lib/asserts.sh:28-37`) is exact equality, so the
     originally planned "subject *starts with* `ait: Add task`" check could not
     be written with it → switched to `assert_contains`.
  2. Children commit `ait: Add child task <id>: …` (`aitask_create.sh:2052`), not
     `ait: Add task …` — a single shared needle would have failed all 6 child
     cases → each path now uses its own **id-bearing** needle
     (`parent_id_of` / `child_id_of`), which also makes the two needles
     mutually discriminating.
  3. The assertion-count derivation was arithmetically wrong (94 vs. the correct
     6×(5+5+4)+3+1 = 88); a correct implementation would have failed its own
     tripwire. Corrected before implementation; the implemented `TOTAL` came out
     at exactly 88, matching the derivation with no adjustment.
- **Key decisions:**
  - **Discriminating sentinel over an empty `labels.txt`.** The fixture seeds
    `zzz_sentinel_preexisting` — a value that intersects none of the test inputs
    — so any append+`sort -u` by the batch path necessarily changes the file. An
    empty file would have passed the "untouched" assertion vacuously.
  - **`assert_clean_baseline()` as a checked precondition.** The sentinel must be
    committed before the first `--batch --commit`, because `aitask_create.sh`
    unconditionally runs `task_git add "$LABELS_FILE"` and `task_git commit`
    commits staged paths only. That ordering requirement was implicit in the
    copied fixture; it is now asserted, so a future edit that moves the write
    below `git add -A` fails loudly instead of corrupting the commit-content
    assertions with a fixture artifact.
  - **Assertion-count tripwire.** The negative control is one-shot evidence; a
    later refactor that deleted assertions would still print a green
    `0 failed`. `EXPECTED_ASSERTIONS=88` is checked outside the PASS/FAIL/TOTAL
    counters (so it is not self-referential) and was validated to fire.
- **Verification evidence (all commands run; results verbatim):**
  1. `bash tests/test_characterize_batch_label_frontmatter.sh` →
     `Results: 88/88 passed, 0 failed`, **exit 0**, tripwire silent.
  2. `shellcheck` → only 2 × SC1091 (info, "not following sourced file"); the
     fixture source `tests/test_anchor_create.sh` emits 3 of the same.
     `shellcheck -S warning` → **exit 0**.
  3. **Negative controls — one-time implementation validation** (each mutation
     reverted by undoing only that edit, not `git checkout`):
     - *Frontmatter arm:* `CASE_OUT[1]` `labels: [ui,  backend]` →
       `labels: [ui, backend]` ⇒ `Results: 85/88 passed, 3 failed`, **exit 1**
       (one failure per creation path — confirms all three paths assert the row).
     - *Side-effect arm:* `base_cksum` forced to `"0 0"` in `test_parent_path`
       ⇒ `Results: 82/88 passed, 6 failed`, **exit 1**.
     - *Tripwire arm:* `EXPECTED_ASSERTIONS=87` ⇒ summary still read
       `88/88 passed, 0 failed` **and** the tripwire fired with **exit 1** —
       demonstrating it catches exactly the case a green summary hides.
     A final post-restore run returned to `88/88 passed, 0 failed`, exit 0.
- **Upstream defects identified:** None.

  (Two dead-code observations were made while tracing the label paths —
  `add_label_to_file()` at `aitask_create.sh:1089` and `sanitize_label()` at
  `:1069` have no callers, the interactive path inlining the append at
  `:1219-1221` instead. These are recorded as context, not as defects: they are
  not broken, and t1312 is already scheduled to rework this exact code into a
  shared lib seam. They are deliberately not routed to a follow-up task.)
