---
Task: t2214_fix_yaml_word_labels_and_gitbranch_sed_arglist.md
Base branch: main
Output branch: main
---

# t2214 — YAML-word labels + gitbranch "Argument list too long"

## Context

Two upstream defects found during t2209's review:

1. **Labels that YAML reads as non-strings.** `sanitize_label`
   (`.aitask-scripts/lib/task_utils.sh:2571`) lets through any `[a-z0-9_-]` token,
   and `format_yaml_list` writes labels unquoted. So `on`, `null`, `yes`, `010`,
   `2026-11-05` and `0x1f` reach the frontmatter, and every Python reader (board,
   `task_yaml`) gets `True` / `None` / `8` / a `date` / `31` back instead of the
   string.
2. **gitbranch `sed: Argument list too long`** (`lib/artifact_backends/gitbranch.sh:524`).
   **The task's own diagnosis ("argv") is wrong — measured here:** sed's argv is
   tiny. The failure happens when the **caller's environment exports a variable
   named `out`**. A bash `local out` inherits that export flag, so the store
   listing (~180 KB for 2,501 blobs) ends up in every child's **environment**,
   above the kernel's 128 KiB per-string limit. Reproduced: a plain
   `bash tests/test_artifact_gitbranch_backend.sh` gives 294/294;
   `env out=x bash tests/…` gives 290/294, failing exactly the four "large store"
   asserts that t2209 reported, with the same line-524 message. (t2209's sweep
   harness evidently had `out` exported.) The same exposure applies to every other
   local holding a store-sized value whose name a caller could have exported.

Fixes: labels → reject YAML non-string words in `sanitize_label` (the
controlled-vocabulary option; every caller already treats an empty result as
"dropped/invalid"). gitbranch → keep store-sized data out of exportable
variables.

## Measurement (label rule)

I checked every string of length 1–3 over `019ab_-xeonyftlu7`, plus a list of
known YAML words (5,232 strings in all), against both `yaml.SafeLoader` and
`task_yaml._TaskSafeLoader` by loading `[s]`. 161 strings do not read back as
`[s]`. The candidate rule below lets **none** of those 161 through, and
over-rejects exactly 25 strings that PyYAML does read as strings:
`-09 -0b -0x 009 019 079 08 09 090 091 097 099 09_ 0_9 0b 0b7 0b9 0ba 0bb 0be 0bf 0x 2026-1-5 n y`.
(`y`/`n` are YAML 1.1 bools in the spec, though PyYAML does not resolve them.
Rejecting them is deliberate and conservative.) Floats, `.inf`/`.nan`,
sexagesimals and timestamps with a time part all need `.` or `:`, which the label
charset cannot contain.

Rule (it applies to the *sanitized* token, which is ASCII `[a-z0-9_-]`):
- word ∈ {y, n, yes, no, true, false, on, off, null}
- `^[-+]?[0-9][0-9_]*$` (decimal / octal / `1_000`)
- `^[-+]?0[bx][0-9a-f_]*$` (binary / hex)
- `^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}$` (date)

## Implementation

### A. Labels (`.aitask-scripts/lib/task_utils.sh`)

1. Add `_label_reads_as_string <label>` right above `sanitize_label`. It is pure
   bash (`case` + `[[ =~ ]]`, no forks) and implements the rule above. The comment
   records the measurement and names the test that pins it.
2. `sanitize_label`: capture the existing pipeline into `clean`, then
   `_label_reads_as_string "$clean" || clean=""`, then `printf '%s' "$clean"`.
   Update its header comment: a YAML non-string word sanitizes to "" (rejected),
   because the labels writer (`format_yaml_list`) stays unquoted on purpose, since
   it also writes id/gate lists.
3. **Every route that reaches a frontmatter writer.** I traced each one (the
   sanitizer alone does not cover them all):
   - *Batch create/update* (`--labels`, `--add-label`) → `normalize_labels_csv` /
     `sanitize_label` → already reports `DROPPED:` / "dropped invalid label".
     Imports (`github_map_labels`, inline sed) feed `aitask_create.sh --batch
     --labels`, so they are covered here too. `aitask_labels.sh` prints
     `INVALID:`. No change.
   - **Interactive create, `get_labels_interactive` (`aitask_create.sh:1386`) —
     gap, fix it.** Two of its routes skip `sanitize_label`: the
     "Use labels from previous task" entry (`get_last_used_labels` from
     `userconfig.yaml`, split straight into `selected_labels`, line ~1451) and the
     existing-vocabulary pick (`label="$selected"`, a legacy `labels.txt` may hold
     `on`). Both flow into `SELECTED_LABELS` → `set_last_used_labels` and
     `create_draft_file`'s unquoted `format_yaml_list` (lines 2650–2652). Fix:
     where the function builds `SELECTED_LABELS`, pass the joined CSV through
     `normalize_labels_csv` (two-call stdout/stderr split, the same idiom as the
     batch path at `aitask_create.sh:2274`) and `warn "dropped invalid label(s):
     …"` when the drop line is set. That one choke point covers every route in
     the picker (previous labels, vocabulary, new label). Because the caller saves
     the normalized value, `last_used_labels` also stops re-offering the bad word.
   - *Interactive update* (`interactive_update_labels`) → its consumer at
     `aitask_update.sh:~1765` already runs `add_labels_csv_to_file` and uses
     `AIT_LABELS_NORMALIZED`, so it is covered. It drops tokens silently, so add a
     `warn` when `AIT_LABELS_DROPPED` is non-empty.
   - The two "Add new label" prompts (`aitask_create.sh:~1466`,
     `aitask_update.sh:~1542`) currently ignore an empty sanitize result without a
     word. Add `warn "'<input>' is not a valid label"` so that typing `on` does not
     look accepted.
   - *Not changed, deliberately:* batch `aitask_update.sh` re-writes a task's
     **pre-existing** labels (`CURRENT_LABELS`) as they are. A legacy `labels:
     [on]` already on disk is existing data, and this fix creates no new route to
     it. Removal paths stay unsanitized, so removing a legacy raw label keeps
     working.
4. Docs: `website/content/docs/commands/task-management.md:21` (the label
   sanitization sentence) gets one clause: words YAML would read as non-strings
   (`yes`, `on`, `null`, `010`, dates) are rejected. Then run
   `python3 check_links.py --build` in `website/`.

### B. gitbranch (`.aitask-scripts/lib/artifact_backends/gitbranch.sh`, `.aitask-scripts/aitask_artifact.sh`)

5. `artifact_gitbranch_list` (line 517): stop holding the listing in `out`. Add
   `_artifact_gitbranch_list_tip <tip>`, a subshell with an `mktemp -d` + EXIT trap
   (`# archive-sweep: subshell-local`, the same shape as
   `_artifact_gitbranch_missing_entries`). It writes `git ls-tree -r --name-only`
   to a file, `|| exit 1`, then runs the existing `sed -n` over the file.
   `artifact_gitbranch_list` keeps probe/check outside and dies with the same
   message on failure. Extend the comment above `_artifact_gitbranch_missing_entries`
   ("never an argument or environment string") with the inherited-export
   mechanism.
6. `_artifact_gitbranch_cas` (line 345): declare `lines` with `local +x` (its
   own `local` line plus a comment). In `migrate` it holds every missing
   `ls-tree` entry, and is then piped into `_artifact_gitbranch_build`, which
   execs git.
7. `aitask_artifact.sh:1244`: `local +x src_list dst_list missing`, same comment.
   These hold full store listings while `_artifact_gitbranch_missing_hashes` execs
   sed/sort/comm.
   (`local +x` was checked: it drops an inherited export for the local only, and
   the caller's exported value is untouched.)

### C. Tests

8. **New `tests/test_label_yaml_words.sh`** (self-contained, `assert_*` from
   `tests/lib/asserts.sh`; it uses the PyYAML probe idiom of
   `tests/test_file_refs_yaml.sh`, with both loaders):
   - *Differential:* Python generates the corpus above. One bash process sources
     `task_utils.sh` and prints `_label_reads_as_string` rejections. Assert that
     there are **zero false accepts** (every string PyYAML misreads is rejected),
     and that the over-rejection set **equals the pinned 25-entry list**, so the
     rule cannot quietly grow or shrink.
   - *Pinned accepts:* `3d`, `2fa`, `0day`, `x-1`, `-x`, `ui`, `y2k` survive
     `sanitize_label`. *Pinned rejects:* `on`, `ON`, `Null`, `yes`, `010`, `0x1f`,
     `2026-11-05`, `-5`, `1_000` sanitize to "".
   - *End-to-end round trip:* in a scratch repo (fixture traced from
     `tests/test_characterize_batch_label_frontmatter.sh` before reuse), run
     `aitask_create.sh --batch --labels "on,ui,010"` and
     `aitask_update.sh --batch --add-label null`. Assert the "dropped" warnings,
     and assert that PyYAML (both loaders) reads `labels:` as exactly `['ui']`,
     all strings. Also assert that `labels.txt` gained none of the rejected words.
   - *Interactive create picker, both saved-label routes.* Load
     `aitask_create.sh`'s functions from a scratch copy with the trailing
     `main "$@"` line removed. This is the technique `tests/test_create_email_lock.sh`
     uses. Run it in a scratch `TASK_DIR`, and mock `fzf` as a function that pops
     scripted answers from a queue file (fzf runs in a pipeline subshell, so the
     state has to live in a file).
     (a) previous-labels route: `userconfig.yaml` has `last_used_labels: ["on", ui]`.
         Pick the previous-labels entry, then Done → `SELECTED_LABELS == ui`, and a
         "dropped invalid label(s): on" warning.
     (b) vocabulary route: `labels.txt` holds `on` and `ui`. Pick `on`, Add
         another, pick `ui`, Done → `SELECTED_LABELS == ui`, plus the warning.
     Control: the same two scripted runs against the **pre-fix** function, in the
     scratch copy with the legacy definition appended ahead of `main`. Those runs
     must yield `on` / `on,ui`, which proves the fixture reaches each route and
     does not just pass vacuously.
9. `tests/test_label_vocabulary_lib.sh` Case 2: add `sanitize_label 'on'` → "",
   and `add_labels_csv_to_file "on,ui"` → `AIT_LABELS_NORMALIZED == ui`,
   `AIT_LABELS_DROPPED == (on)`, `on` not appended to `labels.txt`. This covers the
   function the interactive update route depends on.
10. `tests/test_artifact_gitbranch_backend.sh` §18:
    - Factor the 2,501-blob fixture into `mk_big_store` (no behaviour change).
    - Run the existing two migrate calls inside
      `( export out=x lines=x src_list=x dst_list=x missing=x; art A … )`. Add a
      comment explaining that a caller-exported name is inherited by `local`.
    - **New §18b:** on a fresh big store, `mk_marked_branch A partial-art "$(record_id A)"`
      creates a same-store destination with no blobs, so the migrate takes the
      `missing_entries` → big `lines` path. Migrate under the same hostile env, and
      assert success, no "Argument list too long", and 2,501 blobs on
      `partial-art`.

## Verification

- `bash tests/test_label_yaml_words.sh`, `bash tests/test_label_vocabulary_lib.sh`,
  `bash tests/test_characterize_batch_label_frontmatter.sh`.
- `bash tests/test_artifact_gitbranch_backend.sh`, plus a run with `env out=x …`
  (it was 290/294 before the fix and must be 294+/all after).
- **Mutation controls** (each one alone, reverted afterwards, using a scratch copy
  and never `git restore`):
  - revert step 5 → §18 red with the line-524 message;
  - drop `+x` on `src_list dst_list` → §18 red;
  - drop `+x` on `lines` → §18b red;
  - remove the bool-word `case` from the predicate → the differential is red.
  `missing` is empty except on failure, so it has no separate control (stated as
  residual).
- Run the existing label-consumer tests: `grep -l 'labels' tests/test_*.sh`,
  restricted to the create/update/labels/import scripts, plus
  `bash tests/run_all_python_tests.sh --test-dir` on the chatlink payload-guard
  tests (labels.txt fixed-point property).
- `shellcheck` on the touched `.aitask-scripts/*.sh` files and the gitbranch lib.
- `cd website && python3 check_links.py --build`.

Step 9 (Post-Implementation): commit code with `bug: … (t2214)`, then archive via
the standard workflow.

## Risk

### Code-health risk: low
- A route that bypasses `sanitize_label` would still write a YAML word. Review
  found the interactive-create picker's previous-labels and vocabulary routes.
  They are fixed at the picker's single output choke point, with per-route
  regression tests and pre-fix controls (steps A3 and C8) · severity: low
  (residual) · → mitigation: none (in plan)
- Rejecting digit-only / date-shaped labels is a behaviour change for anyone who
  wanted e.g. a `2026` label. There are none in the live vocabulary or on any
  task (checked), and the over-rejections are pinned by the differential test ·
  severity: low · → mitigation: none
- The gitbranch edits touch the store's list/CAS/migrate path. The change is
  confined to variable export attributes and one file-buffered listing, and is
  covered by §18/§18b and the existing 294 asserts · severity: low · → mitigation: none

### Goal-achievement risk: low
- The task's stated cause (argv) differs from the measured one (inherited export).
  The fix targets the measured mechanism, and the test reproduces the reported
  failure set exactly, so the defect as observed is covered · severity: low · → mitigation: none
