---
Task: t2194_fix_agent_picker_recent_window_and_top_used_list.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2194 — Date-correct "recent" windows, batch-review → review, Top used (all ops)

## Context

The agent/model picker (`AgentModelPickerScreen`, `.aitask-scripts/lib/agent_model_picker.py`)
shows stale or empty "recent" lists. There are three reasons:

1. **"Recent" ignores today.** `_recent_aggregate()` adds the stored `month` and
   `prev_month` buckets without comparing their `period` to today. A bucket rolls over
   only when a writer records the *next* run for that model+op, so an unused model keeps
   counting forever. For example, `opus4_8` shows "262 runs recent" from 2026-07/06 data.
   The same flaw is in `_format_op_stats` ("N this mo" / "N prev mo"), in settings
   `_aggregate_verifiedstats`, in `stats_data.recent_aggregate` (a documented copy), and
   in the month/prev_month/week/recent windows of `load_verified_rankings` /
   `load_usage_rankings`, which feed `ait stats` and the stats TUI.
2. **`batch-review` never matches its counters.** The codeagent op key is `batch-review`,
   but aitask-review records under `skill_name: "review"`.
3. **"Top verified" is useless.** Only skills that run the Satisfaction Feedback
   procedure record anything, and every score in this repo is 100, so ties fall back to
   alphabetical order. The user decided to replace it with **"Top used models (recent,
   all ops)"**.

Writers (`aitask_usage_update.sh`, `aitask_verified_update.sh`) stamp `period` as
`date +%Y-%m` (local time) and `date +%G-W%V` (ISO-8601 week, Monday start, ISO year).
On roll-over they move `month` → `prev_month` only when the old month is exactly the
previous month.

With the fix and today's real data (2026-11-04), the recent window holds only
`opus5_5`: pick 16+276, plus changelog/wrap/explore in an unrolled 2026-10 `month` slot.
Every other model's buckets are from 2026-09 or older. That is the correct answer.

## Decisions

- **One shared helper module**: `.aitask-scripts/lib/model_stats_windows.py`, stdlib
  only. It removes both copies of the recent-sum logic and gives t1912's planned "shared
  read path" something to reuse.
- **batch-review fix is reader-side.** A `STATS_KEY_BY_OPERATION = {"batch-review":
  "review"}` map plus `stats_key_for_operation(op)`. Changing the recorded key instead
  would orphan existing `review` history and need skill edits across 3 agent trees plus
  goldens. The map applies only to readers that look counters up **by codeagent
  operation**: the picker and the settings Agent Defaults labels / non-default list.
  Readers keyed by the *recorded* skill name stay unmapped and keep labelling by skill
  (`stats_data` rankings, the Models tab, `ait codeagent list-models`). The picker's
  dismiss `key` stays the operation (`batch-review`); only stats lookups use the mapped key.
- **No verified scores in the two top lists.** They rank by usage. Scores stay in the
  per-agent lists, the settings Agent Defaults tab and the Models tab. Reason: every
  recorded score is 100, so a score carries no information in a ranked list.
- **Week convention = ISO** (`date.isocalendar()` → `YYYY-Www`), matching the writers.
  This is unrelated to `stats_data`'s configurable `week_start_dow`, which only drives
  task-completion charts.
- **Injectable "today"**: every new or changed reader takes `today: date | None = None`,
  meaning `date.today()`. Tests always pin it.

## Coordination (shared file)

`.aitask-scripts/settings/settings_app.py` carries **uncommitted hunks of in-flight
t2175_4** (sitrep). These are the three lines
`"sitrep": "Model used for the sitrep steward agent`,
`Valid skills: pick, fold, review, pr-import, revert, explore, pickrem, pickweb, qa, shadow, brainstorm-discuss, sitrep.`
and `"brainstorm-discuss", "sitrep",`. The pre-phase gate below governs it.

**"Clean" always means clean vs HEAD, staged and unstaged alike:**
`git diff --quiet HEAD -- <file>`. Plain `git diff --quiet -- <file>` compares the
worktree with the index, so it misses changes another session has staged. Every other
target file is clean vs HEAD today.

**Edit guard: a last-accepted-state chain for every target file `P`.** It lives in a
scratch helper, `<scratch>/edit_guard.sh` (not in the repo). State per path is kept as
`<scratch>/guard/<P with / → __>.{head,sha}`. Any non-zero exit → stop and report;
never write or commit through it.
- `begin P` runs once, before my **first** write to `P`.
  - A tracked file must be clean vs HEAD (`git diff --quiet HEAD -- P`).
  - A new file must be absent and untracked (`! git ls-files --error-unmatch -- P`).
  - It records `head = git rev-parse -q --verify HEAD:P` (or `NONE`) and
    `sha = sha256sum P` (or `ABSENT`).
- `check P` runs before **every later** write and before the commit. It does not
  compare with HEAD, because the file differs from HEAD by design once I have edited
  it. It requires all three:
  - the current `sha256sum P` equals the recorded `sha`: nobody wrote since my last
    accepted write;
  - `git rev-parse HEAD:P` equals the recorded `head`: nobody committed `P` in between;
  - `git diff --cached --quiet -- P`: nothing staged there.
- `accept P` runs right after each of my writes and records the new `sha`. It also
  runs after a deliberate correction following a test run.
- Together these prove that at commit time `git diff HEAD -- P` is exactly my own
  accepted edits. That replaces any after-the-fact snapshot, which would silently
  absorb a concurrent write landing *between* two of my edits.
- Commit order: `check` every path, then `git add` the new files only, then
  `git commit -F - -- <paths>`.
- Residual: the sub-second window between one of my writes and its `accept`.
  Claude's Edit tool also refuses a file modified since it was last read.

### Pre-phase (risk mitigations)
1. [gate_settings_app_on_t2175_4] Do steps 1–4 and 6–7 first. Right before the first
   `settings_app.py` edit (step 5), require **both**:
   - (a) `edit_guard.sh begin .aitask-scripts/settings/settings_app.py` succeeds: clean
     vs HEAD, so no staged or unstaged change by anyone;
   - (b) the **actual handover**: `git show HEAD:.aitask-scripts/settings/settings_app.py`
     contains all three t2175_4 lines above verbatim (`grep -qF` each). Record the
     commit that introduced them (`git log -S'"brainstorm-discuss", "sitrep",' --format='%h %s' -- <file>`)
     in the plan.

   A commit merely touching the file does not count. From then on, `settings_app.py`
   follows the normal edit-guard chain: `check` before every later write, `accept` after
   each write. My own pending edits therefore pass, and any foreign write, staging or
   commit is caught.

   If (a) or (b) still fails once everything else is done, stop and ask the user: wait,
   or agree the explicit fallback (temp-index commit of my hunks only, then an
   isolated-worktree test of the committed tree against a parent-commit control).

## Implementation

### 0. Edit guard (scratch only)
- Write `<scratch>/edit_guard.sh` (`begin|check|accept <path>…`, `set -euo pipefail`,
  run from the repo root).
- Self-test it in a throwaway `git init` repo under the scratchpad:
  - `begin` → edit → `accept` → `check` passes;
  - `check` fails on a foreign worktree write, a foreign `git add`, and a foreign commit
    of the file;
  - `begin` fails on a staged-only change.

  Only then use it on the real targets.

### 1. New `.aitask-scripts/lib/model_stats_windows.py`
Module docstring states the contract: buckets roll over only on the next write, so a
reader counts a bucket toward a window only when its `period` equals that window's
period computed from today.
```python
STATS_KEY_BY_OPERATION: dict[str, str] = {"batch-review": "review"}
def stats_key_for_operation(operation: str) -> str   # identity when unmapped

class Periods(NamedTuple): month: str; prev_month: str; week: str
def current_periods(today: date | None = None) -> Periods
    # month f"{y:04d}-{m:02d}"; prev = previous calendar month (Jan → Dec of y-1);
    # week f"{iso_year:04d}-W{iso_week:02d}" from today.isocalendar()

def resolve_windows(buckets, today=None) -> dict[str, dict]
    # -> {"month", "prev_month", "week": {"period": <current>, "runs", "score_sum"},
    #     "recent": {"runs", "score_sum"}}   (recent = month + prev_month)
    # month      = stored month       iff its period == P.month
    # prev_month = FIRST of (stored prev_month, stored month) whose period == P.prev_month
    #              (never both, so no double count)
    # week       = stored week        iff its period == P.week
    # missing/empty/non-str period, non-dict bucket, old flat format -> zeros
    # runs/score_sum: non-bool int only, else 0. Output is idempotent under re-resolve.
def recent_aggregate(buckets, today=None) -> tuple[int, int]   # from resolve_windows
```

### 2. `.aitask-scripts/lib/stats_data.py`
- Delete the local `recent_aggregate` and its "duplicated rather than extracted"
  docstring. Import it from `model_stats_windows` instead; the name stays exported, so
  the `aitask_stats.py` re-export keeps working.
- `load_verified_rankings(project_root=None, today=None)` and
  `load_usage_rankings(project_root=None, today=None)`: store
  `{"all_time": …, **resolve_windows(buckets, today)}` per (model, op). Per-provider
  `month`/`prev_month`/`week`/`recent` entries then read the resolved windows directly.
- All-providers aggregation: sum the resolved windows. Every resolved window already
  shares today's period, so delete the "first-seen period wins" grouping. That logic
  dropped a provider whenever two providers held different month periods.
- Update the `load_usage_rankings` docstring ("recent is synthesized from month +
  prev_month" → date-correct).

### 3. `.aitask-scripts/aitask_stats.py`
`main()`: `load_verified_rankings(today=today)`, so the CLI report uses the same `today`
as the rest of the report. The stats TUI pane (`stats/panes/agents.py`) keeps calling
with no args, i.e. the wall clock.

### 4. `.aitask-scripts/lib/agent_model_picker.py`
- Delete `_recent_aggregate` and the unused `_recent_avg`. Import `resolve_windows`,
  `recent_aggregate` and `stats_key_for_operation`.
- `_format_op_stats(buckets, compact=False, today=None)`: take the "this mo" / "prev mo"
  counts from `resolve_windows`. The output format is otherwise unchanged.
- `AgentModelPickerScreen`:
  - Add the class attribute `_today: date | None = None`, plus `__init__(..., today=None)`
    and a property `stats_key` → `stats_key_for_operation(self.operation)`. The class
    default keeps the task's `__new__`-based repro snippet working.
  - `_MODES` → `("top_all_ops", "Top used models (recent, all ops)")`,
    `("top_usage", "Top by usage (recent, this op)")`, then `all`, `codex`, `opencode`,
    `claudecode` unchanged. Update the module and class docstrings.
  - Replace `_build_top_verified` / `_build_options_top` with `_build_top_all_ops` /
    `_build_options_top_all_ops`:
    - Per non-unavailable model, `total = Σ recent_aggregate(b, today)[0]` over every
      `usagestats` op, and `op_runs` = the recent count under `self.stats_key`.
    - Skip models with `total <= 0`. Sort `(-total, agent, name)` and keep the top 5.
    - Detail: `"{total} runs recent, all ops"`, plus `" · {op_runs} this op"` when
      `op_runs > 0`.
  - `_build_top_usage`: look up `self.stats_key`; recent count from
    `recent_aggregate(b, self._today)`. Detail format unchanged.
  - `_build_options_for_agent`: use `self.stats_key` for the `verifiedstats` and
    `verified` lookups, and pass `today=self._today` to `_format_op_stats`.
  - **Empty states: short placeholder row + separate wrapping hint.** `FuzzyOption` is
    `height: 1`. A probe confirmed that a long placeholder row is clipped both narrow
    (36-col row at 40 cols) and wide (72-col row at 120 cols), so the explanation never
    shows. Instead:
    - **Placeholder rows** (fit one row; ≤ 33 cols with the 4-col prefix):
      - all ops: `"(no recent usage)"`
      - this op: `"(no recent usage for this op)"`
    - **New hint label** inside `#picker_dialog`, after `#picker_step_label` and before
      the FuzzySelect: `Label("", id="picker_empty_hint")`.
      - CSS: `#picker_empty_hint { width: 100%; height: auto; padding: 0 0 1 1; color: $text-muted; display: none; }`.
      - `_apply_mode` sets its text and `display` from `_empty_hint_for_mode(mode_key)`
        only when the built options are the lone placeholder (`value == ""`), and hides
        it otherwise.
      - Hint texts:
        - this op: "Nothing recorded for this op this month or last month. Only skills
          that run satisfaction feedback record usage, so ops such as raw, shadow and
          discuss stay empty here."
        - all ops: "Nothing recorded for any op this month or last month."
      - A second probe showed this label inside the dialog wraps to fit and shows every
        word at 30, 40 and 120 cols.
  - Placeholders: "Type to filter top-used models (all ops)..." and "...(this op)...".
  - `on_fuzzy_select_selected`: match `("top_all_ops", "top_usage", "all")`.
  - `_placeholder_for_mode` / `_build_options_for_mode`: rename the `top` branch.

### 5. `.aitask-scripts/settings/settings_app.py` (gated, see pre-phase)
- Import `resolve_windows` and `stats_key_for_operation`.
- `_aggregate_verifiedstats(all_models, target_cli_id, today=None)`: per provider,
  resolve windows and **sum** month / prev_month / week into result buckets stamped with
  the current periods. This replaces the first-seen-period logic and adds `prev_month`,
  so the all-providers summary can show "prev mo". Update the docstring.
- `_get_verified_label` / `_get_all_providers_label`: look up
  `stats_key_for_operation(operation)` (verifiedstats + flat `verified`).
- `_collect_non_default_skill_stats`: add
  `{stats_key_for_operation(k) for k in default_keys}` to `default_keys`, so `review`
  (now shown under batch-review) is not listed again as a "skill without defaults".

### 6. Tests (all pin `today`)
- **New `tests/test_model_stats_windows.py`**:
  - `current_periods` for 2026-11-04 (`2026-11`/`2026-10`/`2026-W45`), 2026-01-15 (prev
    `2025-12`) and 2027-01-01 (`2026-W53`, ISO year ≠ calendar year).
  - A writer-parity check against `date -d <d> +%G-W%V` for those dates, skipped
    unless GNU date is available.
  - `resolve_windows`: current month counts; a stored `month` from last month lands in
    `prev_month`; a stored `prev_month` matching counts; stale (months-old) month+prev →
    zeros; missing/empty period → zeros; week only when the ISO week matches; non-dict
    and old flat format → zeros; both slots claiming the previous period → counted once;
    idempotent under re-resolve.
  - `recent_aggregate`; `stats_key_for_operation` (batch-review→review, identity otherwise).
- **Rewrite `tests/test_agent_model_picker.py`** with a pinned 2026-11-04 fixture:
  - A stale model (2026-07/06, 262 runs) appears in neither top list.
  - A model with an unrolled 2026-10 `month` slot counts as recent.
  - A model used across pick+explore+wrap (7 total) ranks above one with 6 pick runs in
    all-ops; the order flips in this-op `pick`.
  - Unavailable models are excluded; exact detail strings.
  - `raw`: the all-ops list is populated and the this-op list shows the explanatory
    empty state.
  - `batch-review` finds `review` usage. A per-agent list (patched `MODEL_FILES` to a temp
    json) shows the `review` score.
  - `on_fuzzy_select_selected` (stubbed `dismiss`) returns `key == "batch-review"` and
    `value == "agent/name"` for `top_all_ops`.
  - `_format_op_stats` drops stale "this mo" and shows last month's slot as "prev mo".
  - `_MODES` keys order.
- `tests/test_agent_model_picker_narrow.py`:
  - Update the stale `# top -> top_usage` comment (index order is unchanged).
  - Let `_PickerHost` take `operation` / `all_models` / `today`.
  - **Add empty-state visibility tests** at narrow (40×50, `narrow=True`) and wide
    (120×40). Fixture: operation `raw`, plus one model with current `pick` usage at a
    pinned today. After one `action_next_list()` to `top_usage`:
    - `#picker_empty_hint` is displayed and its region lies inside `#picker_dialog`'s region.
    - At narrow, its height is ≥ 2 (it wrapped).
    - **Every word** of the hint text appears in the exported screen text (an
      `export_screenshot()` SVG → text-token set; per-word, because wrapping splits phrases).
    - The placeholder row's `len("    " + display) <= row.region.width` (not clipped).
  - Negative control on the same host: on `top_all_ops` (populated by the pick model),
    the hint is **not** displayed.
- **`tests/test_aitask_stats_py.py`** `TestVerifiedRankings`:
  - Pass `today=date(2026, 3, 5)` wherever window content is asserted
    (`test_all_providers_aggregation_month`, render tests).
  - Add: stale buckets at today=2026-11-04 → month/prev_month/week/recent empty while
    all_time is intact.
  - Add: today=2026-04-02 → the stored 2026-03 `month` appears in `prev_month`/`recent`,
    not `month`.
  - Add: cross-provider mixed periods (codex 5.3 month 2026-03, opencode 5.3 month
    2026-04, today 2026-04) → month=1 (opencode), prev_month=1 (codex), recent=2.
  - Add a `TestUsageRankings` with one stale and one current model.
- **`tests/test_stats_data.sh`**: add one block asserting
  `stats_data.recent_aggregate is model_stats_windows.recent_aggregate` and that
  `agent_model_picker` no longer defines `_recent_aggregate`. Add one stale-bucket
  `load_usage_rankings(<tmp root>, today=…)` case.
- **New `tests/test_settings_verifiedstats_windows.py`** (gated with step 5):
  - `_aggregate_verifiedstats` with one stale and one current provider → only the
    current one in month/prev/week; all_time sums both.
  - `_get_verified_label` / `_collect_non_default_skill_stats` via a `SimpleNamespace`
    self → batch-review shows `review` stats, and `review` is not in the non-default list.

### 7. Docs (current-state only)
- `website/content/docs/tuis/settings/_index.md`:
  - Replace the stale "Top Verified … Browse all models" paragraph with the six lists
    (top used all ops, top by usage this op, all, per-agent with scores; Shift+←/→
    cycles).
  - Note that "this mo"/"prev mo" count only the current and previous calendar month.
- `website/content/docs/tuis/settings/reference.md`:
  - Buckets table: add `prev_month`; replace "resets when the month changes" with the
    roll-on-next-write + read-against-today rule; one line saying `usagestats` uses the
    same buckets with `runs` only.
  - Aggregation step 4: "sum each provider's buckets resolved against today".
  - Line 266: drop the "model picker (Top Verified ranking)" mention.
- `website/content/docs/skills/verified-scores.md`:
  - Time Windows table: same `prev_month` row and read rule; aggregation step 4.
  - "Where Scores Appear": the picker's top lists rank by recent usage and scores show in
    its per-agent lists; `batch-review` reads the counters recorded by `aitask-review`
    (`review`).
- `aidocs/framework/adding_a_new_codeagent.md`: update the `_MODES` snippet.
- Then: `cd website && python3 check_links.py --build`.

### 8. Step 9 (Post-Implementation)
Current-branch profile: no merge. Archive via `aitask_archive.sh 2194` per task-workflow
Step 9. Commit code by explicit paths only, after `edit_guard.sh check` passes for every path.
`settings_app.py` goes in only after the pre-phase gate.

## Verification
- `~/.aitask/venv/bin/python -m pytest tests/test_model_stats_windows.py tests/test_agent_model_picker.py tests/test_agent_model_picker_narrow.py tests/test_aitask_stats_py.py tests/test_settings_verifiedstats_windows.py -q`
- `bash tests/test_stats_data.sh && bash tests/test_stats_verified_rankings.sh && bash tests/test_no_lib_to_tui_import.sh`
- Full suite: `set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -3`. Read the
  last line for the verdict.
- The task's reproduction snippet (renamed builders) against the real repo:
  - expect `pick`/`raw`/`shadow` all-ops → `claudecode/opus5_5` "307 runs recent, all ops · 292 this op" (pick).
  - expect `pick` this-op → opus5_5 "292 runs recent · 313 all-time".
  - expect `raw`/`batch-review` this-op → empty state.
  - expect no `opus4_8` / `opus5` anywhere.
- `./.aitask-scripts/aitask_stats.sh` exits 0, and its "This month" column shows only 2026-11 data.
- `shellcheck` is not affected (no shell edits).

## Risk

### Code-health risk: medium
- `settings_app.py` is shared with in-flight t2175_4's uncommitted hunks. Path-scoped
  commits by either session would absorb the other's edits · severity: low (residual — addressed by inline pre-phase gate_settings_app_on_t2175_4) · → mitigation: inline pre-phase gate_settings_app_on_t2175_4
- The all-providers aggregation in `stats_data` and settings is rewritten. A slip
  changes `ait stats` / stats-TUI / settings numbers beyond the intended window fix. All_time
  paths are already pinned by `test_all_providers_aggregation` and kept; window paths
  get new pinned-date tests · severity: low · → mitigation: none (covered by step 6)
- Wall-clock coupling: any test fixture with a dated `period` and no pinned `today` now
  fails by calendar (`test_aitask_stats_py.py` uses 2026-03). Step 6 pins `today`, and
  the full Python suite run catches stragglers · severity: low · → mitigation: none (covered by step 6 + full-suite run)

### Goal-achievement risk: low
- On this repo the top lists will show a single model (opus5_5) until other models are
  used again. This is correct by design but may read as "still nearly empty"; the new
  empty-state hint explains the genuinely empty cases · severity: low · → mitigation: none
- The empty-state explanation (a task requirement) could render but be invisible.
  `FuzzyOption` rows are one line, and a probe showed the long placeholder clipped at
  both widths. This is addressed by the wrapping `#picker_empty_hint` label plus the
  narrow/wide per-word visibility tests in step 6 · severity: low · → mitigation: none (covered by steps 4 + 6)

### Planned mitigations
- timing: pre-phase | name: gate_settings_app_on_t2175_4 | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: settings_app.py shared with in-flight t2175_4 | desc: edit settings_app.py only once HEAD contains t2175_4's sitrep lines and the file is clean vs HEAD (staged+unstaged); otherwise ask for an explicit handover

## Out of scope / upstream defect to record at Step 8
- `.aitask-scripts/aitask_codeagent.sh:337` — `list-models` STATS reads `.value.runs`
  (the pre-bucket flat format), so every model prints `runs 0, avg 0`. Pre-existing, and
  the file has another session's uncommitted hunks. This goes in the "Upstream defects
  identified" bullet for a Step 8b follow-up.

## Final Implementation Notes
- **Actual work done:** Implemented the plan as approved, steps 0–7.
  - **Shared helper:** new `lib/model_stats_windows.py` (`current_periods`,
    `resolve_windows`, `recent_aggregate`, `stats_key_for_operation`,
    `STATS_KEY_BY_OPERATION = {"batch-review": "review"}`).
  - **`stats_data`:** the copy of `recent_aggregate` is gone; it is re-exported from the
    helper. Both loaders take `today`, store resolved windows, and sum them across
    providers, replacing the first-seen-period grouping. `aitask_stats.main()` passes its
    `today`.
  - **Picker:** modes are `top_all_ops` / `top_usage` / `all` / per-agent. All stats
    lookups use `stats_key`. `_format_op_stats(today=)` is date-correct. Empty top lists
    show a short row plus the wrapping `#picker_empty_hint` label.
  - **`settings_app`:** `_aggregate_verifiedstats(today=)` sums resolved windows and now
    includes prev_month. The Agent Defaults labels and the non-default list use the
    stats key.
  - **Tests:** new `tests/test_model_stats_windows.py` (17) and
    `tests/test_settings_verifiedstats_windows.py` (5). Rewrote
    `tests/test_agent_model_picker.py` (14). Extended `tests/test_agent_model_picker_narrow.py`
    (+3 visibility), `tests/test_aitask_stats_py.py` (+4 windows, +1 usage class) and
    `tests/test_stats_data.sh` (+3).
  - **Docs:** settings `_index.md` / `reference.md`, `skills/verified-scores.md`,
    `aidocs/framework/adding_a_new_codeagent.md`.
- **Deviations from plan:**
  - Added `prev_month` to the schema JSON example in `reference.md` for consistency
    with the new table row.
  - The empty-state probes and the edit guard are scratch-only; nothing extra is in the repo.
  - Real-data numbers at verification time were 310 / 295 / 316, not the planned
    307 / 292 / 313: other sessions recorded picks meanwhile.
- **Issues encountered:**
  - The pre-phase gate failed at first: t2175_4's sitrep hunks were still uncommitted.
    I did all non-overlapping work, then stopped and asked. After the user reported
    "2175_4 landed", the gate passed: (a) clean vs HEAD with nothing staged; (b) all
    three lines in HEAD, introduced by
    `bdef300b0 feature: Add the sitrep skill and its own agent window (t2175_4)`.
    `settings_app.py` was edited only after that.
  - As predicted, `test_all_providers_aggregation_month` failed by wall clock until
    `today` was pinned.
  - My first HEAD-control harness for the settings tests imported the live module
    (the test re-inserts the settings dir on `sys.path`). I fixed it by pre-loading
    HEAD's copy.
- **Key decisions:**
  - The batch-review fix is reader-side only, so recorded data and skills are unchanged.
  - The top lists show no verified scores; scores stay in the per-agent lists and the
    settings tabs.
  - The hint is a separate Label, because `FuzzyOption` is one row high.
  - The ISO week matches the writers (verified against GNU `date +%G-W%V`).
- **Verification evidence:**
  - Every new test fails under a mutant or against HEAD: picker date-blind mutant 4/6;
    stats_data period-blind `resolve_windows` 5/5; settings tests vs HEAD's
    `settings_app.py` 3 failures + 2 errors of 5; hint forced to `height: 1` 2/2
    (narrow on wrap height, wide on 15 missing words).
  - Full Python suite on the final tree: `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.
  - `test_stats_data.sh` 9/9, `test_stats_verified_rankings.sh` and
    `test_no_lib_to_tui_import.sh` OK, `website/check_links.py --build` SWEEP: PASSED.
  - The edit-guard chain reported `check` OK on all 15 paths before commit.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_codeagent.sh:337` — `ait codeagent list-models` STATS line
    reads `.value.runs` / `.value.score_sum` (the pre-bucket flat format) instead of
    `.value.all_time.*`, so every model prints `runs 0, avg 0`.
- **Observed, not fixed:** the two screenshots under the picker paragraph in
  `website/content/docs/tuis/settings/_index.md` predate this change. They show an old
  two-step agent→model flow with the caption "(via Browse all models)".
