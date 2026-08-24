---
Task: t1544_7_manual_verification_stats_backlog.md
Parent Task: aitasks/t1544_stats_backlog_and_net_flow_by_category.md
Sibling Tasks: aitasks/t1544/t1544_1_*.md, aitasks/t1544/t1544_4_*.md, aitasks/t1544/t1544_5_*.md, aitasks/t1544/t1544_6_*.md
Archived Sibling Plans: aiplans/archived/p1544/p1544_*_*.md
Base branch: main
Output branch: main
---

# p1544_7 — Manual-verification auto-execution record

Retroactive record of the autonomous auto-verification pass over t1544_7's
20-item checklist. Every item reached `pass`; nothing was skipped or deferred.

**Verified tree state:** commit `6a80b7bc5` (t1586, "Extract the shared backlog
view logic into lib/backlog_view.py"), working tree clean. t1586 landed
mid-session; before it did, its uncommitted refactor of `aitask_stats.py` and
`stats/panes/backlog.py` would have made any stats failure unattributable, so
verification waited for it. The verified surfaces therefore include the
extracted `lib/backlog_view.py` seam.

## Execution Log

### Items 1–4 — [t1544_1] session discovery dedupe

- Approach: live tmux + direct calls to the shared discovery path.
- The 2026-08-18 baseline recorded **no duplicate keys**, which the plan itself
  called *vacuous on this machine*. The same three live sessions were running
  today, so the baselines are directly comparable — and a **real duplicate was
  fabricated** (a 2nd tmux session rooted at `/home/ddt/Work/aitasks`) to make
  the checks non-vacuous. It was killed afterwards; the socket was restored to
  its original three sessions.

| # | Evidence | Verdict |
|---|---|---|
| 1 | `discover_aitasks_sessions()` → 3 entries byte-identical to List A (key/session/project_name/live/stale), duplicate keys none. `ait monitor` header `tmux Monitor — 3 sessions`, groups `aitasks`/`thinking_back`/`thinkingapp`. With the duplicate present List A correctly listed it **twice** — the dedupe deliberately does not touch no-flag discovery. | pass |
| 2 | `include_registered=True` → 7 entries byte-identical to the recorded prediction, duplicate keys `[]`. `j` overlay in monitor shows `aitasks · aitasks_go · aitasks_mob` in the selected group. With the duplicate present, still 7 entries and no duplicate key. | pass |
| 3 | `discover_stats_sessions()` → 7 entries, no duplicates, preferring the `is_live=True` entry. Stats TUI sidebar listed `aitasks` once. Project total `1856` and aggregate `2197 / 43 / 360 / 13` were **identical with and without** the duplicate. | pass |
| 4 | With the duplicate live, `j` left/right cycling reached the `thinking_back`, `teamim` and `timeu` groups and returned to `aitasks`; group `[aitasks]` still lists `aitasks`/`aitasks_go`/`aitasks_mob`. Ring not trapped in the duplicated pair. | pass |

### Items 5–12 — [t1544_4] CLI sections and CSV

| # | Evidence | Verdict |
|---|---|---|
| 5 | `### Backlog Level` and `### Backlog Net Flow` both render, each split by the category axis. | pass |
| 6 | Every table row is **exactly 80 chars** at the default horizon (awk-measured). Follow-up rows lowercase, issue-type rows Title Case, separated by `-- follow-ups` / `-- genuine`. | pass |
| 7 | Split renders as `of which parents` / `of which children` rows per `p1544_4:158-160`. Invariant `follow-ups + genuine == TOTAL OPEN == parents + children` holds in **all 8 columns**. | pass |
| 8 | Net-flow header `Now*` + `_Now* covers 2026-08-24..2026-08-24 (partial week)._`; the level table keeps plain `Now` **by design** (`p1544_4:236-237` — offset 0 is a stock, correct as-of-now). Excluded tally, gross-vs-net `bug` footnote and two-clocks footnote all present. | pass |
| 9 | `--backlog-weeks 26` exits 0; its trailing 8 columns are numerically identical to the default run for every row. | pass |
| 10 | Per-task CSV has 12 columns; the first 10 match the pre-change `write_csv` list at `dc69a2b^` **in the same order** (confirmed via `git show`), with `created_at,category` appended. Backlog CSV header is exactly `week_ending,category,open,arrived,departed,net`. | pass |
| 11 | Ran the **pre-change** code from a worktree at `t1544_4^` (`39aebdc5f`) against the *same* live task tree (symlinked `aitasks/`). Deleting only the 50 new backlog lines from current output makes it **byte-identical** to the pre-change capture except the `Generated:` line. | pass |
| 12 | Scratch project (3 open tasks, empty `aitasks/archived`) renders both backlog sections, `TOTAL OPEN 3 = parents 3 + children 0`. **Negative control:** the same project with zero open tasks still prints `No completed tasks found.`, and with no archive dir prints `No archived tasks found in aitasks/archived` — so the check can fail. | pass |

### Items 13–18 — [t1544_5] stats TUI panes

Driven as a real TUI in tmux at 120x45, 150x45, 120x75 and 150x75.

| # | Evidence | Verdict |
|---|---|---|
| 13 | `ait stats-tui` boots and renders at every geometry tried; `backlog` is in the eager import list (`stats/panes/__init__.py:9`). | pass |
| 14 | Picker lists all 7 presets; `backlog` shows both panes in the sidebar. The shipped `stats_config.json` omits the `backlog` **and** `sessions` keys, but `deep_merge` is per-key so both still surface (see Observation below). | pass |
| 15 | Level pane renders real data (not the empty state) and is readable. **Row cap engages:** the TUI's `Other` row equals CLI `Tests + Performance + Refactors` in every one of the 8 columns (21/22/21/30/27/27/27/27). | pass |
| 16 | Netflow chart titled `Backlog Net Flow by Category - last 8 weeks` with per-category series (Features, upstream defect, risk mitigation, manual verification, …) above the ARRIVALS/DEPARTURES/NET strip — the category dimension is visibly present. | pass |
| 17 | Drove the picker through every non-backlog preset: overview → Summary/Daily completions/Weekday distribution; labels → Top labels/Issue types/Label × week; agents → Per agent/Per model/Verified rankings/Usage rankings; velocity → Daily velocity/Rolling average/Parent vs child; pipeline → Time in phase/In-flight (gated); sessions → Per-session totals/Summary/Daily completions. All render. | pass |
| 18 | Same horizon (W-7..Now) and identical values on both surfaces; netflow strip matches the CLI's ARRIVALS 13/39/123/144/114/88/57/14, DEPARTURES 12/17/67/62/63/57/28/11, NET +1/+22/+56/+82/+51/+31/+29/+3. | pass |

**False alarm, recorded so it is not re-investigated.** An early capture showed
the excluded-tally footnote rendering as `8 task(s)     frontmatter: 3, folded:
5).` — ` (no_` replaced by blanks. It was a **mid-repaint capture**, not a
defect: the widget's `render()` in the real `StatsApp` returns the full string,
and with a proper settle wait the line renders correctly at 120x45, 150x45 and
120x75. Do not chase this as a markup bug.

### Items 19–20 — [t1544_6] documentation

| # | Evidence | Verdict |
|---|---|---|
| 19 | `hugo build --gc --minify` exits 0, 237 pages, **no relref/link errors**. Only two pre-existing Hugo deprecation WARNs (`.Language.LanguageDirection`, `.Site.AllPages`), unrelated to this task. | pass |
| 20 | Preset table matches `DEFAULT_PRESETS` pane-for-pane (7 presets). `board-stats.md:94` CSV list matches the live 12-column header exactly; `--csv-backlog` list matches. Namespaced `kind:`/`type:` keys, absence of subtotal rows, and oldest-week-first all confirmed against the live export. Completion-clock text matches `stats_data.py:421` (`Done` **or** `Completed`) — more precise than the report footnote's shorthand. | pass |

## Observation (not a checklist failure)

`aitasks/metadata/stats_config.json` pins only 5 presets and omits both
`sessions` and `backlog`, while `stats/stats_config.py` ships all 7. The parent
task's Scope said to add new pane ids to **both** and explicitly warned "do not
add a third divergence". Behaviour is unaffected — `load_layered_config` merges
per preset key, so the unpinned presets still appear (verified live) — so this
is a code-health drift, not a user-visible defect. Raised for t1544_8's
retrospective rather than filed as a verification failure.

## Cleanup

- Removed the pre-change worktree at `$SCRATCH/prechange` (`git worktree remove`).
- Killed the fabricated tmux session `aitasks_dup2` and the private `t1544v`
  tmux server; the default socket is back to its original three sessions.
- Scratch captures, CSVs and the throwaway projects live under the session
  scratchpad only — nothing was written into `aitasks/` or `aiplans/` beyond
  this plan and the checklist marks.
