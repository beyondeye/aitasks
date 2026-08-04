---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: []
issue_type: documentation
status: Implementing
labels: [documentation, agents_md, docs]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1405_1, t1405_2, t1405_3, t1405_4, t1405_5, t1405_6, t1405_7]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-08-04 12:09
updated_at: 2026-08-04 13:47
---

## Problem

The per-user auto-memory store at
`~/.claude/projects/-home-ddt-Work-aitasks/memory/` has grown to **148 memory
files** (112 `feedback`, 35 `project`, 1 `user`) plus a `MEMORY.md` index that is
loaded into context **every session**.

Three concrete symptoms, all observed on 2026-08-04 during t1243_6:

1. **The index hit its size ceiling.** `MEMORY.md` reached ~20.7 KB against a
   24.4 KB read limit and fired an automatic compaction hook demanding it be cut
   below 17.1 KB. It was compacted in place (all 148 entries kept, hooks
   shortened), but that is a reprieve, not a fix — the store grows every session
   and the next ceiling hit will force either real deletion or lossy truncation
   under time pressure, which is the worst moment to decide what matters.

2. **A memory had gone silently stale and was actively wrong.**
   `project_python_runner_k_filter_runs_nothing` asserted the framework venv has
   no pytest, so `run_all_python_tests.sh` takes its `unittest` fallback. That
   was true on 2026-07-29 and became false on 2026-08-03 when the dev tier was
   installed (`~/.aitask/dev_tier`; pytest 8.4.2 + xdist 3.8.0). For five days a
   memory loaded into every session stated a false premise about the test
   backend. **A wrong always-loaded memory is worse than no memory** — nothing in
   the current scheme re-validates one.

3. **The two agent entrypoints have diverged.** `CLAUDE.md` references
   `aidocs/framework/*` **23 times**; `AGENTS.md` references it **zero** times.
   So every specialist rule the repo has written down reaches Claude Code and
   *none* of it reaches Codex CLI / OpenCode — while the memory store, which
   partially compensates, is **per-user, per-agent, and outside git entirely**.

## Why this matters

The memory store is the wrong home for most of what is now in it:

- It is **not in the repo** — not versioned, not reviewable in a PR, not visible
  to a collaborator, and lost if the user's `~/.claude` is reset.
- It is **Claude-Code-only** — Codex CLI and OpenCode never see it, even though
  ~all 112 `feedback` memories are agent-agnostic engineering conventions.
- It is **unconditionally loaded**, so it competes for context with the task at
  hand, whereas `aidocs/framework/*.md` is read **on demand** via the
  "Read `aidocs/framework/X.md` when …" trigger lines in `CLAUDE.md`.

The repo already encodes the governing principle in
`feedback_prefer_source_enforcement_over_memory` ("enforce contracts in skill
source, not in behaviour-memories"). This task applies that principle to the
memory store itself.

## Goal

Triage every memory in the **frozen manifest** into exactly one disposition
each, then execute the dispositions. Produce a repeatable rule, not just a
one-off cleanup.

**Scope is the frozen manifest, not a fixed count.** The store is live and has a
concurrent writer: it went from 148 to 149 files during planning. So the first
child snapshots the inventory (`name` / bytes / content hash) and *that* list
defines the work. The 148 baseline is pinned by digest — the sorted names,
minus the one known post-start arrival `project_t1224_done_unblocks_t1109`,
give `sha256 84db208094ef3b8997b79efc39c0288d3324475dbe8539ede7bfcc5f2c66207d`.
Any file that arrived after that baseline is **named explicitly and excluded
from triage**, so "every memory classified" stays provable rather than a count
that drifted.

## Dispositions

Every memory in the frozen manifest gets exactly one, recorded in a triage
table. The disposition is the **user's ruling**, taken per memory after its
claim has been re-verified — not the agent's own judgement:

| Disposition | Criterion |
|---|---|
| **PROMOTE** | A durable, agent-agnostic engineering convention that belongs in `aidocs/framework/*.md` and should be reachable from **both** `CLAUDE.md` and `AGENTS.md`. Expect most of the 112 `feedback` memories here. |
| **KEEP** | Genuinely user- or machine-specific (`user_machine_omarchy_g16`, `project_g16_line_out_override`, `project_long_background_campaigns_on_this_box`, `project_benchmark_contention_concurrent_agents`) — facts about *this operator's box*, which must NOT go into a shared repo doc. |
| **DISCARD** | Stale, superseded, or task-scoped state whose task has landed. Candidates: `project_t891_deferred_behind_t756`, `project_t929_carveout_dropped`, `project_t635_29_split_procedure_gate`, `project_t986_2_*`, `project_t986_4_*`, `project_t952_5_*`. Verify against the archived task before discarding. |
| **MERGE** | Near-duplicates that should collapse into one. Known clusters: the **negative-control** family (`feedback_negctrl_restore_without_git_checkout`, `feedback_negctrl_proves_test_discriminates`, `feedback_negctrl_failing_for_the_wrong_reason`, `feedback_negctrl_one_mutation_per_test`, `feedback_negative_control_for_structural_guards`, `feedback_prove_test_harness_can_fail` — 6 files) and the **concurrent-session** family (`project_concurrent_*` — 5 files). |

## Constraints

- **Verify before discarding.** A `project_*` memory is only stale if its task
  actually landed — check `aitasks/archived/`. Do not infer staleness from age.
- **Re-validate before promoting.** The pytest incident shows memories can
  encode premises that have since flipped. Every promoted claim must be
  re-checked against current source, and anything unverifiable dropped rather
  than carried into a repo doc under false authority.
- **Promotion targets existing docs first.** There are already 18 files in
  `aidocs/framework/`. Prefer extending `testing_conventions.md`,
  `code_conventions.md`, `planning_conventions.md`, `tui_conventions.md`,
  `shell_conventions.md` etc. over minting new ones. Only create a new doc when
  no existing one is a reasonable home.
- **Both entrypoints, or it is not done.** Every promoted doc must be reachable
  from `CLAUDE.md` *and* `AGENTS.md`. Closing the 23-vs-0 gap is part of the
  deliverable, not a follow-up. Note `AGENTS.md` is a generated/shared surface —
  check `aidocs/framework/adding_a_new_codeagent.md` and
  `skill_authoring_conventions.md` for how it is produced before hand-editing.
- **Respect the documentation conventions.** Promoted prose must follow
  `aidocs/framework/documentation_conventions.md` (current-state-only, no
  version history in doc bodies) and must be genericized — no operator-specific
  paths, no real repo names (`feedback_generic_example_project_names_in_docs`).
- **Do not silently delete.** The triage table (with the reason per memory) is a
  deliverable and should survive in the plan, so a later session can audit what
  was dropped and why.

## Acceptance criteria

- A triage table covering **every memory in the frozen manifest** (count recorded
  at freeze), one disposition + one-line reason each, with each disposition
  carrying the user's explicit ruling. No manifest memory unclassified, and any
  post-baseline arrival named and listed as out of scope.
- PROMOTE items are merged into `aidocs/framework/*.md`, with each claim
  re-verified against current source; unverifiable claims are dropped and listed
  as such. **UNVERIFIABLE claims are structurally ineligible for promotion** —
  changing that requires amending this criterion first.
- `CLAUDE.md` and `AGENTS.md` both link every promoted doc. The
  `aidocs/framework` reference count in `AGENTS.md` is no longer zero. Because
  `AGENTS.md` is regenerated from `seed/aitasks_agent_instructions.seed.md`
  between `>>>aitasks`/`<<<aitasks` markers, the pointers live in an appendix
  **after** the closing marker — never inside it, and never in the seed (which
  ships to projects that have no `aidocs/`).
- DISCARD and MERGE items are removed/collapsed on disk, and `MEMORY.md` is
  regenerated so every remaining file has exactly one index line and every index
  line points at an existing file (no orphans, no dangling links). MERGE items
  additionally record the source → merged `doc#heading` mapping, and surviving
  `[[wikilinks]]` are rewritten to the exact absorbing section.
- `MEMORY.md` ends materially below the compaction ceiling — target **≤ 10 KB** —
  with headroom for future sessions rather than sitting just under the limit.
  If user KEEP rulings push it over, resolve by hook-compaction first, then by an
  explicit user choice between amending this ceiling and re-ruling. A KEEP ruling
  is never overridden to hit the number, and the task does not end silently over.
- A short **retention rule** is written down (in the promoted doc or
  `documentation_conventions.md`) answering: what earns a memory vs. an
  `aidocs/` entry, and when a `project_*` memory should be deleted. Without this
  the store simply regrows.

## Out of scope

- Rewriting the framework's memory *mechanism* (how memories are written or
  recalled). This task is content triage plus the retention rule.
- Auditing other users'/machines' memory stores.

## Notes

- The store is at `~/.claude/projects/-home-ddt-Work-aitasks/memory/` — **outside
  the repo**, so its edits are not part of any task commit. Only the
  `aidocs/`, `CLAUDE.md` and `AGENTS.md` changes are committable; say so
  explicitly in the plan so the diff is not mistaken for the whole deliverable.
- Useful inventory commands:
  ```bash
  cd ~/.claude/projects/-home-ddt-Work-aitasks/memory
  grep -h "^  type:" *.md | sort | uniq -c          # by type
  grep -c "aidocs/framework" CLAUDE.md AGENTS.md    # the 23-vs-0 gap
  ```
- Related memories that frame the work:
  `feedback_prefer_source_enforcement_over_memory` (the governing principle),
  `feedback_docs_over_narrow_source_scan_guard`,
  `feedback_doc_current_source_not_stale_plan`,
  `feedback_documentation_conventions` via `aidocs/framework/documentation_conventions.md`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-04T10:43:20Z status=pass attempt=1 type=human
