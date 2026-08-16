---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [shadow, aitask_monitormini, opencode]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1159
implemented_with: claudecode/opus5
created_at: 2026-08-14 13:49
updated_at: 2026-08-16 13:03
completed_at: 2026-08-16 13:03
---

Add an `opencode` entry to `SHADOW_READY_DETECTORS` / `SHADOW_STATE_DETECTORS`
(`.aitask-scripts/monitor/review_loop.py`) so the minimonitor auto-recheck loop
can arm when the SHADOW pane runs OpenCode. Sibling of t1509, which shipped the
generic detector plus the `codex` entry; OpenCode was split out because its
composer is structurally different enough to deserve its own live evidence and
its own review.

t1509 left the arm-time refusal reachable **specifically** for `opencode` — it
is the agent the refusal test now targets. Retarget that test when this lands;
do not delete it (find another undetected agent, or convert it to a
synthetic-key case) — a guard that loses its only subject is deleted, not
satisfied.

## What t1509 already measured (opencode 1.18.18, 2026-08-14, `capture-pane -p -e`)

Hand these forward rather than re-deriving them — they cost a live session.

- The composer is a **`┃`-gutter box**, not a prompt glyph + text. Its positive
  anchor must be the box's **`╹▀▀▀…` bottom border** plus the composer status
  row (`Build · <model> · <effort>`).
- The permission dialog **REPLACES** the composer box (no `╹▀▀▀` border, no
  status row) — so the positive half excludes it structurally, exactly as for
  Codex. But the dialog is **also** a `┃`-gutter box, and it **contains blank
  gutter rows**. A naive "a blank `┃` row exists" positive rule therefore
  FALSE-POSITIVES on the permission dialog. This needs an explicit negative
  control.
- The gray placeholder hint (`Ask anything...`) is **NOT** a durable readiness
  signal: it is present on a fresh session and **gone after the first turn**.
  Do not build the positive half on it.
- The working state is a **blank composer box plus an `⬝⬝⬝⬝ esc interrupt`
  footer** — i.e. at-rest and working are indistinguishable inside the box, and
  the footer is the only discriminator.
- There is **no SGR-dim styling anywhere** in the OpenCode composer (the hint is
  a truecolor gray, `38;2;128;128;128`), so `_DIM_SPAN_RE` — the discriminator
  the Claude and Codex detectors share — does **not** transfer.
- `opencode` already has two live t1467 dialog patterns (`opencode_question`,
  `opencode_permission`) available as the negative half.

## Scope

Reuse the generic `review_loop._composer_state` if it fits; if OpenCode's box
shape does not fit its glyph+pad contract, add a sibling classifier rather than
distorting the shared one, and keep `SHADOW_READY_DETECTORS` /
`SHADOW_STATE_DETECTORS` keyed identically (t1509 pins that with a test).

## Acceptance criteria

- An `opencode` entry in both detector tables.
- Raw-ANSI fixtures in `tests/review_loop_fixtures.py` for: at-rest-fresh (hint
  present), **at-rest-after-a-turn (hint absent)**, typed, working, and the
  permission dialog. Trim each to the 15-line window `capture_raw_tail` actually
  reads, as the `CODEX_*` fixtures do.
- An **isolated-positive-half** test: with `PROMPT_PATTERNS_BY_AGENT["opencode"]`
  emptied, the permission dialog must still be not-ready — proving structural
  exclusion rather than pattern coverage.
- The **blank-`┃`-row negative control**: a naive "blank gutter row exists" rule
  must be shown to fail on the permission dialog, so the border/status-row
  anchor is pinned as load-bearing.
- The same post-interaction settle measurement t1509 ran (wall-clock seconds at
  0.25s sampling, ≥5 reps per interaction kind), and confirmation that
  `SHADOW_SETTLE_SECONDS` is still adequately sized for OpenCode's transitions.
- The arm refusal stays reachable and still names the agent.
- `bash tests/run_all_python_tests.sh` — final stderr verdict line only.

## Coordination

- **t1509** — shipped the generic `_composer_state`, `shadow_state`, the
  wall-clock settle latch, and the pid-carrying shadow seam this task builds on.
  Read `aiplans/archived/p1509_*.md` (its Pre-phase RESULTS section) first.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-16T07:48:33Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-16T09:52:11Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-16T10:03:23Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:b2173ba087748734

> **✅ gate:risk_evaluated** run=2026-08-16T10:03:23Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1520/risk_evaluated_2026-08-16T10:03:23Z-risk_evaluated-a1.log`
