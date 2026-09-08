---
Task: t1732_vocabulary_scan_misses_archive_writer.md
Base branch: main
Output branch: main
---

# t1732 — Register `archived_reason` with the vocabulary scanner

## Context

`bash tests/test_docs_vocabulary_coverage.sh` fails on the live repo:

```
FAIL E/corpus: task files carry frontmatter keys no known writer emits:
      ['archived_reason'] (hand-edited, or a retired field)
```

`archived_reason` is a real, legitimately-written field. `.aitask-scripts/aitask_archive.sh:172`
emits it in the `--superseded` flow:

```bash
awk '/^status:/{print; print "archived_reason: superseded"; next}1' "$file_path" ...
```

The scanner (`tests/lib/docs_vocabulary_scan.py`) derives its writer set from
`ECHO_WRITERS` (`aitask_update.sh`, `aitask_create.sh`) plus an `OTHER_WRITERS`
registry plus the `frontmatter_patch.py` callers. `archived_reason` is in none
of them, so `check_corpus_supplemental` reports every task file carrying it as
an unknown key.

The gap has been latent since t400. `E/corpus` compares the **live** corpus
against the derived writer set, so it stayed green while no task file carried
the field. `aitasks/archived/t1730_*.md` (archived with `--superseded` on
2026-09-07 18:20) is the first and currently only instance on disk.

Intended outcome: the suite passes on the live repo, `archived_reason` is a
first-class documented field, and the E/corpus diagnostic still fires for a
genuinely unknown key.

## Decision: register the field (task's option 2), not extend `ECHO_WRITERS`

`OTHER_WRITERS` already exists for exactly this case — its comment reads
*"Writers that do not use the `echo "<field>: "` shape"* — and it already holds
`completed_at`, written by **the same script**, in **the same `awk` insertion
shape**, at `aitask_archive.sh:167`, one line above the `archived_reason` write.
`archived_reason` is `completed_at`'s exact structural twin.

Option 1 (add `aitask_archive.sh` to `ECHO_WRITERS` and teach the extractor the
`awk` shape) is worse on two counts:

- `ECHO_WRITERS` membership carries an assertion — `writer_fields()` fails with
  `D/writers: <file> emitted no field names -- the writer shape changed` when a
  listed file yields zero `echo "<field>: ` matches. `aitask_archive.sh` yields
  zero, so adding it fails the suite until the extractor is generalized.
- Generalizing the `echo`-shape regex to also match `awk`-embedded `print`
  statements would make the *derivation* looser for every writer, to discover
  one field — where an explicit registry entry names the field, names its writer,
  and asserts the writer still writes it.

## Sweep: is `archived_reason` the only gap?

The task asks to sweep for other fields written outside `ECHO_WRITERS`. Done,
along four axes — **one gap found, no others**:

| axis | command shape | result |
|---|---|---|
| `echo "<field>: "` outside the two `ECHO_WRITERS` | grep `.aitask-scripts/**.{sh,py}` | only non-task files: `aitask_pr_import.sh` (PR data file in `PR_DATA_DIR`), `aitask_contribute.sh` (contribution fingerprint), `aitask_plan_externalize.sh` (**plan** frontmatter `plan_verified`), `aitask_skillrun.sh` (help text) |
| `awk`/`printf` inserting a frontmatter key line | grep `print "<key>: ` / `printf '<key>: ` | exactly two task-frontmatter sites, both in `aitask_archive.sh`: `completed_at` (registered) and `archived_reason` (**the gap**) |
| `sed` inserting a *new* key | grep `a\`/`i\`/`\n<key>: ` | none |
| Python direct frontmatter writers | grep `metadata["<key>"] =` etc. across `.aitask-scripts/` | `assigned_to`, `boardcol`, `boardidx`, `depends`, `status`, `updated_at`, `verifies` — **all already emitted by `aitask_update.sh`**. `merged_from` (`diffviewer/merge_screen.py`) is *plan* frontmatter; `components` / `usergroups_degraded` (`chat/`) are chat-message metadata, not task frontmatter |

Verified mechanically: `writer_fields()` currently returns 40 fields with zero
failures, and `archived_reason` is the only key on disk missing from it.

## Implementation

### 1. `tests/lib/docs_vocabulary_scan.py` — register the field

Change `OTHER_WRITERS` (line ~176) from `{field: path}` to
`{field: (path, needle)}` and add the entry:

```python
# Writers that do not use the `echo "<field>: "` shape. Each value is
# (path, needle): the file, and the fragment that proves it still performs
# the write. The needle is the *write expression*, not the bare field name --
# `archived_reason` also appears in aitask_archive.sh's --superseded help
# line, so a field-name substring would keep this guard green after the awk
# insertion was deleted. Same reasoning as the anchor tripwire in
# check_sites(): a write that moves or is reshaped must fail loudly here
# rather than silently stop being checked.
OTHER_WRITERS = {
    "completed_at": (".aitask-scripts/aitask_archive.sh",
                     'print "completed_at: '),
    # `ait archive --superseded`. Same script, same awk-insertion shape as
    # completed_at, one line below it -- registered here rather than adding
    # aitask_archive.sh to ECHO_WRITERS, which asserts an `echo "<field>: `
    # emission this script does not have.
    "archived_reason": (".aitask-scripts/aitask_archive.sh",
                        'print "archived_reason: '),
}
```

Two call sites follow:

- `writer_fields()` (line ~368): unpack the tuple and check the needle —
  `for field, (rel, needle) in OTHER_WRITERS.items():` … `if needle not in read(root, rel):`
  keeping the existing `D/writers: %s no longer writes %s` message.
- `main()` `--list-inputs` (line ~475): `inputs |= {rel for rel, _needle in OTHER_WRITERS.values()}`.
  (No new fixture input — `aitask_archive.sh` is already listed for `completed_at`.)

### 2. `website/content/docs/development/task-format.md` — add the table row

`check_field_coverage` requires a row for every writer-derived field, so this is
mandatory once step 1 lands. Insert directly after the `completed_at` row
(line 46), matching its placement and phrasing register:

```
| `archived_reason` | `superseded` | Why the task was archived for a reason other than completion. Written only by `ait archive --superseded`; absent ⇒ archived as completed. Distinct from folding — a folded task is **merged** into its primary (see [Folded tasks]({{< relref "/docs/concepts/folded-tasks" >}})), not superseded |
```

The final clause is deliberate: `website/content/docs/concepts/folded-tasks.md:15`
holds the project's "merged, never superseded/replaced" rule for *folding*, and
a bare `superseded` value in the field table sitting next to it would read as a
contradiction. Naming the distinction once keeps both correct.

No other documentation surface needs updating. `completed_at` — the same
archival-only class of field — appears in **neither** `CLAUDE.md`, the
`seed/aitasks_agent_instructions.seed.md` "Task File Format" block (nor its
`AGENTS.md` / `.codex` / `.opencode` mirrors), **nor** `aitask_merge.py`'s
`merge_frontmatter()`. `archived_reason` is written once, at archive time,
immediately before the file is moved to `aitasks/archived/`, so it has no
concurrent-edit exposure and needs no merge rule. `aidocs/issue_type_vocabulary_duplication.md`
explicitly defers the field-table dimension to the scanner's own header
(line 32), so it needs no edit either.

### 3. `tests/test_docs_vocabulary_coverage.sh` — two new controls

Existing Test 12 (`mystery_key` → `E/corpus`) already supplies the negative
control the task's verification section asks for, and is unaffected by this
change. Two things the fix newly asserts are **not** yet covered:

**Test 12b — positive control: a registered `archived_reason` does not trip E/corpus.**
Today only the live corpus proves this, incidentally, via one file
(`aitasks/archived/t1730_*.md`) that will vanish into an `old.tar.zst` bundle.
Add a deterministic fixture-based control that seeds an archived task file and
asserts the scan **passes** — the mirror of Test 12 on the same axis:

```bash
mutate_corpus_archived_reason() {
    mkdir -p "$1/aitasks/archived"
    cat > "$1/aitasks/archived/t2_superseded.md" <<'EOF'
---
priority: low
effort: low
issue_type: chore
status: Done
archived_reason: superseded
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
completed_at: 2026-01-01 00:00
---

Superseded sample task.
EOF
}
```

Needs a small `assert_positive_control` helper (mutate a fresh fixture, assert
the scan still **passes**, and print the scan output on failure) — `assert_control`
asserts the opposite. Also exercises the `aitasks/archived/` arm of the
`check_corpus_supplemental` walk, which no fixture currently reaches.

**Test 12c — negative control: deleting the awk write is caught.**
This is what makes the needle in step 1 a real guard rather than an assertion
about itself. Delete the `archived_reason` awk line from the fixture's
`aitask_archive.sh` (leaving the `--superseded` help line, which is the case a
field-name substring would miss) and assert `D/writers` fires:

Both facts 12c depends on must be **recorded assertions that can fail the
suite**, not a `|| echo` warning: `echo` exits 0, so a violated precondition
would print and the control would still report green while no longer proving
anything (raised in Step-8 review, confirmed empirically — see Final
Implementation Notes).

```bash
mutate_archive_writer_dropped() {
    local f="$1/.aitask-scripts/aitask_archive.sh"
    grep -v 'print "archived_reason: ' "$f" > "$f.tmp"
    mv "$f.tmp" "$f"
    # (a) the mutation landed
    assert_not_contains "12c precondition: the awk write is gone" \
        "archived_reason" "$(grep -F 'print "archived_reason: ' "$f" || true)"
    # (b) the INTENDED non-write occurrence survived — checked explicitly on
    #     the `--superseded` help line, not as "any occurrence anywhere". That
    #     line is what a bare field-name needle would match and is the sole
    #     reason this control discriminates; if a later archive-script refactor
    #     drops it, 12c degrades to "the field vanished entirely" (which any
    #     needle catches) and must fail loudly.
    assert_contains "12c precondition: the --superseded help line survives" \
        "archived_reason" "$(grep -- '--superseded' "$f" || true)"
}
test_control_archive_writer_dropped() {
    echo "=== Test 12c: control — dropping the archived_reason write is caught ==="
    assert_control "dropped archived_reason writer" "D/writers" \
        mutate_archive_writer_dropped
}
```

`assert_contains` / `assert_not_contains` both return 0 (they record via
`assert_record_fail`), so neither trips the file's `set -e`; the recorded FAIL
reaches the footer's `[[ "$FAIL" -eq 0 ]] || exit 1`.

Register all three new functions in the test-runner call list at the file
footer (after `test_control_corpus_unknown_key`), and update the header comment
block and the numbered `===` echo labels to stay consistent.

## Verification

1. **The defect is fixed on the live repo** (the task's primary criterion):
   ```bash
   bash tests/test_docs_vocabulary_coverage.sh
   ```
   Expect `Results: 28/28 passed, 0 failed` (25 today − 2 currently failing
   + 3 new assertions), with Test 1 green and the scan line reading
   `OK <N> issue_type sites, 41 writable fields` (40 → 41).

2. **The diagnostic is not silenced wholesale** — Test 12 (`mystery_key`) must
   still fail the scan and name `E/corpus`. Confirm it is reported as passing,
   i.e. the mutation still flips the scan to FAIL.

3. **The new controls actually discriminate** — deliberately break each and
   confirm it goes red, then revert:
   - revert the `OTHER_WRITERS` entry → Test 1 and Test 12b must fail;
   - loosen the needle back to the bare field name `archived_reason` → Test 12c
     must fail (the help line alone keeps the guard green).

4. **Scanner and test file parse** — covered by existing Test 13, plus:
   ```bash
   python3 tests/lib/docs_vocabulary_scan.py --root . --list-inputs | grep aitask_archive
   ```
   must still print `.aitask-scripts/aitask_archive.sh` exactly once (the
   tuple refactor must not drop or duplicate it).

5. **Website link check** (mandatory per CLAUDE.md after editing anything under
   `website/content/`) — the new row carries a `{{< relref >}}`:
   ```bash
   cd website && python3 check_links.py --build
   ```

6. **Shellcheck** the edited test script:
   ```bash
   shellcheck tests/test_docs_vocabulary_coverage.sh
   ```

Step 9 (Post-Implementation) handles commit, cleanup, and archival.

## Risk

### Code-health risk: low
- Tightening `OTHER_WRITERS` to a write-expression needle makes the guard
  sensitive to reformatting of the two `awk` lines in `aitask_archive.sh`: a
  future refactor of those lines turns the suite red on an edit that is not
  itself a defect · severity: low · → mitigation: inline — the failure message
  `D/writers: <file> no longer writes <field>` already names both file and
  field, and Test 12c pins the behavior so the tripwire is documented rather
  than surprising. This is the same deliberate loud-failure tradeoff the
  scanner already makes with its `check_sites()` anchor tripwire.
- Blast radius is three files, all test/documentation infrastructure. No
  framework runtime path changes; `aitask_archive.sh` itself is not modified.

### Goal-achievement risk: low
- None identified. The defect is reproduced, its cause is located to one line,
  the fix is validated by an existing failing test flipping green, the "which
  option" decision is grounded in an in-file precedent (`completed_at`), and
  the requested sweep is discharged with mechanical evidence across four axes.

## Final Implementation Notes

- **Actual work done:** Implemented as planned across the three named files.
  `OTHER_WRITERS` in `tests/lib/docs_vocabulary_scan.py` gained
  `archived_reason` and changed shape from `{field: path}` to
  `{field: (path, needle)}`; its two call sites (`writer_fields()`,
  `main()` `--list-inputs`) were updated. `website/content/docs/development/task-format.md`
  gained the `archived_reason` row after `completed_at`.
  `tests/test_docs_vocabulary_coverage.sh` gained an `assert_positive_control`
  helper, Test 12b (positive control) and Test 12c (negative control). Suite
  went from 23/25 to **30/30**; the scanner's writable-field count went 40 → 41.

- **Deviations from plan:** One, added during Step-8 review. Test 12c's mutator
  originally guarded its surviving-occurrence precondition with
  `grep -q 'archived_reason' "$f" || echo "FIXTURE BUG: ..."`. Because `echo`
  exits 0, a violated precondition would only print — the control would still
  report green while no longer proving that a bare field-name needle is
  inadequate. Replaced with two recorded assertions
  (`assert_not_contains` that the write is gone, `assert_contains` that the
  `--superseded` help line survives), which pushes the suite to 30 assertions.

- **Issues encountered:** None in the fix itself. Two verification mechanics
  were worth solving properly rather than shortcutting:
  - Every mutation-discrimination check was run against **scratch copies**
    (a mutated scanner, and a scratch project root built from symlinks to the
    real repo with a real `tests/` dir), so the shared, concurrently-edited
    working tree was never left in a mutated state. `make_fixture` uses `cp`,
    which follows symlinks, so the symlinked root builds identical fixtures.
    One artifact: Test 13 hard-codes `test_docs_vocabulary_coverage.sh`, so a
    mutant must keep that filename or Test 13 alone fails.
  - `origin/main` was ahead by 2 commits touching `aitask_archive.sh` — a real
    file-level overlap with this plan. Verified inert at line level: the change
    is t1729's one-line `mktemp` → `mktemp_suffixed` swap, and the two `awk`
    write lines this scanner reads are byte-identical on both sides. `main` also
    advanced twice mid-session; the suite was re-run green against the new HEAD
    and none of the new commits touch this task's inputs.

- **Key decisions:**
  - **Registered the field (task's option 2) rather than extending `ECHO_WRITERS`
    (option 1).** Rationale is in the code comment: `ECHO_WRITERS` membership
    *asserts* an `echo "<field>: ` emission that `aitask_archive.sh` does not
    have, and widening the echo regex to match awk-embedded `print` would loosen
    the derivation for every writer in order to discover one field.
  - **Pinned the write expression, not the field name.** `archived_reason` also
    appears in the `--superseded` help line, so a field-name substring would
    keep `D/writers` green after the awk insertion was deleted. Measured: under
    a loose needle, Test 12c's mutation passes cleanly; under the tightened one
    it fails with `D/writers`. The cost is a deliberate tripwire — reformatting
    those two `awk` lines now fails loudly, matching the scanner's existing
    `check_sites()` anchor-tripwire philosophy.
  - **No other documentation surface updated.** `completed_at`, the same
    archival-only class of field, appears in none of `CLAUDE.md`, the
    `seed/aitasks_agent_instructions.seed.md` "Task File Format" block (or its
    `AGENTS.md` / `.codex` / `.opencode` mirrors), or `aitask_merge.py`'s
    `merge_frontmatter()`. `archived_reason` is written once at archive time,
    immediately before the file moves to `aitasks/archived/`, so it has no
    concurrent-edit exposure and needs no merge rule.
  - **Every new check was proven able to fail.** Forced-failure runs confirmed:
    dropping the registration fails both the live scan and Test 12b's fixture;
    a loose needle makes Test 12c vacuous; and each of 12c's two new
    preconditions fails the suite when violated. The pre-review `|| echo` form
    was demonstrated to report `28/28 passed, 0 failed` on the very mutant that
    invalidates the control.

- **Upstream defects identified:** None.
