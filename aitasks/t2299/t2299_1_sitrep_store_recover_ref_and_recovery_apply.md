---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [sitrep, crash_recovery]
gates: [risk_evaluated]
anchor: 2299
created_at: 2026-11-15 12:53
updated_at: 2026-11-15 12:53
---

## Context

First of four children of t2299 (sitrep: track crashed agents for resume). The parent's approved design keeps **one recovery item per task** in the sitrep store, under a stable task-based ref. Its evidence and category are updated in place, a done item reopens when the task crashes again, and dismissal is scoped to an *episode* (one claim attempt). This child adds the store-side support. The detector (t2299_2), refresh/TUI wiring (t2299_3) and skill/docs (t2299_4) build on it. The design record is the parent plan, `aiplans/p2299/` (read the child plan and the parent task t2299).

Facts from exploration (HEAD af0dca45c):

- **Writer split.** `lib/sitrep_todo.py` is the pure core: parse, validate, render, `--out`. `.aitask-scripts/aitask_sitrep_todo.sh` holds the mutex, `.bak`, `next_id`/`next_rev`, and the atomic rename (`mutate()`, sh:386-429). `@`-prefixed lines are wrapper directives.
- **Item model** (py:213-239): `num, rev, kind, state, group, checked_at, ref, derived, outcome, title`. There is ONE `ref`.
- **Vocabularies** (py:112-115). `KINDS=(task,action,question,watch)`; an unknown kind is a FormatError, which makes the whole store look damaged, so do NOT add a kind. `ORIGIN_KEYS` (py:132) is `{agent,task,commit,date,skill,pane}`.
- **Refs.** `normalize_ref` (py:575-590) accepts only `t<N>[_<M>]`, `proj#N`, and `push:<branch>@<sha>`. Dedup is by ref in ANY state (`_ref_owner` py:1000-1004, used by `op_add`).
- **Format.** `TODO_FORMAT_VERSION=2`, `TODO_READ_FORMATS=(1,2)`, `PUSH_REF_FORMAT=2` (py:79-98). A v1 file containing `push:` is refused (py:483-485). The first *changing* write upgrades the file (`_commit_todo` py:1029-1036). Line 2 is `<!-- aitask-sitrep todo format=N -->`.
- **Unguarded writes.** `upsert-context` (py:1195-1215) has no `--expect-rev`. `set-state` (py:1131) allows any transition, including dismissed→open. `set-state --batch` KEEPs dismissed items (`KEPT:c<N>|dismissed`).
- **Context format** (py:250-260, 363-430): `background` (≤400 chars, no `|`), `origin: k=v …`, `theme`, `sources` (`task|plan|trail|capture|commit|artifact|file|url`), `related`; ≤2000 bytes in total.

## Key files to modify

- `.aitask-scripts/lib/sitrep_todo.py`:
  - **Ref and kind:** `normalize_ref` accepts `recover:t<N>[_<M>]` (strict `t`, no other spelling). Add `parse_recover_ref(ref) -> task_id | None`. Bind the ref to `kind=task` in `_check_item_values` and `op_update`.
  - **Origin key:** `ORIGIN_KEYS += incarnation`, whose value is exactly 12 lowercase hex characters (validated in the context parser).
  - **Format:** `TODO_FORMAT_VERSION=3`, `TODO_READ_FORMATS=(1,2,3)`, `RECOVER_FORMAT=3`. A v1/v2 file that carries a `recover:` ref or an `incarnation` origin is refused (same shape as the PUSH_REF_FORMAT gate). The first changing write upgrades to 3.
  - **New verb `op_recovery_apply`**, described below.
- `.aitask-scripts/aitask_sitrep_todo.sh`: the verb's flag loop plus the header contract lines.
- `.aitask-scripts/lib/sitrep_refresh.py`: `select_targets` (:218-235) must NOT turn a `recover:` item into a `task` target. It returns no target for now; t2299_3 adds `check="recovery"`.
- **Ref-consumer inventory.** Grep `normalize_ref`, `_LOCAL_REF_RE`, `parse_push_ref`, `ref_owner`, `task_ref_id` (`sitrep_tui/sitrep_tui_model.py:1133`), `lib/sitrep_cli.py`, `lib/sitrep_corpus.py`, and `lib/sitrep_harvest.py` (`_known`, `ref_owner`). Each consumer must ignore or handle `recover:`. Record the inventory in the plan's Final Implementation Notes.

### Verb `recovery-apply` (one atomic commit under the writer mutex)

```
recovery-apply --ref recover:t<N> --expect-rev <R|absent> --incarnation <12hex> \
               --state open|unknown|done --outcome <T> [--title T] [--group G] \
               --checked-at now|<ts> [--context-file -]
```

Rules, enforced IN THE WRITER:

| Case | Result |
|---|---|
| `--expect-rev absent` and no item owns the ref | create (kind=task, derived=script) → `ADDED:c<N>\|<rev>`; a context is required |
| `--expect-rev absent` but an item exists | `STALE:c<N>\|<rev>` |
| rev mismatch | `STALE:c<N>\|<rev>`, nothing changes |
| the ref is not `recover:` | exit 2 |
| the given context's origin `incarnation` ≠ `--incarnation` | exit 2 |
| item open/unknown | apply every given field in one write → `APPLIED:c<N>\|<rev>`, or `UNCHANGED:c<N>\|<rev>` when nothing differs |
| item done, `--state open` | reopen → `REOPENED:c<N>\|<rev>` |
| item dismissed: recorded context incarnation == `--incarnation` | `KEPT:c<N>\|dismissed` (no write) |
| item dismissed: no recorded incarnation | `KEPT:c<N>\|dismissed_no_incarnation` |
| item dismissed: incarnation differs AND `--state open` AND a context is given | reopen and write the new context → `REOPENED` |
| a dismissed item and no context | always `KEPT` |

The state, outcome, checked_at, title, group and context land in ONE `_commit_todo`, so no interleaving can separate a reopen from its new incarnation.

## Reference patterns

- `PUSH_REF_FORMAT` gate plus the `push:` ref addition, the precedent for a format bump. Use `git log -S PUSH_REF_FORMAT` to find the task that added it.
- `op_set_state`, `op_update`, `_expect`, `_apply`, `Revs`.
- The `op_add` flags, parsed at py:1531-1538 and wrapped at sh:433-453.

## Fixtures

- `tests/fixtures/sitrep/store/`: move to format 3. Add one open `recover:` task item and one dismissed one, each with a context carrying `incarnation=`. Bump `next_id`/`next_rev` and regenerate `expected_list.txt`, `expected_context_c1.txt` (if affected) and `expected_check_sources.txt`.
- New `tests/fixtures/sitrep/store_v2/`: a copy of today's format-2 store.
- `store_v1/` stays.

## Verification

- `bash tests/test_sitrep_todo.sh`:
  - The full `recovery-apply` matrix: absent/create; open apply; unchanged; done→reopen; dismissed with the same key → KEPT; a new key → REOPENED with the new context written; no key → KEPT; a stale rev; a context key mismatch; a non-recover ref; the kind binding; a bad incarnation value.
  - A v2 file with a `recover:` ref → exit 4.
  - v2 reads as is and upgrades to 3 on its first changing write.
  - Fixture test 16 (plus a new 16c for v2).
  - The atomic-write property (an interrupted mutate leaves the old or the new file).
- `python3 -m pytest tests/test_sitrep_todo_format.py tests/test_sitrep_refresh.py` (round trip; the refresh exclusion).
- `shellcheck .aitask-scripts/aitask_sitrep_todo.sh`.
- Run the other sitrep suites that read the fixture (`tests/test_sitrep_corpus.py`, `tests/test_sitrep_tui_app.py`) and confirm they still pass.

## Notes

- Never `git restore`, `git stash` or checkout: the shared tree holds other crashed tasks' uncommitted hunks. Commit only this task's paths.
- `aidocs/framework/sitrep.md` is updated in t2299_4, not here.
