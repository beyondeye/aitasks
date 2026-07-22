---
Task: t1162_1_work_report_gatherer_helper.md
Parent Task: aitasks/t1162_add_manager_facing_work_report_skill_and_board_flow.md
Sibling Tasks: aitasks/t1162/t1162_2_work_report_codeagent_operation.md, aitasks/t1162/t1162_3_work_report_skill_and_wrappers.md, aitasks/t1162/t1162_4_board_w_work_report_flow.md, aitasks/t1162/t1162_5_work_report_documentation.md, aitasks/t1162/t1162_6_manual_verification_add_manager_facing_work_report_skill_and.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-07-22 14:12
---

# Plan: t1162_1 — Work-report gatherer helper + unit tests

## Context

t1162 adds a manager-facing `/aitask-work-report` skill and a board `w` flow.
Both consumers need the *same* deterministic view of "which parent tasks are in
which board columns, in board order" — the skill's interactive/arg paths
(t1162_3) and the board's reviewed-selection launch (t1162_4, which passes
`--columns` / `--tasks`). This child builds that report-input layer: an internal
whitelisted helper that reads board configuration + active parent tasks and
emits structured, validated, ordered records, plus a throughput signal so the
report can project when the selected work will land.

The hard requirement is **membership/order equivalence with the board** — the
board is the UI the user reviewed the selection in, so any divergence silently
produces a report about different tasks than the user picked.

Plan re-verified against current `main` on 2026-07-22 (verify path, no prior
verifications), then revised twice after review. **Design decisions** records
what verification found; D2, D3, D9, D10, D11 and D12 are *corrections to the
parent plan's pinned contract*, not restatements of it. D12 in particular
replaces the velocity model, so the parent plan and t1162_3 must be amended in
this same commit (see Implementation step 0).

## Files

1. **`aiplans/p1162_add_manager_facing_work_report_skill_and_board_flow.md`**,
   **`aitasks/t1162/t1162_1_*.md`**, **`aitasks/t1162/t1162_3_*.md`**,
   **`aiplans/p1162/p1162_3_*.md`** (amend) — propagate the D12 contract change
   (Implementation step 0). Task data → `./ait git`.
2. **`.aitask-scripts/board/aitask_board.py`** (modify, 1 line) —
   `TaskManager.get_column_tasks` gains an explicit secondary sort key (D2).
3. **`.aitask-scripts/aitask_work_report_gather.sh`** (new) — thin bash entry.
   Exact shape of `.aitask-scripts/aitask_stats.sh` (verified): `#!/usr/bin/env
   bash`, `set -euo pipefail`, resolve `SCRIPT_DIR`, source `lib/aitask_path.sh`
   **and** `lib/python_resolve.sh`, `PYTHON="$(require_ait_python)"`, then
   `exec "$PYTHON" "$SCRIPT_DIR/lib/work_report_gather.py" "$@"`. `chmod +x`.
4. **`.aitask-scripts/lib/work_report_gather.py`** (new) — implementation.
5. **`tests/test_work_report_gather.sh`** (new) — unit tests + the board
   equivalence test, modelled on `tests/test_query_files_inflight.sh` (mktemp
   tree + exported `TASK_DIR`, `tests/lib/asserts.sh`, own PASS/FAIL/TOTAL
   summary, exit 1 on failure).
6. **`tests/lib/work_report_equiv.py`** (new) — board-vs-gatherer equivalence
   oracle invoked from the test (D11).

Whitelisting the helper is **t1162_2's** job — not done here.

## PINNED output contract

Exit 0 for all validation outcomes; nonzero only for infrastructure/usage errors
(bad flag, malformed `--columns`/`--tasks`/`--now`/`--velocity-window` input,
unreadable or protocol-unrepresentable board config).

```
COLUMN:<col_id>|<title>
TASK:<col_id>|<task_id>|<boardidx>|<status>|<priority>|<effort>|<pending_children>|<remaining_items>|<task_file_path>
VELOCITY_MODEL:<model_id>|<window_days>|<start_date>|<end_date>|<model_label>
VELOCITY:<bucket_id>|<observed_units>|<completed_count>|<avg_per_unit>|<bucket_label>
PROJECTION:<remaining_total>|<projected_date>|<days_ahead>
PROJECTION:<remaining_total>|none|insufficient_data
ERROR:unknown_column:<id>
ERROR:unknown_task:<id>
ERROR:task_not_in_selected_columns:<id>
ERROR:task_order_changed:<canonical_csv>
NO_TASKS
```

At most one free-text field per record, always **last** (`<title>`,
`<task_file_path>`, `<model_label>`, `<bucket_label>`); consumers split on `|`
with maxsplit. `PROJECTION:` has no free-text field. Every fixed field is
pipe-free **by enforcement**, not by assumption — D9.

The `VELOCITY_MODEL:` / `VELOCITY:` rows are deliberately **model-agnostic**: a
consumer renders "per bucket: label, average, observed units" without knowing
which estimator produced them (D12/D13).

## Design decisions

**D1 — Reuse `board/task_yaml.py` instead of writing a local frontmatter parser.**
The parent plan hedged ("board-internal — prefer a `lib/`-level reuse or a small
local parser"). Verified: there is **no** `lib/`-level frontmatter reader
(`frontmatter_patch.py` is a line-editing tool for the gate ledger), and
`task_yaml.py`'s own docstring says it was *"Extracted from aitask_board.py for
reuse by aitask_merge.py and other tools."* — already a shared module with a
second consumer (`board/aitask_merge.py`). Import `parse_frontmatter` and
`BOARD_KEYS` from it: phantom-stub and frontmatter semantics become equivalent
to the board **by construction**, avoiding a fork of `_TaskSafeLoader`'s
`\d+_\d+`-stays-a-string resolver (`task_yaml.py:14-29`). Trade-off: a `lib/` →
`board/` import direction (see Risk / recorded mitigation).

**D2 — Give equal-`boardidx` ties an explicit, durable secondary order in the
board *and* the gatherer.** *(Correction — the parent plan proposed mirroring
glob order.)* `TaskManager.load_tasks` (`aitask_board.py:543-556`) fills
`task_datas` from `glob.glob(str(TASKS_DIR / "*.md"))` and `get_column_tasks`
(`:668-671`) stable-sorts by `board_idx` alone, so ties fall back to directory
enumeration order. **Verified empirically**: two tasks both at `boardidx: 10`
came back as `['t901_b.md', 't900_a.md']` — readdir order, not alphabetical.
That is not a durable contract between two separate processes, and any tie would
make the board-reviewed `--tasks` sequence spuriously trip
`ERROR:task_order_changed`. Fix — change the board to:

```python
return sorted(tasks, key=lambda t: (t.board_idx, t.filename))
```

and use the identical key in the gatherer. `filename` is the tie-break because
it is durable, unique among top-level files, and needs no id parsing (numeric
`t1000` vs `t99` ordering is irrelevant for a tie-break — this is disambiguation,
not ranking). User-visible effect: tied board cards now render alphabetically
instead of arbitrarily, and stop reshuffling when unrelated files are added or
removed. Pinned by the D11 equivalence test with a deliberate tie fixture.

**D3 — Reuse `stats_data.collect_stats(...)` as the completion-history seam,
with a date-only frozen-now.** `collect_stats` (`stats/stats_data.py:987`) scans
archived parents **and** children and returns `daily_counts: Counter[date, int]`
(`:1037`), resolving each date with `resolve_completion_date` (frontmatter
`completed_at`, `updated_at` fallback for Done, gate-ledger fallback). D12
computes its weekday averages from `daily_counts` — so the archive scan and date
resolution are reused wholesale, with no parallel scan and no reimplemented date
logic.
*Correction — the parent plan proposed `--now <YYYY-MM-DD[ HH:MM]>`.* Verified:
`collect_stats` subtracts `date` objects, and `datetime - date` raises
`TypeError: unsupported operand type(s)`. Coercing a timestamp to a date would
make the stated time component silently meaningless. So **`--now` accepts
`YYYY-MM-DD` only** (same for env `WORK_REPORT_NOW`); anything else is a usage
error. All windows are therefore whole-day.
**Constraint discovered:** `stats_data.TASK_DIR` is hardcoded `Path("aitasks")`
and does **not** honor the `TASK_DIR` env var; `_paths_for(project_root)`
(`:40-51`) rebases as `project_root / "aitasks"`. So pass
`project_root = task_dir().parent` when `task_dir().name == "aitasks"` (true for
the default and for tests using `TASK_DIR=$tmp/aitasks`), else `None`.
A `TASK_DIR` whose basename is not `aitasks` gets history from `./aitasks` —
a declared approximation carried as an explicit comment, not silent.

**D4 — "Known column" rule derived from the board renderer.** The board renders
`unordered` first *iff* it has ≥1 task, titled `Unsorted / Inbox`
(`aitask_board.py:4898-4905`; `cols = ["unordered"] if … else []` +
`column_order` at `:6182-6183`), then iterates `column_order` and **silently
drops** any id with no matching entry in `columns` (`:4907-4915`, `if conf:`).
Therefore `known = {"unordered"} ∪ [id for id in column_order if id has a
`columns` entry]`. `unordered` is always *requestable* via `--columns` (it just
contributes no rows when empty); only `--list-columns` gates it on having tasks.

**D5 — Fail-closed is staged.** Pipeline: parse/normalize/dedup → **columns
stage** → **task-membership stage** → **order stage** → emit. All errors within
the failing stage are emitted (in post-dedup input order); later stages do not
run because their inputs are undefined. No `COLUMN:`/`TASK:`/`VELOCITY*:`/
`PROJECTION:` line is ever emitted alongside an `ERROR:` line.

**D6 — `NO_TASKS` is a standalone sentinel.** A valid selection yielding zero
tasks emits `NO_TASKS` **instead of** any `COLUMN:` lines, still followed by the
velocity and projection block. (Empty column headings would render empty report
sections; one unambiguous "nothing to report" marker is what both consumers
want.) `--list-columns` is enumeration mode: `COLUMN:` lines only.

**D7 — Numeric formatting.** `avg_per_day` = `f"{value:.2f}"` with trailing
zeros and a trailing `.` stripped → `0`, `0.14`, `1.5`, `2`. Dates are ISO
`YYYY-MM-DD`.

**D8 — Non-int `boardidx` degrades to `0`** (the board would raise inside
`sorted`). Deliberate divergence where the board crashes; the D11 oracle does
not fixture that case.

**D9 — Delimiter safety is enforced on every field, not assumed.** *(Correction
— the parent plan asserted fixed fields were "pipe-free by construction", but
`col_id` comes from user-editable `board_config.json` and
`status`/`priority`/`effort` from user-editable YAML.)* Record-breaking
characters are `|`, CR and LF. Pinned policy by field class:

| Field | Source | Policy on `\|`/CR/LF |
|---|---|---|
| `--columns` / `--tasks` argv | caller | **Usage error, nonzero exit** — malformed input from the board/skill, never data |
| `col_id` | `board_config.json` | **Infrastructure error, nonzero exit** + stderr diagnostic — an identity field that must round-trip cannot be represented; already inside the pinned "invalid board config" clause |
| `status`, `priority`, `effort` | task YAML | **Safe coercion to the literal `invalid`** — one weird task must not block the whole report; `invalid` is pipe-free and unmistakable for a real enum value |
| `boardidx`, `pending_children`, `remaining_items`, all velocity/projection fields | derived ints, dates, fixed day names | pipe-free by construction (D7, D8, D10, D12) |
| `task_id` | filename regex `t(\d+(?:_\d+)?)_` | pipe-free by construction |
| `title`, `task_file_path` | config / filesystem | `\|` is **legal** (last field, maxsplit); CR/LF replaced with a single space so line framing survives |

Each row gets its own assert block.

**D10 — `children_to_implement` type policy.** *(New.)* Absent → leaf rules.
A list → `len(list)` (element types are never inspected). `None` (a bare
`children_to_implement:`) → treated as an empty list → `pending_children = 0`,
`remaining_items = 0`. **Any other type** (str, int, mapping) → the key is
**ignored and the task is treated as a leaf** (`pending_children = 0`,
`remaining_items = 0` if `Done` else `1`), with a warning to **stderr** (stdout
stays protocol-clean and the pinned `ERROR:` vocabulary is not extended). This
is the conservative answer — `len("t1_2")` would otherwise silently report 4
children, and `len(None)` would crash. Tested for `None`, `str`, and `dict`.

**D11 — Board equivalence is asserted in *this* task.** *(Correction — the
parent plan deferred equivalence entirely to t1162_4, so this task could have
shipped a gatherer that disagrees with the board and had consumers built on it.)*
The board is available as independent ground truth right here: verified that
`TaskManager` imports and constructs headlessly (no Textual app needed) once
`TASK_DIR` is set before import. t1162_4's test remains the higher-level
board-flow oracle; this one pins the data layer.

**D12 — Velocity is per-weekday throughput, and the gatherer computes the
projection.** *(Correction — the parent plan pinned
`VELOCITY:<window_days>|<completed_count>|<avg_per_day>` for fixed 7/30-day
windows. That single blended rate cannot express a work rhythm that differs by
weekday, which is what the projection actually needs.)*

- **Window:** the `W` calendar days ending at `--now` inclusive; `W` defaults to
  **90** and is overridable with `--velocity-window <days>` (positive int; else
  usage error).
- **`dow` model (default):** for each ISO weekday 1..7 (Mon..Sun),
  `observed_units` = how many dates of that weekday fall in the window,
  `completed_count` = sum of `daily_counts` over exactly those dates,
  `avg_per_unit = completed / observed_units`. Days with zero completions
  **stay in the denominator** — iterating the date range (not the Counter keys)
  is what makes that correct. All **seven** rows are always emitted, zeros
  included; `bucket_id` = `1`..`7`, `bucket_label` reuses `stats_data.DAY_NAMES`
  (`:53`) indexed by ISO weekday.
- **Projection** (model-independent — see D13): `remaining_total` =
  Σ `remaining_items` over the emitted `TASK:` rows. Walk forward from `--now`
  **inclusive**, subtracting `estimate.rate_for(day)`; the first day the running
  remainder reaches ≤ 0 is `<projected_date>`, and `days_ahead` =
  `(projected_date - now).days`.
  - `remaining_total == 0` → `PROJECTION:0|<now>|0`.
  - every bucket average is 0 → `PROJECTION:<n>|none|insufficient_data`.
  - walk bounded at **3650 days** (10 years); exceeding it →
    `PROJECTION:<n>|none|insufficient_data`. Pinned with an at-bound and an
    over-bound test.

  Worked example (the pinned semantics): today Sunday, `remaining_total` 25,
  Sun avg 10, Mon avg 20 → Sunday leaves 15, Monday leaves −5 → projected
  Monday, `days_ahead` 1.

**D13 — The estimator is a swappable seam, proven by shipping two models.**
*(New — requested in review.)* The velocity model must be replaceable without
touching emission or projection, so the dependency between them is narrowed to a
single primitive:

```python
@dataclass(frozen=True)
class VelocityBucket:
    bucket_id: str          # pipe-free, model-defined ("1".."7", "all", …)
    observed_units: int     # denominator — how many units were observed
    completed_count: int    # numerator
    avg_per_unit: float
    bucket_label: str       # free text, emitted LAST

@dataclass(frozen=True)
class VelocityEstimate:
    buckets: list[VelocityBucket]
    def rate_for(self, day: date) -> float: ...   # expected completions on `day`

class VelocityModel(Protocol):
    model_id: str
    model_label: str
    def estimate(self, daily_counts: Counter, now: date, window_days: int) -> VelocityEstimate: ...
```

`rate_for(day)` is the **only** thing the projection walk consumes, and the walk
lives in the caller — so a model supplies *rates*, never *policy* (no model
decides the bound, the ≤ 0 stop condition, or the `insufficient_data` rule).
Emission is equally generic: it renders `buckets` verbatim. Swapping a model
therefore touches one class and one registry entry:

```python
VELOCITY_MODELS = {"dow": DayOfWeekVelocity(), "flat": FlatVelocity()}
```

selected by `--velocity-model <id>` (default `dow`; unknown id → usage error
listing the registered ids).

**Two models ship, so swappability is demonstrated rather than asserted.** The
second, `flat`, is the parent plan's original blended rate preserved as a
selectable option: a single bucket (`bucket_id` = `all`, label `All days`) with
`observed_units` = `W` and `avg_per_unit` = window completions ÷ `W`; its
`rate_for` returns that same value for every day. The test suite runs the full
CLI under **both** models and asserts each produces correct rows and a correct
projection through the identical emission/projection path — a real second
implementation is a stronger seam proof than a mock, and costs ~15 lines.

## Implementation

### Step 0 — Propagate the D12 contract change (same commit)

The old `VELOCITY:` shape is pinned in four places that siblings read as source
of truth. Amend each to the D12 contract before/alongside the code:

- `aiplans/p1162_…board_flow.md` — the contract block (`:95`), the velocity
  rules (`:126`, `:133`), the t1162_1 test list (`:174-177`), and the t1162_3
  projection AC (`:246`, `:256`).
- `aitasks/t1162/t1162_1_…md` — contract block (`:34`), velocity bullet
  (`:50`), verification list (`:55`).
- `aitasks/t1162/t1162_3_…md` `:32` — the PINNED projection AC currently says
  *"throughput = `avg_per_day` (prefer 30-day window; mention 7-day when notably
  divergent); projected days ≈ items ÷ rate"*. Rewrite: the gatherer now emits
  the projection directly (`PROJECTION:`), so the skill **reports** it rather
  than computing it; the skill renders `VELOCITY:` rows generically (per bucket:
  label, average, observed units) and must **not** hardcode weekday semantics,
  since the model is selectable (D13); `insufficient_data` means "insufficient
  completion history for a projection" — never fabricate a rate.
- `aiplans/p1162/p1162_3_…md` `:89` — same zero-velocity wording.

Commit task/plan data with `./ait git`, separately from code.

### `lib/work_report_gather.py`

Module bootstrap (mirrors the `stats_data.py:19-24` idiom): insert
`<scripts>/board` and `<scripts>/stats` into `sys.path` (its own `lib/` dir is
already `sys.path[0]` when run as a script), then
`from config_utils import load_layered_config, task_dir, metadata_dir`,
`from task_yaml import parse_frontmatter, BOARD_KEYS`,
`from stats_data import collect_stats, DAY_NAMES`.

- **CLI** (`argparse`): `--list-columns` (mutually exclusive with the pair
  below), `--columns <csv>` (required otherwise), `--tasks <csv>` (optional),
  `--now <YYYY-MM-DD>` (env `WORK_REPORT_NOW`, then today),
  `--velocity-window <days>` (default 90), `--velocity-model <id>` (default
  `dow`). Usage violations and D9 input violations → nonzero exit.
- **Board config:** `load_layered_config(str(metadata_dir() / "board_config.json"),
  defaults={"columns": DEFAULT_COLUMNS, "column_order": DEFAULT_ORDER})` with the
  board's literals (`aitask_board.py:134-139`) copied as the defaults.
- **Id normalization:** strip a leading `t`; dedup preserving first occurrence.
- **Membership scan:** `glob.glob(str(task_dir() / "*.md"))` → for each,
  `parse_frontmatter(text)`; `None`/parse failure → `metadata = {}`; skip when
  `not metadata or set(metadata) <= set(BOARD_KEYS)` (phantom stub, mirroring
  `_is_phantom_stub`). `boardcol` default `"unordered"`, `boardidx` default `0`
  (verified `aitask_board.py:269-283`). No status filter; no archived, no
  children. Sort by `(boardidx, filename)` per D2.
- **Fields:** `status`/`priority`/`effort` default to `unknown` when absent, then
  D9-coerced; `pending_children` / `remaining_items` per D10 and the leaf rule.
- **Validation** per D5; `task_order_changed` compares the post-dedup `--tasks`
  sequence against the canonical order restricted to those ids, reporting
  `<canonical_csv>` as bare ids.
- **Velocity / projection** per D12–D13: `collect_stats(now, 1,
  project_root).daily_counts` → `VELOCITY_MODELS[model_id].estimate(...)` →
  generic emission of `estimate.buckets` → the projection walk over
  `estimate.rate_for(day)`. Keep the three concerns (`VelocityBucket` /
  `VelocityEstimate` / models, the emitter, the walk) in clearly separated
  sections of the module so the seam is visible in the source.
- **Emission order:** `COLUMN:` lines (selected, canonical order) → `TASK:` lines
  grouped by column in that order → `VELOCITY_MODEL:` → the model's `VELOCITY:`
  rows → `PROJECTION:`.

### `tests/lib/work_report_equiv.py` (D11 oracle)

1. Puts `.aitask-scripts/board` + `.aitask-scripts/lib` on `sys.path`, builds
   `TaskManager()`, collects `{col_id: [filename, …]}` from `get_column_tasks`
   for `unordered` + every configured column.
2. Runs **the real CLI** (`aitask_work_report_gather.sh --columns <all>`) via
   `subprocess`, parses `TASK:` lines with maxsplit, takes each row's
   `basename(task_file_path)`.
3. Prints `EQUIV_OK` on an exact per-column list match, else a readable diff and
   a nonzero exit.

Fixture tree exercises: a deliberate `boardidx` tie (pins D2 in both
implementations at once), a phantom stub, a task with no `boardcol` (→
`unordered`), a `Done` task (no status filter), a child under `aitasks/t<N>/`
and a file under `aitasks/archived/` (both excluded), and a non-default
`column_order`.

### `tests/test_work_report_gather.sh`

Isolated tree per test: `mktemp -d`, `export TASK_DIR="$tmp/aitasks"`, write
`metadata/board_config.json` + task fixtures, plus archived fixtures under
`$TASK_DIR/archived/` and `$TASK_DIR/archived/t<parent>/` for history. Python
resolved by sourcing `lib/python_resolve.sh` (the same seam the entry script uses).

Assert blocks: ordering across 2+ columns; ascending `boardidx`; **tie-break
determinism (D2)**; subset `--tasks`; `t`-prefix normalization; duplicate dedup;
unknown column / unknown task / moved task (exact `ERROR:` lines **and** absence
of every non-`ERROR:` line kind); non-canonical `--tasks` order →
`ERROR:task_order_changed:<canonical>`; `--list-columns` with and without
Unsorted tasks and with an orphan `column_order` id; `unordered` requested
explicitly; **D9 delimiter table — one block per row**; **D10 —
`children_to_implement` as `None` / `str` / `dict`**; remaining-work semantics
(Done leaf → 0, `[]` → 0, 3 pending → 3, active leaf → 1); phantom-stub
exclusion; **D12 (`dow`)** — exactly seven `VELOCITY:` rows in Mon..Sun order; a
zero-completion weekday still counted in `observed_units`; a completion just
inside vs just outside the window; `--velocity-window` override changes
`observed_units`; the **worked example reproduced end-to-end** (Sunday `--now`,
25 remaining, Sun/Mon fixtures → `PROJECTION:25|<monday>|1`); `remaining_total
0` → `PROJECTION:0|<now>|0`; zero history → all-zero buckets +
`insufficient_data`; the 3650-day bound at-bound and over-bound; a non-date
`--now` and a non-positive `--velocity-window` → nonzero; empty selection →
`NO_TASKS` + velocity block; **`EQUIV_OK` from the D11 oracle**.

**D13 seam blocks:** the *same* fixture tree run under `--velocity-model flat`
yields exactly one `VELOCITY:all|…` row and a projection consistent with the
flat rate, while every `COLUMN:`/`TASK:` line is byte-identical to the `dow`
run — proving the model is the only thing that varies. Plus:
`VELOCITY_MODEL:<id>|…` echoes the selected model in both runs; an unknown
`--velocity-model` exits nonzero and lists the registered ids; and a model whose
`bucket_id` contains `|` is rejected by the D9 fixed-field enforcement.

**Harness self-check** (per `feedback_prove_test_harness_can_fail`): before
finishing, temporarily corrupt one expectation and confirm the suite prints
`FAIL:` and exits `1`, then revert.

## Verification

- `bash tests/test_work_report_gather.sh` — all PASS, exit 0 (includes the D11
  board equivalence assertion).
- Harness-can-fail check above.
- `shellcheck .aitask-scripts/aitask_work_report_gather.sh` — clean.
- Board regression from D2: run the existing `tests/test_board_*.py` suite
  (13 files, e.g. `test_board_empty_column_focus.py`, `test_board_view_filter.py`,
  `test_board_topic_view.py`) and confirm no regression from the
  `get_column_tasks` key change.
- Live sanity on the real repo: `./.aitask-scripts/aitask_work_report_gather.sh
  --list-columns`, then `--columns now`, compared against what `ait board` shows;
  sanity-check the weekday averages against `ait stats`.

## Risk

### Code-health risk: medium
- `lib/work_report_gather.py` imports from `board/task_yaml.py` (D1) and
  `stats/stats_data.py` (D3), inverting the layer direction — `lib/` is the
  shared base layer and would now depend on two higher-level packages, so
  moving or renaming either module silently breaks the gatherer ·
  severity: medium · → mitigation: promote_task_yaml_to_lib
- D2 modifies `TaskManager.get_column_tasks`, a load-bearing board path, so the
  change reaches the live TUI and not just the new helper. Blast radius is one
  sort key and the effect is strictly more deterministic, but tied cards visibly
  reorder once · severity: low · → mitigation: covered by the D11 tie fixture
  and the board test run in Verification
- Everything else is a pure addition: no other existing code file is modified ·
  severity: low · → mitigation: none

### Goal-achievement risk: medium
- D12 changes a contract three sibling tasks already pin. If Implementation
  step 0 is skipped or partial, t1162_3 will be built against a `VELOCITY:`
  shape the gatherer no longer emits · severity: medium ·
  → mitigation: step 0 is in-scope and lands in the same commit; the grep list
  in step 0 names every current reference
- The crux requirement (board membership/order equivalence) is now asserted
  in-task against the board itself (D11) rather than deferred to a sibling, and
  is satisfied by construction — same `glob`, same parser, same phantom-stub
  predicate, same sort key · severity: low · → mitigation: none
- A 90-day window gives ~13 samples per weekday; a project with sparse or
  bursty history will produce a jumpy projection. Mitigated by reporting
  `observed_days` alongside every average so the consumer can judge confidence,
  and by `--velocity-window` · severity: low · → mitigation: none (accepted)

### Planned mitigations
- timing: after | name: promote_task_yaml_to_lib | type: refactor | priority: medium | effort: low | addresses: code-health — lib/→board/ import inversion | desc: Move board/task_yaml.py to lib/task_yaml.py and update its importers (board/aitask_board.py, board/aitask_merge.py, lib/work_report_gather.py) so the shared base layer no longer depends on board/.

## Step 9 reference

Post-implementation: merge/cleanup + archival per task-workflow Step 9.
