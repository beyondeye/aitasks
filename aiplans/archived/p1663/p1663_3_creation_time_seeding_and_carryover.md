---
Task: t1663_3_creation_time_seeding_and_carryover.md
Parent Task: aitasks/t1663_advisory_task_premise_staleness.md
Sibling Tasks: aitasks/t1663/t1663_4_workflow_check6_premise_procedure.md, aitasks/t1663/t1663_5_website_docs_premise_staleness.md, aitasks/t1663/t1663_6_retrospective_prompt_rate_evaluation.md
Archived Sibling Plans: aiplans/archived/p1663/p1663_1_premise_core_engine_and_producer.md, aiplans/archived/p1663/p1663_2_premise_baseline_field_end_to_end.md
Base branch: main
Output branch: main
---

# t1663_3 — creation-time `premise_baseline` seeding + carry-over inheritance

## Context

t1663_1 shipped the reader (`aitask_premise_stale.sh check`), t1663_2 the field
and its update-path writer. Nothing writes the field organically yet, so every
task reads `SKIP no_stored_baseline`. Per the design record
(`aidocs/framework/task_premise_staleness.md` "Seeding", "Tier B reachability",
"Baseline lifecycle"), creation-time seeding is the only organic coverage path:
a task created with a derivable scope (`--file-ref` = Tier A, `--verifies` =
Tier B) is stamped with HEAD-at-creation; `--followup-of` alone never seeds
(t1673 correction); a carry-over task inherits its origin's value verbatim.

Two decisions taken with the user during planning (both widen the literal task text):
1. **Seed `finalize_draft` too.** The live Tier-A producer (codebrowser's
   create-task action, `codebrowser_app.py:1613`) runs *interactive*
   `aitask_create.sh --file-ref X`, which writes a draft and commits it through
   `finalize_draft()`. Seeding only `--batch --commit` would leave it unseeded.
   Drafts themselves stay unseeded; the stamp is HEAD at finalize (the commit point).
2. **Carry-over inherits through a creation flag** `aitask_create.sh
   --premise-baseline <oid @ ts | "">`. Carry-over passes `--verifies`, which
   would now seed HEAD; an explicit value overrides seeding and lands in the
   creation commit (no interim HEAD-stamped commit, no post-create update whose
   commit-existence check could abort archival on a history-rewritten origin).

Plan review (user, two blocking findings, both reproduced): `read_yaml_field`
keeps a quoted scalar's quotes and returns empty for a block-style list, so
the file-derived reads (finalize scope, carry-over origin value) go through a
YAML-parser-backed helper instead (§1).

HEAD = `git rev-parse --verify --quiet 'HEAD^{commit}'` in the cwd (the repo
root, `ait` cds there) — the same repo the reader resolves
(`aitask_premise_stale.sh:343-345`), i.e. the code checkout, not `.aitask-data`.

## Implementation

### 1. Shared grammar helper — `.aitask-scripts/lib/task_utils.sh`

New pure function next to the other field helpers:

```bash
# premise_baseline_canonical <raw>
# Prints "<lowercase oid> @ <YYYY-MM-DD HH:MM>" and returns 0 when <raw> is a
# full 40/64-hex id followed by " @ YYYY-MM-DD HH:MM" (the stored grammar the
# reader accepts); prints nothing and returns 1 otherwise. Grammar only — no
# repository lookup (an inherited value may name a commit that a history
# rewrite removed; the reader reports that as history_rewritten).
```
Same regexes as `aitask_update.sh:normalize_premise_baseline` (`oid_re`, `ts_re`).
`aitask_update.sh` is NOT rewired onto it (its contract adds the bare-oid stamp
and the commit-existence check; touching it shifts t1663_2's pins for no gain).

**YAML-backed field reader** `read_premise_seed_fields <task_file>` (same file,
modelled on `read_file_references_batch` / `_AIT_FILE_REFS_GLUE`). The two
file-derived inputs of this task — an existing `premise_baseline` and the
scope — are read through the framework's YAML parser, **never** through
`read_yaml_field` (which keeps surrounding quotes, so a valid
`premise_baseline: "<oid> @ <ts>"` would fail the grammar, and which returns
empty for a block-style `verifies:\n  - 1` list). A Python glue
`_AIT_PREMISE_SEED_GLUE` (run `-B`, `sys.path` stripped of `""`/`.`, imports
only `task_yaml`, which `setup_fake_aitask_repo` already copies) parses with
`task_yaml.parse_frontmatter` and prints exactly:

```
BASELINE_ABSENT            key not in the mapping
BASELINE:<str>             key present; YAML-decoded string ("" for null/empty)
BASELINE_INVALID           key present but not a string, or holds CR/LF/NUL
REFS:<n>                   len(task_yaml.file_reference_entries(meta)) — every
                           entry, ok or not (the reader evaluates all of them)
VERIFIES:<n>               verifies: as a list — list/tuple → len, None/"" → 0,
                           other scalar → 1 (the followup_origin._as_list rule)
END:3
```
or the single line `INVALID:frontmatter`. Exit 0 = success; 2 = read/parse
failure or any structural deviation (shell side checks the line order and the
`END:3` count and prints **nothing** on failure — never a partial answer);
3 = no usable Python/PyYAML. Callers capture with `out=$(…) || rc=$?` and treat
every non-zero as "unknown", never as "absent".

### 2. `aitask_create.sh`

- **Globals:** `BATCH_PREMISE_BASELINE=""`, `BATCH_PREMISE_BASELINE_SET=false`.
- **parse_args:** `--premise-baseline) BATCH_PREMISE_BASELINE="$2"; BATCH_PREMISE_BASELINE_SET=true; shift 2 ;;`
- **Help text:** an entry marked internal: "Explicit premise_baseline for the
  new task, overriding creation-time seeding (`""` = none). Used by carry-over
  inheritance; requires --commit. Value: `<full commit id> @ YYYY-MM-DD HH:MM`."
  Plus one line in the description block: "With --commit (or on --finalize), a
  task carrying --file-ref or --verifies is seeded with premise_baseline = HEAD."
- **Validation in `run_batch_mode`** beside the `--followup-kind` check (before
  the id claim and the label registration, so a rejection writes nothing):
  - `BATCH_PREMISE_BASELINE_SET` with `BATCH_COMMIT != true`, or with
    `--finalize`/`--finalize-all` → `die "--premise-baseline requires --commit
    (drafts are never seeded)"`. (Finalize branches return before validation, so
    check `SET` at the top of the finalize branches too.)
  - non-empty value → `premise_baseline_canonical` must succeed, else
    `die "Invalid --premise-baseline value: '<v>' (expected '<full commit id> @
    YYYY-MM-DD HH:MM', or \"\" for none)"`; store the canonical value back.
- **Seed resolver** `resolve_premise_seed <has_scope>` (called directly, never
  in `$( )`; sets global `PREMISE_SEED`; never dies):
  - `BATCH_PREMISE_BASELINE_SET` → `PREMISE_SEED="$BATCH_PREMISE_BASELINE"` (may be "").
  - else `has_scope != true` → `""`.
  - else `rev=$(git rev-parse --verify --quiet 'HEAD^{commit}' 2>/dev/null)`;
    must match `^[0-9a-f]{40}$|^[0-9a-f]{64}$`, else `warn` "premise_baseline
    not seeded: no HEAD commit" (stderr) and `""` (field absent ⇒ SKIP, the
    designed legacy behaviour; creation is never blocked). Value
    `"$rev @ $(get_timestamp)"`.
- **Serializers:** `create_task_file` and `create_child_task_file` gain
  positional **17** `local premise_baseline="${17:-}"`, emitted immediately
  after the `file_references:` block as `echo "premise_baseline: $premise_baseline"`
  only when non-empty. `create_draft_file` is unchanged (drafts never carry it).
- **`--commit` call sites** (child and parent branches, `run_batch_mode`
  ~2361/2401): after `deduped_file_refs` is computed, call
  `resolve_premise_seed` with `has_scope=true` iff
  `[[ -n "$deduped_file_refs" || -n "$BATCH_VERIFIES" ]]` — exactly the two
  conditions under which the serializer emits `file_references:` / `verifies:`
  — and pass `"$PREMISE_SEED"` as the 17th argument.
- **`finalize_draft`** (both parent and child branches, after the
  `sed ... > "$filepath"` copy and `enforce_manual_verification_gate_invariant`,
  before the commit): new helper `seed_finalized_premise_baseline "$filepath"`:
  - one `read_premise_seed_fields "$filepath"` call; non-zero exit or
    `INVALID:frontmatter` ⇒ `warn` "premise_baseline not seeded: frontmatter
    unreadable" and return (absent ⇒ SKIP, never a guessed seed);
  - any `BASELINE:`/`BASELINE_INVALID` line (the key exists, even null — a
    hand-edited draft) → keep the file as-is: no second key is ever inserted;
  - scope = `REFS:` > 0 **or** `VERIFIES:` > 0 (block-style and flow-style
    lists alike, because YAML parsed them);
  - `resolve_premise_seed true` (no explicit flag on this path) and, when
    non-empty, insert `premise_baseline: <v>` just before the frontmatter's
    closing `---` (awk into `ait_atomic_render`, value is `[0-9a-f @:-]` only).
  The insertion is in the same file that the existing scoped commit names, so it
  lands in the task-creation commit.

### 3. `aitask_archive.sh` — `create_carryover_task`

- Read the origin through `read_premise_seed_fields "$orig_file"` (YAML-decoded,
  so `"<oid> @ <ts>"` and `'<oid> @ <ts>'` arrive without their quotes).
  `BASELINE:<v>` with non-empty `<v>` → `premise_baseline_canonical "$v"`;
  `BASELINE_ABSENT` / empty → `""`.
- `BASELINE_INVALID`, a canonical-grammar rejection, or a non-zero helper exit →
  `warn "carry-over: origin premise_baseline <unreadable|malformed>; not
  inherited"` and use `""` (malformed and absent both read SKIP; archival is not
  blocked by an advisory field).
- Always append `--premise-baseline "$canon_or_empty"` to `create_args` (empty
  explicitly suppresses the `--verifies`-triggered HEAD seed, so an origin
  without a baseline yields a carry-over without one). Comment beside the
  existing `verification_baseline` inheritance block: same t1555 rule, but
  routed through creation so the value is in the creation commit.

### 4. Documentation (current-state rule)

- `aidocs/framework/task_premise_staleness.md`: "Field" — writers are now the
  update flag, creation-time seeding, and the internal creation flag for
  carry-over (grammar-checked only, why). "Seeding" — the `--commit` and
  `finalize_draft` paths, HEAD-at-commit-point, drafts unseeded, missing HEAD ⇒
  not seeded with a warning, the codebrowser live-producer fact. Lifecycle
  table: add "draft finalized with `file_references`/`verifies`" row; carry-over
  row says inherited at creation, absent stays absent, malformed dropped with a
  warning. Known limits: a draft finalized long after it was written is stamped
  at finalize time.
- `.claude/skills/task-workflow/task-creation-batch.md`: replace the "no
  creation flag" note with: seeded automatically when `--commit` carries
  `--file-ref`/`--verifies`; `--premise-baseline` at creation is internal
  (carry-over inheritance) — do not pass it; set/clear an existing task's value
  with `aitask_update.sh --premise-baseline`. Regenerate the three goldens
  `tests/golden/procs/task-workflow/task-creation-batch-{default,fast,remote}.md`
  and the three committed remote prerenders
  (`.claude/skills/task-workflow-remote-/`, `.agents/skills/task-workflow-remote-codex-/`,
  `.opencode/skills/task-workflow-remote-/` `task-creation-batch.md`) by
  rendering only the `aitask-pickrem`/`aitask-pickweb` remote closures, exactly
  as t1663_2 did (never a full `rerender remote`, which would sweep other
  sessions' uncommitted skill sources). Diff must be exactly the note.
- `website/content/docs/development/task-format.md` `premise_baseline` row:
  drop "(update-only)"; say it is seeded with the creating commit when a task is
  created with `--file-ref`/`--verifies`, inherited by a carry-over task, and
  set/cleared with `ait update --premise-baseline`. The internal creation flag is
  not documented there (same convention as the other internal flags). Run
  `python3 check_links.py --build` in `website/`. (The full workflow page stays
  t1663_5's.)
- `aidocs/framework/aitasks_extension_points.md` worked example: replace
  "update-only" with the creation seam (two serializers + finalize insertion;
  the carry-over flag), mirroring how the record describes it.
- `CLAUDE.md` / seed Task File Format comment lines: unchanged (they name the
  update flag and stay true).

### 5. Tests

**a. `tests/test_premise_baseline_seeding.sh`** (new; fixture = the
`setup_project` shape of `tests/test_file_references.sh` — bare remote + clone,
`setup_fake_aitask_repo`, copies of create/claim_id/update/find_by_file +
`lib/task_utils.sh`; plain function bodies, in-process counters). Each case
captures `pre=$(git rev-parse HEAD)` immediately before the create call:
- `--commit --file-ref lib/a.sh` → `premise_baseline:` sha == `pre`, timestamp
  half matches `YYYY-MM-DD HH:MM`.
- `--commit --verifies 1` → seeded.
- **Contract fixture:** `--commit --verifies 1 --type test`, no
  `--followup-of`/`--followup-kind` → seeded, and the file has no `anchor:` /
  `followup_kind:` (non-vacuity of "no follow-up relation").
- `--commit --followup-of <existing>` alone → field absent, and `anchor:` present
  (non-vacuity: the trigger the record used to name really ran).
- `--commit` with none of the three → absent.
- `--commit --parent <p> --file-ref …` → child seeded; parent's
  `children_to_implement` still updated (child creation unbroken).
- Draft: `--batch --file-ref …` (no `--commit`) → draft has no field; then
  `--batch --finalize <draft>` → finalized task seeded with `pre` taken before
  finalize; same for a child draft (`--parent`).
- Draft without scope → finalize leaves it absent.
- Hand-edited draft already carrying a value → finalize keeps it verbatim (no
  second line; `grep -c '^premise_baseline:'` == 1); same for a draft whose
  `premise_baseline:` key is present but null (still exactly one key).
- **Block-list finalize fixtures** (review finding): a hand-edited draft with
  only `verifies:\n  - 1` (block style, no `file_references`) → finalized task
  seeded; and one with only a block-style `file_references:\n  - lib/a.sh` →
  seeded. Non-vacuity: assert `read_yaml_field` really returns empty for that
  `verifies:` line in the fixture, so the case proves the YAML path.
- `read_premise_seed_fields` unit cases (sourced `task_utils.sh` in the
  fixture): absent / quoted / null / non-string baseline; flow vs block lists;
  unparseable frontmatter ⇒ `INVALID:frontmatter`; no Python (PATH stub) ⇒ exit 3
  with empty stdout.
- Explicit flag: `--commit --verifies 1 --premise-baseline "<pre> @ 2026-01-02 03:04"`
  → that exact value (not re-stamped); `--premise-baseline ""` with
  `--verifies` → absent; uppercase oid → stored lowercase.
- Rejections (non-zero, no task file created, counter not advanced / no new
  commit): bare `HEAD`, abbreviated oid, `<oid>@<ts>`, missing timestamp;
  `--premise-baseline <v>` without `--commit`.
- No HEAD: a fresh `git init` repo with no commits (claim-id local mode as the
  fixture allows) → created, field absent, stderr warns. If the fixture cannot
  create without a commit, assert via `resolve_premise_seed` on a sourced copy instead.
- End to end through the shipped reader: a `--file-ref lib/a.sh` task created
  at C0 reads `DECISION:FRESH`; after a committed change to `lib/a.sh` it reads
  `DECISION:ASK_STALE` with `CHANGED:lib/a.sh|`. (Copies
  `aitask_premise_stale.sh` + its lib deps into the fixture, as
  `tests/test_premise_baseline_field.sh` Part F does.)
- Structural pins: exactly two `echo "premise_baseline: ` emits in
  `aitask_create.sh`; both `create_task_file` / `create_child_task_file`
  `--commit` call sites pass `"$PREMISE_SEED"`; `create_draft_file` emits none.

**b. `tests/test_premise_baseline_field.sh` Part E** — the writer pin becomes
`aitask_create.sh aitask_update.sh` (deliberately extended, comment updated).

**c. Carry-over** — add to `tests/test_verification_stale.sh` beside
`test_carryover_inherits_baseline` (same `setup_archive_project` fixture):
- origin with `verifies:` + `premise_baseline: <real oid> @ <ts>` → carry-over
  carries the identical string (not HEAD — the origin's oid is a pre-HEAD commit
  so a re-stamp is distinguishable);
- origin with `verifies:` and no baseline → carry-over has no field (this is the
  case that would get a HEAD seed without the explicit `""`);
- origin with a malformed value → archival succeeds, carry-over has no field,
  warning printed;
- origin whose oid names no commit (history-rewritten) → inherited verbatim;
- **quoted origin values** (review finding): `premise_baseline: "<oid> @ <ts>"`
  and `premise_baseline: '<oid> @ <ts>'` → carry-over carries the unquoted
  `<oid> @ <ts>`, and `aitask_premise_stale.sh check` on the carry-over reads the
  same `BASELINE:<oid>|…` row as on the origin (non-vacuity: assert the raw
  `read_yaml_field` value in the fixture still contains the quotes).

### Post-phase (risk mitigations)

1. [seeding_red_proofs] In scratch copies under the session scratchpad (never
   the shared worktree, never `git restore`/stash), apply each mutation alone,
   re-run the new seeding test (and the carry-over cases) against the mutated
   copy, record the failing-assertion count, then discard the copy:
   (a) drop positional 17 at the `create_task_file` `--commit` call site → the
   parent `--file-ref`/`--verifies`/contract cases fail;
   (b) drop the `premise_baseline:` emit in `create_child_task_file` → the
   `--parent` case fails;
   (c) make `seed_finalized_premise_baseline` a no-op → both finalize cases fail;
   (d) remove the explicit `--premise-baseline ""` from `create_carryover_task` →
   the "origin without baseline ⇒ carry-over absent" case fails;
   (e) route finalize's scope read and carry-over's baseline read back through
   `read_yaml_field` → the block-list finalize cases and the quoted-inheritance
   cases fail.
   Each mutation must turn at least one assertion red; record the counts in the
   Final Implementation Notes (durable evidence).

## Verification

```bash
bash tests/test_premise_baseline_seeding.sh
bash tests/test_premise_baseline_field.sh
bash tests/test_verification_stale.sh
bash tests/test_archive_carryover.sh
bash tests/test_archive_verification_gate.sh
bash tests/test_file_references.sh
bash tests/test_verifies_field.sh
bash tests/test_auto_merge_file_ref.sh
bash tests/test_premise_stale.sh
ls tests/test_create*.sh tests/test_*manual_verification*.sh | xargs -n1 bash   # create-path neighbours
bash tests/test_skill_render_task_workflow.sh
./.aitask-scripts/aitask_skill_verify.sh
shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_archive.sh .aitask-scripts/lib/task_utils.sh
(cd website && python3 check_links.py --build)
```
Any existing test that byte-compares a committed task created with
`--file-ref`/`--verifies` will now see a `premise_baseline:` line; update its
expectation only when the diff is exactly that line.

Then Step 9 (Post-Implementation): code commit `feature: … (t1663_3)` by named
paths, plan commit via `aitask_task_commit.sh`, gates, archival.

## Risk

### Code-health risk: medium
- Existing create/carry-over/MV tests that compare committed task files byte-exactly gain a line; an over-broad expectation update could hide a real regression · severity: medium · → mitigation: none (covered in-plan: update only diffs that are exactly the new line; named suites in Verification)
- Three write sites (two serializers + the finalize insertion) — a missed one silently leaves a path unseeded · severity: low · → mitigation: inline post-phase seeding_red_proofs
- A second Python glue in `task_utils.sh` (beside the file-refs one) adds a reader whose output protocol could drift from its shell parser · severity: low · → mitigation: none (count-attested protocol, unit cases in 5a, prints nothing on any deviation)
- Editing `task-creation-batch.md` shifts 3 goldens + 3 committed remote prerenders · severity: low · → mitigation: none (closure-scoped re-render, diff reviewed to be exactly the note, skill verify)

### Goal-achievement risk: low
- A draft finalized long after it was written is stamped at finalize time, which can under-report drift that predates finalization · severity: low · → mitigation: none (documented in Known limits; the user chose the commit point)
- A malformed origin value is dropped rather than inherited verbatim · severity: low · → mitigation: none (malformed and absent both read SKIP; warned)

### Planned mitigations
- timing: post-phase | name: seeding_red_proofs | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: missed write site leaves a path silently unseeded | desc: mutate each seeding site in scratch copies and confirm a new test turns red

## Final Implementation Notes
- **Actual work done:** All five plan sections and the post-phase landed as written.
  - `lib/task_utils.sh`: `premise_baseline_canonical` (grammar only, lowercases) and `read_premise_seed_fields` with its `_AIT_PREMISE_SEED_GLUE`. The glue imports only `task_yaml`, its output is count-attested, and it prints nothing on any deviation (exit 2 bad shape / 3 no python).
  - `aitask_create.sh`:
    - the internal `--premise-baseline` flag (`--commit` only, refused with `--finalize`/`--finalize-all` and without `--commit`, validated before the id claim);
    - `resolve_premise_seed` (explicit flag wins, `""` included; no scope means none; otherwise HEAD of the cwd plus a timestamp; an unborn HEAD gets a warning and is not seeded);
    - positional 17 plus an emit after `file_references:` in `create_task_file` / `create_child_task_file`;
    - both `--commit` call sites seed iff `deduped_file_refs` or `BATCH_VERIFIES` is non-empty;
    - `seed_finalized_premise_baseline` in both `finalize_draft` branches. It reads YAML, skips a draft that already has the key, and inserts before the closing `---` through `ait_atomic_render`. Every failure warns and continues.
  - `aitask_archive.sh` `create_carryover_task`: reads the origin through YAML, canonicalises, warns and drops a malformed or unreadable value, and **always** passes `--premise-baseline` (`""` suppresses the `--verifies` seed).
  - Docs: the design record ("Field", "Seeding", lifecycle table, Known limits), the extension-points worked example, the website `task-format.md` row, and the `task-creation-batch.md` note. The note's three goldens and three committed remote prerenders were regenerated; each diff is exactly the note.
  - Tests:
    - `tests/test_premise_baseline_seeding.sh` (new, 91 assertions, parts A–G);
    - `test_carryover_inherits_premise_baseline` in `tests/test_verification_stale.sh` (plain, absent, malformed, history-rewritten, double- and single-quoted origins, plus reader-row parity);
    - the `tests/test_premise_baseline_field.sh` Part E writer pin, extended to `aitask_create.sh aitask_update.sh`.
- **Deviations from plan:**
  - The finalize insertion warns and continues on a render failure instead of dying, so an advisory field never aborts a finalize.
  - The new test's fixture also copies `aitask_query_files.sh`: `--followup-of` validates its target through `normalize_anchor_id` → `aitask_query_files.sh task-status`. Without it the `--followup-of` case died before creating anything, and the "not seeded" assertion passed vacuously. The planned non-vacuity check (`anchor:` really written) is what caught it.
  - `task_utils.sh` sources its siblings via `$SCRIPT_DIR`, so every test subshell that sources it sets `SCRIPT_DIR` to the fixture's `.aitask-scripts` first.
- **Issues encountered:**
  - `aitask_create.sh` and `lib/task_utils.sh` held t2214's uncommitted label-sanitizing hunks when implementation began. The non-shared work (archive, tests, docs, goldens) went first. The two files were edited only after t2214 landed (b70a70e9e: both clean vs HEAD, HEAD containing `_label_reads_as_string()` / `_set_selected_labels()`), under a self-tested last-accepted-state guard (begin / accept / check: sha, `HEAD:path`, nothing staged) on every write.
  - Plan review (user) found two blocking defects in the first plan: `read_yaml_field` keeps a quoted scalar's quotes, and it misses block-style lists. Both are fixed by `read_premise_seed_fields` and pinned by fixtures.
- **Red proofs (seeding_red_proofs post-phase; scratch mirror of `.aitask-scripts` + tests, control run green 0/0; counts = failing seeding-test assertions / failing carry-over premise assertions):**
  - (a) drop `"$PREMISE_SEED"` at the parent `create_task_file` call → 14 / 5 (the carry-over is a parent create);
  - (b) disable the `create_child_task_file` emit → 2 / 0;
  - (c) `seed_finalized_premise_baseline` returns immediately → 9 / 0;
  - (d) pass `--premise-baseline` only when non-empty → 0 / 2;
  - (e) route the finalize and carry-over reads back through `read_yaml_field`/`parse_yaml_list` → 6 / 3.
- **Key decisions:**
  - Seed at both commit points (`--batch --commit` and `finalize_draft`; drafts never). The live Tier-A producer, codebrowser, runs interactive create, so it goes draft → finalize.
  - Carry-over inheritance goes through a creation flag, not a post-create update. That leaves no interim HEAD-stamped commit and no commit-existence check that could abort archival on a history-rewritten origin.
  - The creation flag is grammar-only. `aitask_update.sh` is not rewired onto `premise_baseline_canonical`, because its contract adds bare-oid stamping and the commit-existence check.
  - A key already present in a draft, even null, is never duplicated.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - t1663_4 (Check 6): new tasks with `--file-ref`/`--verifies` now leave creation with a baseline, so its end-to-end fixture can create one with `aitask_create.sh --batch --commit --file-ref …` rather than hand-writing the field. `tests/test_premise_baseline_seeding.sh` Part F shows the seeded FRESH → ASK_STALE path through the reader.
  - t1663_5 (docs): the opt-in wording holds — seeded at creation (or draft finalize) when the task carries `file_references`/`verifies`; `--followup-of` alone does not seed. `aitask_create.sh --premise-baseline` is internal (carry-over) and deliberately undocumented on the website. The `task-format.md` row already states creation seeding and carry-over inheritance.
  - t1663_6 (retrospective): MV tasks created by `aitask_create_manual_verification.sh` are now seeded (`--verifies`), but Check 3 routes them away, so split them out when counting the seeded population.

## Post-Review Changes

### Change Request 1 (2026-11-06)
- **Requested by user:** (review finding, confirmed by repro) `--premise-baseline` was validated only in `run_batch_mode`. The interactive flow (no `--batch`) never reaches that validation, and its `finalize_draft` → `seed_finalized_premise_baseline` → `resolve_premise_seed` trusted the unvalidated override, so `aitask_create.sh --premise-baseline HEAD` committed `premise_baseline: HEAD`. The reader rejects that value, which silently disables the check.
- **Changes made:**
  - `main()` refuses `--premise-baseline` without `--batch`, right after `parse_args` and before the mode split.
  - Defence in depth: `resolve_premise_seed` takes a second argument, and the finalize seeder passes `ignore_override`, so the finalize path never honours the flag.
  - Regression cases in `tests/test_premise_baseline_seeding.sh`:
    - the interactive route is refused with the specific message (the message assertion keeps it from passing vacuously on a box without fzf), with no commit and no draft;
    - a lifted-function unit shows the finalize resolver seeds HEAD while the batch resolver honours the override;
    - a structural pin that the finalize seeder passes `ignore_override`.
  - Test now 97/97. Red proofs (scratch mirror, control 0/0):
    - (f) remove the `main()` refusal → 1 failing;
    - (g) drop `ignore_override` at the finalize call → 1 failing.
- **Files affected:** `.aitask-scripts/aitask_create.sh`, `tests/test_premise_baseline_seeding.sh`
