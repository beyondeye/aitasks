---
Task: t1243_8_boardgroup_field_and_model.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_10_group_collapse_and_filtering.md, aitasks/t1243/t1243_11_group_formation_and_block_moves.md, aitasks/t1243/t1243_12_group_membership_commands.md, aitasks/t1243/t1243_13_documentation.md, aitasks/t1243/t1243_14_retrospective_benchmark.md, aitasks/t1243/t1243_15_manual_verification_board_groups_and_reordering.md, aitasks/t1243/t1243_9_group_focus_and_rendering.md
Archived Sibling Plans: aiplans/archived/p1243/p1243_1_movement_baseline_and_harness.md, aiplans/archived/p1243/p1243_2_board_field_persistence_seam.md, aiplans/archived/p1243/p1243_3_gap_indexing.md, aiplans/archived/p1243/p1243_4_render_filter_scoping.md, aiplans/archived/p1243/p1243_5_lateral_dom_transplant.md, aiplans/archived/p1243/p1243_6_multiselect_marking.md, aiplans/archived/p1243/p1243_7_move_to_column_command.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-07 12:58
---

# t1243_8 — `boardgroup` field and model

> **Verify-path re-plan.** `aiplans/p1243/p1243_8_boardgroup_field_and_model.md`
> had never been verified (`plan_verified` count 0). Every anchor was re-located
> by symbol name against current `HEAD`. Four review concerns were then tested
> live; **all four reproduced** and are addressed below.

## Context

t1243 adds **in-column task groups** to `ait board`. This child lands the
**data model** only — no board widgets (t1243_9/10/11/12 own those).

```yaml
boardcol: now
boardidx: 3072
boardgroup: perf_work
```

Identity is `(column, slug)`; membership is "same column, same slug". No
registry, no ids, no title/colour store in v1.

The hard part is not the field — it is that four silent-failure seams meet on
it (parent plan, code-health risk 3). t1243_2 closed the save/timestamp seam.
This child closes the rest: **membership must not merge local-wins**, and
**neither one-sided presence nor a task-wide `updated_at` can decide who edited
the field**.

## Anchor re-verification — results

| Premise | Verdict |
|---|---|
| `BOARD_LAYOUT_KEYS` exists; `_KEEP_LOCAL_FIELDS` derived from it | ✅ `task_yaml.py:55`, `aitask_merge.py:139` |
| `BOARD_KEYS` exists separately | ✅ but a bare **alias**: `BOARD_KEYS = BOARD_LAYOUT_KEYS` (`task_yaml.py:62`) |
| `merge_frontmatter` has no base parameter | ✅ `(local_meta, remote_meta, batch=False)` `:171` |
| One-sided presence resolves first, unconditionally | ✅ `:209-214`, ahead of every field rule |
| `_ACTIVE_TUPLE_FIELDS` is the pre-loop precedent | ✅ block `:196-200`, loop guard `:203-204` |
| diff3 base parsed then discarded | ✅ `pass  # discard base content` `:94` |
| `merge.conflictStyle` configured nowhere | ✅ the diff3 path is production-dead |
| `main()` has no `--base-file` | ✅ only `file`, `--batch`, `--rebase` |
| `--rebase` swaps documents *before* frontmatter parsing | ✅ `:436-440` — base needs **no** swap |
| One driver invocation site, `aitask_sync.sh:221` | ✅ exact line match |
| `get_column_tasks` sorts by `(normalize_board_idx, filename)` | ✅ `aitask_board.py:1460-1470` |
| `--boardidx` update-only, absent from `aitask_create.sh` | ✅ zero matches in create |
| `aitask_fold_mark.sh` has no per-field scalar list | ✅ `anchor` precedent is a comment-only no-op |

### Premise corrections

1. **"seven call sites"** of `reload_and_save_board_fields` → now **six**
   (t1243_3 retired `swap_tasks`, renamed `normalize_indices` →
   `respace_column`). This child adds none; the frozen AST table
   `EXPECTED_CALL_SITES` already matches — no test churn.

2. **`task_git show ":1:$file_path"` uses the wrong variable.** `$f` is
   git-relative; `$file_path` is `.aitask-data/$f` in branch mode. A `:1:`
   pathspec must be repo-relative → use **`$f`**.

3. **The shared match predicate already exists.** t1243_4 landed
   `task_matches_filter(task, visible, search)` at `aitask_board.py:375-395` —
   module-level, app-free, per-task. `board_groups.py` will **not** re-export or
   re-implement it. Scope reduction, recorded.

4. **`SEM` is already the literal `"boardgroup"`**
   (`test_board_persistence_seam.py:78`). Landing the key makes
   `allow_semantic_key()` a no-op and turns the currently-**vacuous**
   `test_no_shared_board_key_is_ever_local_wins` live. Their docstrings
   ("synthetic stand-in", "none of which should see it") become untrue and are
   rewritten in the same commit.

### Review concerns — tested live, all four reproduced

**(A) Branch mode never reaches the merge driver's success path.** Built a repo
with a real `.aitask-data` worktree, wedged a rebase, and ran the actual
`lib/task_utils.sh`:

| Step | Observed |
|---|---|
| `task_git show ":1:<path>"` | **RC=0, 55 bytes** — base extraction works while wedged ✓ |
| `task_git add "<path>"` (as `aitask_sync.sh:223` calls it) | **`die`d**; path **still unmerged** |
| `git rebase --continue` | `aitasks/t1_x.md: needs merge / You must edit all merge conflicts` |

`add` is neither read-only (`task_utils.sh:70-89`) nor recovery (`:92-104`), so
`assert_data_worktree_clean` kills it on `rebase-merge`. `aitask_sync.sh:223`
suppresses that with `2>/dev/null || true`, so the driver reports success, the
file is never staged, continuation fails, and sync aborts to `CONFLICT:`.
**`AUTOMERGED` is unreachable in branch mode — and this repo runs branch mode**
(`.aitask-data/` is present). Shipping `--base-file` without fixing this would
be shipping dead code. **This is now a gate, not an observation** (§0).

**(B) A malformed persisted value crashes the "pure, total" derivation.** CLI
validation cannot protect against a hand edit or a value arriving from another
checkout. Probed against the real parser: `boardgroup: []` → `[]`, and
`isinstance(..., Hashable)` is **False** — using it as a group-unit map key
raises `TypeError`. `parse_frontmatter` uses a real YAML loader
(`task_yaml.py:139`) and the repo's stated philosophy is that the parser leaves
malformed input "type-honest" for the **consumer** to handle
(`_normalize_task_ids` docstring). So the boundary belongs in `board_groups.py`
(§4).

**(C) The shell writer emits YAML null, not an empty string.** Probed both
writers:

| Writer | Emits | Reparses as |
|---|---|---|
| Python `serialize_frontmatter` (`yaml.dump`) | `boardgroup: ''` | `''` ✓ |
| Shell `echo "boardgroup: $v"` with `v=""` | `boardgroup: ` | **`None`** ✗ |
| explicit `boardgroup: ""` | `boardgroup: ""` | `''` ✓ |

So the Python path is already safe and only the **shell** path breaks the
tombstone. Canonicalising `None`→`""` in the merger would paper over it while
leaving the persisted contract ambiguous to every other reader. Fix at the write
site (§5).

**(D) The integration test can pass without exercising the feature.** Git merges
textually per hunk: if the `boardgroup:` and `status:` edits land in
non-overlapping hunks, the rebase succeeds cleanly, `aitask_merge.py` is never
invoked, and the assertion on the final file content still passes.
`tests/test_sync.sh` Test 12 only works because its two edited lines are
**adjacent**. The test must assert the conflict actually happened (§Verification).

## Approach

### 0. Gate — recovery-path authorization (blocking, runs first)

Concern (A) reproduced, so this is a prerequisite, not a follow-up. The current
block (`aitask_sync.sh:222-228`) has **two** independent defects:

```bash
if [[ $merge_exit -eq 0 ]]; then
    task_git add "$f" 2>/dev/null || true      # (1) authorization  (2) failure swallowed
    resolved_count=$((resolved_count + 1))     # counted as resolved regardless
    iinfo "Auto-merged: $f"                    # actively reports success
else
    unresolved="${unresolved}${unresolved:+$'\n'}$f"
fi
```

A failed `add` — the state-check `die`, but equally an `index.lock`, a
permission or filesystem error — is discarded, the file is counted resolved,
success is printed, and the file never enters `unresolved`. The problem then
surfaces only as a rebase-continuation failure, by which point `2>/dev/null` has
destroyed the diagnostic. Fix both:

```bash
if [[ $merge_exit -eq 0 ]]; then
    local add_err add_rc=0
    add_err="$(AIT_GIT_SKIP_STATE_CHECK=1 task_git add "$f" 2>&1)" || add_rc=$?
    if [[ $add_rc -eq 0 ]]; then
        resolved_count=$((resolved_count + 1))
        iinfo "Auto-merged: $f"
    else
        # warn(), never info()/iinfo(): this function's STDOUT is the
        # unresolved-file list its caller parses.
        warn "auto-merge could not stage $f (git add rc=$add_rc): ${add_err:-<no output>}"
        unresolved="${unresolved}${unresolved:+$'\n'}$f"
    fi
else
    unresolved="${unresolved}${unresolved:+$'\n'}$f"
fi
```

**A failed stage is an unresolved merge, immediately** — the file joins
`unresolved`, so sync reports `CONFLICT:<file>` honestly instead of claiming
success and failing later. The bypass stays narrow; the diagnostic is preserved
and routed to stderr.

**Channel discipline is load-bearing here** (verified): `info()` echoes to
**stdout** (`terminal_compat.sh:19`), `warn()` redirects to **stderr** (`:21`),
and `iinfo()` calls `info` whenever `BATCH_MODE == false` (`aitask_sync.sh:125`).
Since the caller does `remaining=$(try_auto_merge "$conflicted")`, a diagnostic
on stdout would be parsed as a conflicted filename. `add_err="$(… 2>&1)"`
captures both of git's streams into a variable so nothing leaks either.

`AIT_GIT_SKIP_STATE_CHECK` is the **documented, advertised** bypass — the die
message itself names it (`task_utils.sh:132`) — and scoping it to this single
call keeps the guard fully intact everywhere else. The guard exists to stop
*accidental* mutation while wedged; sync's conflict resolution is *deliberate*
mutation while wedged, by the code that owns the rebase.

Rejected: adding `add` to `_ait_git_subcmd_is_readonly`/`_is_recovery` (weakens
the guard repo-wide for every caller), and switching to `_ait_data_git` (whose
docstring scopes it to read-only probes and `task_push`, which "asserts once up
front" — this call site does not).

**This is a behaviour change to sync's conflict path for every field, not just
`boardgroup`**, so it carries its own branch-mode regression test asserting
`AUTOMERGED` and a staged, merged file — the test that would have caught it.

### 1. `lib/task_yaml.py` — append to `BOARD_KEYS`

```python
BOARD_KEYS = BOARD_LAYOUT_KEYS + ("boardgroup",)
```

One line; the split exists. Six consumers inherit it with no edit:
`serialize_frontmatter` tail ordering, `_is_phantom_stub`
(`aitask_board.py:1328`), `work_report_gather:180`, `trail_gather:313`,
`board_columns._eligible:483`, `test_board_movement.nonboard_diff:103`.

`_KEEP_LOCAL_FIELDS` needs **no** change — it reads `BOARD_LAYOUT_KEYS`.

**Do not** widen `reload_and_save_board_fields` to the whole `BOARD_KEYS` set;
its `fields` argument is required per-call precisely so a stale board object
cannot re-apply a key it never mutated. Four negative controls in
`test_board_persistence_seam.py` exist to stop that.

Update the `serialize_frontmatter` docstring, which enumerates
"board keys (boardcol, boardidx)".

### 2. `aitask_merge.py` — base-aware resolution

```python
_BASE_AWARE_FIELDS = ("boardgroup",)
```

- `merge_frontmatter(local_meta, remote_meta, batch=False, base_meta=None)`.
- A **pre-loop block** resolves these before `for key in all_keys:`; the loop
  gains `if key in _BASE_AWARE_FIELDS: continue`, so the unconditional
  one-sided-presence branch can never see them.
- `main()` gains `--base-file PATH`, parsed through the same `parse_frontmatter`
  as the two sides. Missing flag, unreadable file, or no frontmatter →
  `base_meta = None`.
- **No rebase swap for the base** — stage 1 is the ancestor either way.
- The diff3 marker parser is untouched (fallback only).

**Canonicalisation — the same `normalize_group_slug` from §4, on all three
sides.** Absent, `None` and `""` all mean *ungrouped*; comparing raw would send
a decidable case to PARTIAL when one side deletes the key and another writes the
tombstone. This is defence in depth, **not** the tombstone contract — §5 is.

| base vs sides | Result |
|---|---|
| values equal | that value |
| only local differs from base | local |
| only remote differs from base | remote |
| both differ, different values | **unresolved → PARTIAL** |
| no base, values differ | **unresolved → PARTIAL** (fail closed) |
| absent on both sides | key not emitted |

Emission mirrors `_ACTIVE_TUPLE_FIELDS` (`if any(k in local_meta or k in
remote_meta ...)`), so a never-grouped task never gains the key. Unresolved uses
the existing convention (placeholder + `unresolved.append` → exit 2
`PARTIAL:<fields>`).

### 3. `aitask_sync.sh` — supply the base from git's conflicted index

In `try_auto_merge`, before the driver call at `:221`:

```bash
base_args=()
base_tmp="$(mktemp)"
if task_git show ":1:$f" > "$base_tmp" 2>/dev/null; then
    base_args=(--base-file "$base_tmp")
else
    rm -f "$base_tmp"; base_tmp=""
fi
```

Pass `${base_args[@]+"${base_args[@]}"}` (the repo's safe-empty expansion, cf.
`aitask_crew_init.sh:91`); `rm -f "$base_tmp"` after. `show` is on the read-only
allowlist and was **measured** working under a wedged rebase (§Review concern A).
An add/add conflict has no stage 1; `git show :1:` fails, `base_args` stays
empty, PARTIAL is correct.

### 4. `lib/board_groups.py` — new pure module (INV-R)

Same shape as `lib/topic_semantics.py` / `lib/board_ordering.py`: pure,
duck-typed over `.filename`/`.metadata`, docstring naming the semantic owner,
the tests that must stay green, and forward pointers to t1243_9/10/11.

**`normalize_group_slug(raw)` — the malformed-value boundary** (concern B).
Directly mirrors `normalize_board_idx`'s contract, which already coerces junk
deterministically rather than raising:

- `str` and non-empty after strip → that string is the group key.
- everything else — `None`, `""`, whitespace-only, `list`, `dict`, `int`,
  `bool` → **`""` (ungrouped)**.

Only `str` values become keys, so the unit map can never be handed an unhashable
key and INV-R stays **total**. A non-CLI-shaped string (e.g. a hand-edited
`Perf Work`) is *kept* as its own group rather than discarded — it is hashable
and sortable, so grouping still works, and silently dropping a user's hand edit
would be worse. `int`/`bool` are treated as typos, not as keys.

> **INV-R.** A column's rendered order is a pure, total function of the
> persisted state of that column's tasks.

Derivation over `get_column_tasks(col)` (already sorted by
`(normalize_board_idx, filename)`):

1. A task whose `normalize_group_slug` is non-empty joins that slug's **group
   unit**; every other task is a **singleton unit**.
2. A unit's sort key is the key of its **first** member in that walk.
3. Units emit in sort-key order; members render inside their unit in walk order.
   A single-member group unit renders as a plain card (mirrors
   `_build_topic_lanes`'s `len(members) >= 2` singleton collapse).

**Contiguity of `boardidx` is explicitly not an invariant** — grouping writes no
index at all. No post-sync reconciliation exists or is needed.

### 5. `aitask_update.sh --boardgroup` (update-only)

Threads through the same places as `--boardidx` (globals `:94-97`, help
`:225-227`, parse `:350-351`, has-update probe `:1762-1763`, frontmatter read
`:551-552`, apply `:1989-1997`, `write_task_file` positional + serialize
`:801-808`).

Three things the `--boardidx` pattern does **not** give for free:

- **Slug validation — reject, never coerce** (user-decided). Validate in
  `main()` *after* `parse_args`, *before* any file touch (the `--boardcol`
  placement, `:2225-2227`), with a `normalize_anchor_id`-shaped check: the value
  must already match `^[a-z0-9_]+$`, else `die "boardgroup '<raw>' is not a
  valid slug (expected [a-z0-9_]+)"`. No lowercasing, no separator coercion —
  two inputs must never silently collapse into one group, since the parent plan
  requires coalescing to be **confirmed, never silent**. t1243_12's UI
  normalises before calling. `--boardgroup ""` skips validation and clears.

- **The tombstone must be written quoted** (concern C). `write_task_file` emits
  board fields only when non-empty (`if [[ -n "$boardcol" ]]`), and a bare
  `echo "boardgroup: $v"` with an empty `v` produces `boardgroup: ` — which the
  real YAML loader reads back as **`None`, not `""`**. Emit the two-character
  literal explicitly:

  ```bash
  if [[ -n "$boardgroup" ]]; then
      echo "boardgroup: $boardgroup"
  elif [[ "$boardgroup_present" == true ]]; then
      echo 'boardgroup: ""'
  fi
  ```

  Append **two** positionals (`new_boardgroup`, `boardgroup_present`) at the
  **end** of the `write_task_file` argument list — appending avoids renumbering
  the 18 existing positional reads. Present is true when the existing file
  carried the key or the user passed the flag. The Python writer already emits
  `boardgroup: ''` correctly (measured) and needs no change.

`updated_at` needs no special handling: `write_task_file` regenerates it on
every write (`get_timestamp`, `:657-658`).

### 6. Sweep, not fix

`aitask_fold_mark.sh` gets a **comment-only no-op note** — the exact `anchor`
(t1016) precedent at `:315-317`. No per-field list exists to extend.

Walk `aidocs/framework/aitasks_extension_points.md` (six layers: 1, 2, 3, 4, 4b,
5) and hand uncovered layers on:

- **Layer 3** (`TaskDetailScreen` `BoardGroupField`) → **t1243_12**, per the
  parent plan's decomposition table.
- **Layer 5** (docs) → **t1243_13**: `seed/aitasks_agent_instructions.seed.md` +
  the `AGENTS.md` mirror, `CLAUDE.md`, `.codex/instructions.md`,
  `.opencode/instructions.md`,
  `website/content/docs/development/task-format.md`,
  `website/content/docs/tuis/board/reference.md`,
  `website/content/docs/commands/task-management.md`,
  `.claude/skills/task-workflow/task-creation-batch.md`, and
  **`website/content/docs/commands/sync.md:72`'s merge-rules table** (needs a
  `boardgroup` row: base-aware, fails closed to PARTIAL). Also the
  `aitask-trail` `SKILL.md.j2` + three goldens, which list `boardidx` under
  "never mutate task metadata" — a goldens regeneration, one call per profile.

## Verification

**Gate regression tests (§0)** — three cases, all in a branch-mode fixture (real
`.aitask-data` worktree):

1. **Authorization** — a frontmatter conflict must report **`AUTOMERGED`** and
   leave the path **staged and merged**. Run against unmodified `HEAD` first to
   confirm it **fails** (reproducing `CONFLICT:`), then against the fix. A test
   that has never failed does not prove the fix.
2. **Failed stage is honest.** Force the `add` to fail and assert sync reports
   **`CONFLICT:<file>`**, not `AUTOMERGED`, and that the `Auto-merged: <f>` line
   is **absent** for that file. This is the assertion the current `|| true`
   makes impossible.

   **Do not induce the failure with a pre-planted `index.lock`** — measured, it
   defeats the test: `git rebase` aborts at `error: could not detach HEAD` with
   **no rebase state, no unmerged path, and no conflict**, so `try_auto_merge`
   is never reached and the case passes for the wrong reason. Use a **narrowly
   scoped `git` PATH shim** instead (verified viable: every `task_git` /
   `aitask_sync.sh` call site invokes bare `git`, so PATH resolution reaches the
   shim; a probe confirmed pass-through for `status` and interception of `add`
   with rc=128 and a stderr diagnostic).

   The shim passes everything through to the real git and fails **only** `add`,
   and only **while a rebase is in progress** (probe the data worktree's git-dir
   for `rebase-merge`). That scoping matters: sync's auto-commit step runs
   `git add` *before* the pull, and a blanket-failing shim would abort the run
   before a conflict ever exists. Install it on `PATH` for the `ait sync`
   invocation only — fixture setup uses real git.

   **Positive control, asserted first:** confirm an unmerged path actually
   materialised (`--diff-filter=U` names the task file) before asserting the
   `CONFLICT:` outcome. Without it this case can still pass vacuously if the
   rebase never conflicted — the same failure mode as the `index.lock` approach,
   just harder to see.

3. **Diagnostic survives and stays off stdout** — the same forced failure must
   emit git's message on **stderr**, while the captured stdout contains only the
   conflicted filename. Assert stdout is **exactly** the file list: a `warn`
   accidentally written as `info` would put prose into the conflict list, and
   only a stdout-exact assertion catches that.

**Pure unit tests** — new `tests/test_board_groups.py`: scattered indices, ties,
an interleaved non-member, a singleton group, an empty column; the **two
post-sync fixtures** ("remote add", "remote remove") rendering identically and
stably; and a **malformed-value matrix** for `normalize_group_slug` — `[]`,
`{}`, `42`, `True`, `None`, `""`, `"   "`, and a non-CLI-shaped string — each
asserted to produce a deterministic unit layout **and no exception**. `[]` is
the specific regression case: it is non-empty and unhashable.

**Merge unit tests** — extend `tests/test_aitask_merge.py`: local-only change,
remote-only change, both-changed-same, both-changed-different (PARTIAL),
deletion from each side, no base (PARTIAL), identical, absent-on-both, and the
`None`/absent/`""` canonicalisation cases.

**Integration test — must prove it exercised the feature** (concern D). New
self-contained `tests/test_aitask_merge_boardgroup.sh` carrying its own
bare-remote + `local`/`pc2` harness modelled on `tests/test_sync.sh`'s
`setup_sync_repos()` / Test 12. Base carries `boardgroup: perf_work`; one side
clears it to `""`; the other changes only `status`. Three assertions, in order:

1. **Positive control on the path** — the rebase actually conflicts:
   `git diff --name-only --diff-filter=U` names the task file. Without this the
   test can pass on a clean textual auto-merge that never invoked the driver.
2. Sync reports **`AUTOMERGED`** (not `CONFLICT:`).
3. The **cleared** side wins — the `status`-only edit must not win a field it
   never touched.

The fixture places `status:` and `boardgroup:` on **adjacent lines** so the
hunks necessarily overlap; that adjacency is load-bearing, so a sibling case
places the same two edits far apart and asserts git auto-merges with **no**
unmerged path — proving assertion 1 discriminates rather than always holding.

**Negative control** — the same scenario with the base withheld must yield
PARTIAL, proving the base is what decided it.

**Guard test** — every `aitask_merge.py` invocation site in `aitask_sync.sh`
passes `--base-file`.

**Seam tests** — `aitask_update.sh --boardgroup` round-trips and advances
`updated_at`. Clearing asserts **the key is present AND `parse_frontmatter`
returns `''` (a `str`), explicitly `assertIsNotNone`** — the bare-colon
regression yields `None` and must fail this. A `boardgroup` set in memory
survives a named-field save (`fields=("boardgroup",)`) and is **not** written
back by a plain layout move. `test_board_persistence_seam.py`'s `SEM` docstrings
are rewritten from "synthetic" to real.

Run: `bash tests/run_all_python_tests.sh --test-dir tests`, `bash
tests/test_sync.sh`, `bash tests/test_aitask_merge.sh`, `bash
tests/test_aitask_merge_boardgroup.sh`, `shellcheck
.aitask-scripts/aitask_sync.sh .aitask-scripts/aitask_update.sh`.

> Baseline: t1243_2 recorded the Python suite at **1 pre-existing failure**
> (`test_board_work_report`, from a malformed `t_<slug>.md` in the live tree).
> Confirm that is still the only failure before and after.

## Risk

### Code-health risk: medium

- The merge driver is the single point where every checkout's task data
  converges; a wrong rule silently loses another machine's edit rather than
  failing loudly · severity: **high** · → mitigation: inline pre-phase
  `characterize_merge_baseline`; plus a pre-loop block mirroring the audited
  `_ACTIVE_TUPLE_FIELDS` precedent, fail-closed PARTIAL in both ambiguous cases,
  and a real-rebase integration test with a withheld-base negative control.
- §0 changes sync's conflict-resolution authorization for **every** field, not
  just `boardgroup` · severity: **high** · → mitigation: the narrowest available
  form (one call site, the documented `AIT_GIT_SKIP_STATE_CHECK` bypass, guard
  untouched elsewhere), two broader alternatives explicitly rejected, and a
  branch-mode regression test proven to fail before the fix.
- §0 also converts a swallowed `git add` failure into an unresolved merge, so
  errors that were previously silent now surface as `CONFLICT:` · severity:
  medium · → mitigation: this is strictly more honest than reporting a success
  that cannot complete, and the failure diagnostic is preserved rather than
  discarded; a forced-failure test pins both the `CONFLICT:` outcome and the
  stderr routing, since a diagnostic mistakenly sent to stdout would be parsed
  as a conflicted filename.
- `--base-file` adds a shell → Python argument inside a wedged-rebase path where
  a mistake is only observable during a conflict · severity: medium ·
  → mitigation: `task_git show` measured working while wedged; extraction is
  best-effort (missing base degrades to today's behaviour); guard test pins
  every invocation site.
- `write_task_file` gains positionals in a 30-argument call · severity: medium ·
  → mitigation: appended at the **end** so no existing index shifts;
  set/clear/absent round-trip test.

### Goal-achievement risk: medium

- Branch mode cannot reach the merge driver's success path at all, so the whole
  feature would be dead code in this repo's own operating mode · severity:
  **high, and confirmed live** · → mitigation: promoted from an observation to
  the blocking §0 gate, fixed in this child with a regression test.
- A malformed persisted `boardgroup` (`[]` is non-empty and unhashable) crashes
  the "pure, total" derivation; CLI validation cannot protect values arriving
  from a hand edit or another checkout · severity: **high** · → mitigation:
  `normalize_group_slug` boundary in `board_groups.py` (§4) with an
  eight-case malformed-value matrix.
- The `""` tombstone round-trips as YAML `None` through the shell writer,
  making the persisted contract ambiguous to every reader · severity: **high** ·
  → mitigation: emit `boardgroup: ""` explicitly at the write site (§5); the
  seam test asserts the parsed value is a `str`, not merely that a later merge
  happens to work.
- The integration test can pass on a clean textual auto-merge that never invoked
  the driver · severity: medium · → mitigation: an unmerged-path positive
  control plus a far-apart sibling case proving that control discriminates.
- INV-R is unverifiable at this layer because nothing renders yet · severity:
  low · → mitigation: pure derivation, property-tested against the two post-sync
  fixtures; visual confirmation belongs to t1243_9 and the t1243_15 sibling.

### Planned mitigations
- timing: pre-phase | name: characterize_merge_baseline | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (merge driver regression) | desc: Characterize today's resolution for every merge field this task does not touch, run green against unmodified HEAD first, then re-assert base_meta=None is behaviour-identical.
- timing: pre-phase | name: branch_mode_recovery_gate | type: bug | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement risk 1 (branch mode unreachable) | desc: Blocking gate — reproduce the branch-mode CONFLICT against unmodified HEAD, scope AIT_GIT_SKIP_STATE_CHECK to the single task_git add in try_auto_merge, and pin AUTOMERGED with a branch-mode regression test.

### Reassessment after inlining
`branch_mode_sync_probe` was **upgraded from a probe to a blocking fix**
(`branch_mode_recovery_gate`) because the probe was run during planning and the
defect reproduced. That raises code-health exposure — the child now edits sync's
authorization path — but removes a **high** goal-achievement risk that would
otherwise have shipped a feature that cannot execute in this repo's own mode.
Both dimensions remain **medium** overall: the sync change is one call site
using a documented bypass, and every new risk carries a test proven to fail
first.

## Step 9 (Post-Implementation)

Merge to `main`, archive per the standard flow.

**Record in Final Implementation Notes:**
- `anchor` merges newer-wins (`aitask_merge.py:232-235`) and has the same
  task-wide-timestamp weakness `boardgroup` avoids. Observation only.
- **Upstream defects identified:** `aitask_sync.sh:223 — task_git add is
  rejected by assert_data_worktree_clean mid-rebase in branch mode and the
  failure is swallowed by \`|| true\`, so frontmatter auto-merge never completes
  and sync aborts to CONFLICT:` — **fixed in this task** (§0) rather than
  deferred, because it blocked this task's own deliverable. Note the whole test
  suite was blind to it: `tests/test_sync.sh` runs only in legacy mode, where
  the guard is a no-op.
- **Upstream defect (recorded, NOT fixed — separate scope):**
  `aitask_sync.sh:225 — iinfo "Auto-merged: $f" writes to STDOUT in interactive
  mode (iinfo → info → echo), but try_auto_merge's stdout is captured by the
  caller as the unresolved-file list, so a non-batch sync with any unresolved
  file yields a list polluted with "Auto-merged: …" prose.` Found while routing
  §0's diagnostic. Batch mode is unaffected (`iinfo` no-ops), which is why the
  suite never caught it. §0 deliberately uses `warn` (stderr) so it adds no new
  pollution, but it does not fix the existing `iinfo` line.
- **Notes for sibling tasks:** membership writes use
  `reload_and_save_board_fields(fields=("boardgroup",))` — there is no
  `semantic=True` bool. t1243_11 must name `("boardgroup",)` **only**; naming
  `boardidx` too would discard a concurrent move. `task_matches_filter` is
  already the data-level predicate for t1243_10 — do not reimplement it. Any new
  consumer of `boardgroup` must read it through `normalize_group_slug`, never
  raw: the persisted value can legally be `None`, a list, or an int.

---

## Post-Review Changes

### Change Request 1 (2026-08-07 13:40)

- **Requested by user:** Two concerns, both verified live and both valid.
  (a) *blocking* — `normalize_group_slug` returned `raw.strip()`, so a
  hand-edited `boardgroup: "perf_work "` silently joined the `perf_work` group
  and read as UNCHANGED from an unspaced base in the merge driver. This
  contradicted the module's own documented promise to preserve non-CLI-shaped
  strings and the design's no-silent-coalescing rule.
  (b) *follow-up* — in interactive mode `try_auto_merge` still wrote
  `iinfo "Auto-merged …"` to stdout, which its caller parses as the
  unresolved-file list.

- **Changes made:**
  - **(a)** `normalize_group_slug` now returns `raw if raw.strip() else ""` —
    whitespace-only is ungrouped, everything else is **verbatim**. Confirmed by
    probe that a *quoted* YAML scalar preserves its whitespace through the
    loader (`'perf_work '`), while unquoted plain scalars are stripped by YAML
    itself — so only the hand-edit case reaches the boundary, and stripping
    there was silently destroying it. Added `test_whitespace_is_content_not_noise`,
    `test_whitespace_bearing_slug_forms_its_own_group`, and two merge cases
    (`test_whitespace_bearing_value_is_a_real_change`,
    `test_whitespace_only_value_reads_as_ungrouped`).
  - **(b)** Fixed rather than deferred, because a live probe showed it was worse
    than a cosmetic leak: the interactive loop opened `$EDITOR` on `RESOLVED`,
    on `Auto-merged: aitasks/t1_ok.md` and on `PARTIAL:body`, and the genuinely
    conflicted file was **never offered at all**. Added `iinfo_err()` (stderr
    variant of `iinfo`, same batch-mode suppression and colouring) and routed
    all three informational lines inside `try_auto_merge` through it — that
    function's stdout is a data channel. Added Test 5 to
    `tests/test_sync_branch_mode_automerge.sh`, which needs a MIXED outcome
    (one file resolving, one not) to expose the leak at all: when everything
    resolves, `unresolved` is empty and the caller discards stdout.

- **Files affected:** `.aitask-scripts/lib/board_groups.py`,
  `.aitask-scripts/aitask_sync.sh`, `tests/test_board_groups.py`,
  `tests/test_aitask_merge.py`, `tests/test_sync_branch_mode_automerge.sh`.

- **Verification:** full Python suite PASSED (runner=pytest, exit=0);
  `test_sync_branch_mode_automerge.sh` 15/15 with the fix and **7 failures**
  against unmodified `HEAD` (including "the genuinely conflicted file IS offered
  for editing"); `test_aitask_merge_boardgroup.sh` 14/14; `test_sync.sh` and
  `test_aitask_merge.sh` unchanged; shellcheck 22 findings before and after —
  zero new.

---

## Final Implementation Notes

- **Actual work done:** The planned data model landed in full — `boardgroup`
  appended to `BOARD_KEYS` (six consumers inherit it unedited); new pure
  `lib/board_groups.py` (INV-R unit derivation + the `normalize_group_slug`
  totality boundary); base-aware merge resolution in `aitask_merge.py`
  (`_BASE_AWARE_FIELDS`, pre-loop block, `--base-file`); the merge base supplied
  from git stage 1 by `aitask_sync.sh`; `--boardgroup` in `aitask_update.sh`
  (update-only, reject-don't-coerce validation, `""` tombstone); a fold no-op
  note; and the extension-points worked example. Plus the §0 gate described
  below. 1050 lines of new tests across four files.

- **Deviations from plan:**
  - **`board_groups.py` does NOT re-export the filter match predicate.** The
    task file asked for it, but verification found t1243_4 had already landed
    `task_matches_filter(task, visible, search)` at `aitask_board.py:375-395` —
    module-level, app-free, per-task. Re-exporting would have been a parallel
    implementation of a canonical seam. Scope reduction, recorded at plan time.
  - **The planned integration fixture was unusable.** "Clear `boardgroup` vs a
    `status`-only edit" always reports PARTIAL — divergent non-`Implementing`
    statuses are unresolvable by a *pre-existing* rule, so the case proved
    nothing about `boardgroup`. Switched the unrelated edit to `labels`
    (union-merged). Assertions now check the **parsed value and type** via the
    real loader, not a quoting style: the Python writer emits `boardgroup: ''`
    and the shell writer `boardgroup: ""`, and a bare colon yields `None`.
  - **"Seven call sites" of `reload_and_save_board_fields` is now six** —
    t1243_3 retired `swap_tasks` and renamed `normalize_indices` →
    `respace_column`. No call site added here, so `EXPECTED_CALL_SITES` needed
    no edit.

- **Issues encountered:**
  - **`try_auto_merge` had FOUR defects, not the one planned**, all from one
    root cause: a function whose stdout is a data channel (the caller does
    `remaining=$(try_auto_merge …)`) was being used as a place to print.
    (1) `task_git add` is a mutating verb, so `assert_data_worktree_clean`
    rejected it mid-rebase in **branch mode** — the framework's normal mode, and
    this repo's; (2) `|| true` discarded that rejection while still counting the
    file resolved and printing "Auto-merged"; (3) the merge driver's own stdout
    (`RESOLVED` / `PARTIAL:…`) was never redirected; (4) `iinfo` progress lines
    went to stdout in interactive mode. Combined, branch-mode auto-merge could
    never succeed (`CONFLICT:RESOLVED`), and the interactive loop opened
    `$EDITOR` on `RESOLVED`, on `Auto-merged: <file>` and on `PARTIAL:body`
    while **never offering the genuinely conflicted file**. All four fixed; the
    whole suite was blind to them because `tests/test_sync.sh` runs only in
    legacy mode (where the state guard is a no-op) and only asserted `CONFLICT:`
    as a substring.
  - **The `""` tombstone was defeated by the shell writer.** `write_task_file`
    emits board fields only when non-empty, and `echo "key: $v"` with an empty
    `v` produces `key: `, which the real YAML loader reads back as `None`. Fixed
    by emitting the quoted literal behind a `boardgroup_present` flag.
  - **Two of three `write_task_file` call sites are preservation paths.** They
    pass `$CURRENT_*` wholesale; omitting the new positionals there would have
    silently dropped `boardgroup` whenever a parent's child list changed or an
    interactive update ran.

- **Key decisions:**
  - **Base from git's conflicted index, not diff3 markers.** `merge.conflictStyle`
    is configured nowhere, so git emits 2-way markers and the parsed-then-discarded
    diff3 base is production-dead. `task_git show ":1:$f"` was measured working
    while the rebase is wedged (`show` is on the read-only allowlist). Uses `$f`
    (repo-relative), never `$file_path`.
  - **Fail closed.** Both-sides-changed-differently and no-base both go to
    unresolved/PARTIAL rather than a timestamp guess.
  - **Reject, never coerce, at the CLI**; and **preserve verbatim, never strip,
    at the boundary.** Group identity IS the slug, so any silent normalization
    coalesces distinct groups — which the design requires to be confirmed, never
    inferred. A quoted `"perf_work "` survives YAML with its space, so stripping
    would both silently join `perf_work` and read as unchanged from base.
  - **`AIT_GIT_SKIP_STATE_CHECK` scoped to one call**, rather than widening
    `_ait_git_subcmd_is_readonly` (weakens the guard repo-wide) or switching to
    `_ait_data_git` (whose contract is read-only probes + `task_push`).
  - **A failed stage is an unresolved merge**, reported immediately with its
    diagnostic preserved on stderr, instead of a success that cannot complete.

- **Upstream defects identified:**
  - `.aitask-scripts/board/aitask_merge.py:232-235 — anchor merges newer-wins on a task-wide, minute-resolution updated_at, so an unrelated edit on a stale checkout can win a field it never touched; the same causality weakness boardgroup avoids via base-aware detection. anchor could adopt _BASE_AWARE_FIELDS.`
  - `.aitask-scripts/aitask_update.sh:657-658 — write_task_file regenerates updated_at on EVERY write, so a --boardidx-only shell update records a semantic modification while the board's own layout write is deliberately timestamp-neutral; the two writers disagree about whether a pure layout move is a change.`

- **Notes for sibling tasks:**
  - Membership writes use `reload_and_save_board_fields(fields=("boardgroup",))`
    — there is **no** `semantic=True` bool. **t1243_11 must name
    `("boardgroup",)` only**; naming `boardidx` too would discard a concurrent
    move.
  - **Never read `boardgroup` raw.** Go through
    `board_groups.normalize_group_slug` — the persisted value can legally be
    `None`, a list (unhashable: it would crash a keyed derivation), an int or a
    bool, and `lib/task_yaml.py` deliberately leaves malformed input
    type-honest for the consumer.
  - **t1243_9/10:** `build_column_units(tasks)` returns `(slug, members)` in
    render order; `slug == ""` is a singleton. A one-member group **keeps its
    slug** so a group is never silently dissolved. `group_members(tasks, slug)`
    gets a collapsed group's members as data. `task_matches_filter` is already
    the data-level predicate — do not reimplement it.
  - **Grouping writes no index**, and `boardidx` contiguity is explicitly not an
    invariant. The two post-sync fixtures in `tests/test_board_groups.py` pin
    that no reconciliation write is needed.
  - **t1243_13 (docs)** inherits: every layer-5 surface, plus
    `website/content/docs/commands/sync.md`'s merge-rules table (needs a
    `boardgroup` row: base-aware, fails closed to PARTIAL) and the
    `aitask-trail` `SKILL.md.j2` + three goldens. **t1243_12** owns layer 3
    (`BoardGroupField`) and must normalize before calling the CLI, which rejects
    non-slug input.
  - **When writing a shell test for sync**, remember `try_auto_merge`'s stdout
    is a data channel: use `warn`/`iinfo_err`, never `info`/`iinfo`, inside it.
