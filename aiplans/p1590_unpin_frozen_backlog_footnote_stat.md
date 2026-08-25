---
Task: t1590_unpin_frozen_backlog_footnote_stat.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1590 — Unpin the frozen backlog footnote stat

## Context

t1544_6 (docs) was asked to state that the two completion clocks "can name a
different week for ~0.3% of tasks". Verification showed that figure is **not
computed** — it is a string literal frozen from a one-time t1544_3 measurement,
with nothing recomputing or guarding it. The docs were therefore written to
state the behavioural invariant *without* the number, which left the rendered
CLI report as the only surface still asserting a stale statistic to users.

A second defect was recorded at the same time: `aitasks/metadata/stats_config.json`
pins five presets that `stats_config.py::DEFAULT_PRESETS` already defines.

This task removes the untrue claim and the redundant pin.

### Two premises in the task text are wrong — scope is smaller than described

Verified against the source (post-t1586):

| task text claims | actual |
|---|---|
| `stats/panes/backlog.py` mirrors the footnote verbatim | **False.** The pane's `_diagnostic_lines()` (`backlog.py:65-82`) emits only the exclusion + clamp lines. It never renders any of the three prose footnotes. |
| t1544_5's CLI-parity test pins the pair | **False.** `test_diagnostics_match_the_cli_exclusion_footnote` (`test_stats_backlog_panes.py:496`) compares the **exclusion** footnote, a different sentence. |
| the literal is at `aitask_stats.py:471` | Now `:390-393` — t1586 (`6a80b7bc5`) moved it. |

So the footnote half is a **2-site edit**, not a coupled 3-site edit: one
production string and one test golden.

### Measured ground truth (read-only probe against the live archive)

| | count | pct |
|---|---|---|
| archived tasks where both clocks resolve | 1859 | — |
| differ by a **day** | 27 | 1.45% |
| differ by a **week bucket** | 6 | **0.32%** |

The literal is coincidentally still accurate — which is exactly why it is
dangerous: it is unmaintained, and the by-week numerator (6) is small enough
that the percentage drifts with every archive addition.

**Decision (user-approved): drop the percentage rather than compute it.**
Computing is feasible — `resolve_completion_date(content, frontmatter)` is
already called one line after backlog booking (`stats_data.py:1329-1330`) and
`merge_stats_data` merges Counter fields additively — but it would add ~40 lines
and a new metric surface for a task the docs already settled by stating the
invariant instead.

---

## Implementation

### Pre-phase (risk mitigations)

**`characterize_effective_presets`** — before touching
`aitasks/metadata/stats_config.json`, capture the effective preset config and
keep it for comparison:

```bash
~/.aitask/venv/bin/python -c "import sys,json; sys.path.insert(0,'.aitask-scripts'); \
from stats import stats_config; print(json.dumps(stats_config.load()['presets'], indent=2))" \
  > "$SCRATCH/presets_before.json"
```

Re-run after Step 2 and diff. It must be byte-identical (all 7 keys, same
order, same lists). This converts "all five pins are identical, verified by
inspection" into an executed check, and is the only thing that would catch a
pin that differs in a way per-key inspection missed.

### Step 1 — Drop the frozen percentage from the CLI footnote

**`.aitask-scripts/aitask_stats.py:390-393`**, in `render_backlog_level()`:

```python
    print(
        "_Backlog uses `completed_at` (falling back to `updated_at` for Done); the other sections "
        "prefer gate-ledger stamps -- the same set of completed tasks, a small number bucketed "
        "one week apart._",
        file=out,
    )
```

Replaces `a different week for ~0.3%._`. The new wording mirrors the prose the
docs already settled on at `website/content/docs/commands/board-stats.md:90`
("…can disagree on *which week* it landed in, so a small number of tasks are
bucketed one week apart"), so the rendered surface and the docs now agree.

**`tests/test_aitask_stats_py.py:622`** — update the last line of
`_LEVEL_SECTION_GOLDEN` to the new sentence. This is a whole-section golden, so
it must match byte-for-byte; nothing else in the golden changes.

No other site is affected: `render_backlog_level` has exactly one production
call site (`aitask_stats.py:523`), and no doc quotes the footnote verbatim.

### Step 2 — Remove the redundant preset pins

**`aitasks/metadata/stats_config.json`** — all five pinned presets (`overview`,
`labels`, `agents`, `velocity`, `pipeline`) are **byte-identical** to their
`DEFAULT_PRESETS` entries, so the file contributes nothing to the effective
config today. Because `deep_merge` (`lib/config_utils.py:101-118`) merges dicts
per key but **replaces lists wholesale**, each identical pin is a live drift
hazard: a pane later added to any of those five code presets would be silently
masked in this project.

Reduce the file to:

```json
{}
```

The `presets` key goes away entirely — there are no genuine overrides to keep.
`_load_json` treats a missing-or-empty project layer as `{}`, so the effective
config becomes purely code-defined. Emptying rather than deleting keeps the path
that `website/content/docs/tuis/stats/_index.md:103` documents as the project
override layer, and keeps `config_utils.DEFAULT_EXPORT_PATTERNS` (`*_config.json`)
sweeping a file that still exists.

**This lives on the `aitask-data` branch** (`aitasks/` is a symlink to
`.aitask-data/aitasks/`), so it must be committed with `./ait git`, not plain git.

### Step 3 — Add the drift guard (this is what makes Step 2 stick)

Add one test to `TestPresetPrecedence` in `tests/test_stats_backlog_panes.py`:
assert that **no preset pinned in the shipped project JSON equals its
`DEFAULT_PRESETS` entry** — every pin must be a genuine override.

Word its docstring to distinguish it from the class docstring's existing
prohibition ("Never an equality test between `DEFAULT_PRESETS` and the JSON
literal — that would lock the duplication in permanently"). This guard is the
**inverse**: it forbids duplication rather than pinning it, and it passes
vacuously when the JSON has no `presets` block. Read the JSON directly (not via
`load()`) — the whole point is to inspect the project layer before merging.

### Post-phase (risk mitigations)

**`root_anchor_preset_drift_guard`** — resolve the JSON in the Step 3 guard from
the **repo root**, not the process cwd:

```python
_REPO_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_STATS_CONFIG = _REPO_ROOT / "aitasks" / "metadata" / "stats_config.json"
```

≈39 modules in this suite chdir the process, so a cwd-relative read could make
the guard pass vacuously against a missing file — a guard that cannot fail.
(The pre-existing `test_backlog_preset_is_in_the_effective_config` keeps its cwd
dependency; this mitigation covers only the new guard.)

### Not changed

- `website/content/docs/tuis/stats/_index.md:57-73` already lists all seven
  presets and correctly locates them in `stats_config.py`, framing the JSON as
  an optional override. Emptying the JSON keeps every sentence true.
- `aitasks/t1544/t1544_8_...md:108` repeats `~0.3%`, but as an explicitly
  attributed historical record ("26 of ~1828") in a pending retrospective — a
  legitimate past-tense measurement, not a current-fact assertion.

---

## Verification

1. **Negative control for the golden** — after the `aitask_stats.py` edit but
   *before* fixing the golden, confirm `test_aitask_stats_py.py`'s level-section
   comparison **fails**, and record the failing test id. A golden that passes
   un-updated would prove it never pinned the footnote.

2. **Negative control for the drift guard** — temporarily re-add one identical
   preset pin to the JSON, confirm the new guard fails, then remove it.

3. **Targeted tests**
   ```bash
   ~/.aitask/venv/bin/python -m pytest tests/test_aitask_stats_py.py tests/test_stats_backlog_panes.py
   ```

4. **Full Python suite** — read only the last line (`PYTHON SUITE: PASSED|FAILED`):
   ```bash
   bash tests/run_all_python_tests.sh 2>&1 | tail -3
   ```

5. **Rendered surface** — `ait stats`; confirm the Backlog Level section's last
   footnote carries no percentage.

6. **Stats TUI unaffected** — `ait stats --tui`, open the layout picker, confirm
   all seven presets still list with the JSON emptied.

## Step 9 (Post-Implementation)

Standard closure: commit `.aitask-scripts/aitask_stats.py` and `tests/` with
plain git (path-scoped, `-o --`); commit `aitasks/metadata/stats_config.json`
with `./ait git`. Then archive t1590 and its plan.

## Risk

*(Levels reassessed against the augmented plan after both inline mitigations
were confirmed — unchanged at low/low; the mitigations reduce rather than add
exposure.)*

### Code-health risk: low
- Emptying the JSON changes the effective config for any project that *relied*
  on the pin — here, none, since all five pins are byte-identical to the code
  defaults (verified per-key). · severity: low · → mitigation: inline pre-phase characterize_effective_presets
- The new drift guard reads the project JSON by path, so a cwd-relative read
  could make it pass vacuously under this suite's chdir-ing modules. · severity: low · → mitigation: inline post-phase root_anchor_preset_drift_guard

### Goal-achievement risk: low
- None identified. Both defects reduce to a single concrete edit each, both
  task premises were verified against source, and the drop-vs-compute decision
  was resolved by the user.

### Planned mitigations
- timing: pre-phase | name: characterize_effective_presets | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — JSON emptying could silently change the effective preset config | desc: Capture stats_config.load()["presets"] before Step 2 and assert byte-identical after.
- timing: post-phase | name: root_anchor_preset_drift_guard | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — drift guard's cwd-relative path sensitivity | desc: Resolve the project stats_config.json from the repo root so the guard cannot pass vacuously under a chdir.

---

## Implementation record

All steps completed as planned; no deviations.

| step | outcome |
|---|---|
| Pre-phase `characterize_effective_presets` | **PASS** — effective presets byte-identical before/after (all 7 keys, same order). |
| Step 1 — footnote | `aitask_stats.py:390-393` string replaced; `test_aitask_stats_py.py:622` golden updated. |
| Step 2 — preset pins | `aitasks/metadata/stats_config.json` reduced to `{}`. |
| Step 3 — drift guard | `test_no_shipped_json_pin_duplicates_a_code_default` added to `TestPresetPrecedence`. |
| Post-phase `root_anchor_preset_drift_guard` | Guard anchors on the **pre-existing** `PROJECT_DIR` constant (`test_stats_backlog_panes.py:25`) rather than a new `_REPO_ROOT` — same root-anchoring, one fewer constant. |

### Negative controls (both executed)

1. **Golden** — with only the `aitask_stats.py` edit applied, `test_aitask_stats_py.py::TestBacklogSections::test_backlog_sections_render_byte_for_byte` FAILED, and the diff named exactly the footnote sentence. The golden did pin the footnote.
2. **Drift guard** — re-pinning `pipeline` identically to its code default made the new guard FAIL, naming `['pipeline']`. Restoring a *genuine* override (`["pipeline.timing"]`) made it PASS. The guard discriminates on redundancy, not on the mere presence of a pin.

### What the guard does NOT buy

It only inspects the project layer of *this* repo. It cannot see a redundant pin in a downstream project's own `stats_config.json`, and it says nothing about the list-replacement semantics themselves (still pinned separately by `test_a_json_preset_list_replaces_the_code_list`). Deleting the JSON entirely would make it skip, not fail.

## Final Implementation Notes

- **Actual work done:** Exactly the approved plan — both inline mitigations, both
  defects, both negative controls. Four files: `aitask_stats.py` (footnote string),
  `test_aitask_stats_py.py` (golden), `stats_config.json` (→ `{}`),
  `test_stats_backlog_panes.py` (new drift guard).
- **Deviations from plan:** One, and it reduced scope. The post-phase mitigation
  `root_anchor_preset_drift_guard` planned a new `_REPO_ROOT` constant; the file
  already had a root-anchored `PROJECT_DIR` (`test_stats_backlog_panes.py:25`),
  so the guard reuses it. Same root-anchoring, one fewer constant.
- **Issues encountered:** None during implementation. Before it, the working tree
  held t1586's uncommitted refactor of the same two stats files; since
  `git commit -o -- <paths>` commits whole file contents, a t1590 commit would
  have swallowed it. Surfaced to the user, who landed t1586 first (`6a80b7bc5`);
  this work then ran on a clean tree.
- **Key decisions:**
  - **Drop the percentage rather than compute it** (user-approved). Computing is
    viable — `resolve_completion_date` is already called one line after backlog
    booking (`stats_data.py:1329-1330`), and `merge_stats_data` merges Counter
    fields additively — but the docs had already settled the question by stating
    the invariant without a number, and a new metric surface exceeds this task.
    Measured at implementation time: 6 of 1859 archived tasks (0.32%) differ by
    week bucket; 27 (1.45%) differ by a day.
  - **Empty the JSON rather than delete it.** All five pins were byte-identical
    to `DEFAULT_PRESETS`, so none was a genuine override. Emptying keeps the path
    documented at `website/content/docs/tuis/stats/_index.md:103` and keeps
    `config_utils.DEFAULT_EXPORT_PATTERNS` (`*_config.json`) sweeping a real file.
  - **Added a drift guard**, since removing the duplication without one invites
    its return. It asserts no pinned preset equals its code default — the inverse
    of the prohibition in `TestPresetPrecedence`'s docstring, which bans pinning
    the JSON *equal* to `DEFAULT_PRESETS`.
- **Upstream defects identified:**
  - `aitasks/t1590_unpin_frozen_backlog_footnote_stat.md:26 — the task's own "Upstream defect" bullet states two premises that are false against source: (a) that stats/panes/backlog.py mirrors the clock footnote verbatim — it does not, its _diagnostic_lines() (backlog.py:65-82) emits only the exclusion and clamp lines and no prose footnote; and (b) that t1544_5's CLI-parity test pins the pair — test_diagnostics_match_the_cli_exclusion_footnote (test_stats_backlog_panes.py:496) compares the exclusion footnote, a different sentence. The recorded line number (:471) was also stale after t1586. No code defect; a defect in the recorded diagnosis that would have misled a fresh context into a 3-site edit.`
  - `.aitask-scripts/stats/panes/backlog.py:65-82 — the stats TUI backlog pane renders none of the CLI's three prose footnotes (Postponed/Folded, bug-net-of-upstream-defect, and the two-clocks note). The two surfaces are asserted at parity only on the exclusion line, so a TUI user never sees that the backlog sections use a different completion clock than the rest of the report. Possibly worth a separate task: decide whether the pane should carry the clock footnote too, or whether the omission is deliberate given pane height budgets.`

### Commit provenance note (concurrent session)

`aitasks/metadata/stats_config.json` is **not** in a `(t1590)`-tagged commit. A
concurrent session claimed t1595 mid-implementation; its `aitask_pick_own.sh`
ran a broad `add aitasks/` and swept this task's two data-branch files into
`442c65179 "ait: Start work on t1595: set status to Implementing"`. The content
committed there is correct (`{}`, verified by `git show`), and the code half
landed normally in `6e91f5d28 (t1590)`. History was left unrewritten on purpose
— the data branch is shared and that session is live.

Consequence: `aitask_issue_update.sh`, which finds commits by the `(tNN)` tag,
will not associate the `stats_config.json` change with t1590.
