--- NODE_YAML_START ---
node_id: n001_explorer_001a
parents: [n000_init]
description: "Intent-anchored concern triage: shadow keeps the human as design authority by routing every surfaced concern through an explicit now/defer-as-draft/drop disposition, spilling deferrals into aitask drafts so nothing is lost and the active plan stays lean."
proposal_file: br_proposals/n001_explorer_001a.md
created_at: "2026-06-17 07:52"
created_by_group: explorer

# --- reference_files (baseline had none; all NEW) ---
reference_files:
  - .claude/skills/aitask-shadow/SKILL.md
  - .claude/skills/aitask-shadow/plan-challenge.md
  - .claude/skills/aitask-shadow/plan-assumptions.md
  - .claude/skills/aitask-shadow/plan-socratic.md
  - .claude/skills/aitask-shadow/plan-explain.md
  - .claude/skills/aitask-shadow/plan-triage.md          # NEW component
  - .aitask-scripts/aitask_shadow_capture.sh
  - .aitask-scripts/aitask_shadow_context.sh
  - .aitask-scripts/aitask_shadow_spinoff.sh             # NEW component
  - .aitask-scripts/aitask_create.sh
  - tests/test_aitask_shadow_spinoff.sh                  # NEW component
  - aidocs/framework/shadow_agent.md
  - aidocs/framework/planning_conventions.md

# --- requirements (NEW) ---
requirements_fixed:
  - "Preserve the advisory-only contract: shadow never sends keystrokes/input into the followed pane."
  - "Stay a static, user-invocable skill (no profile/.j2/stub machinery) per shadow_agent.md."
  - "Reuse existing helpers (capture, context, create --batch) rather than forking their logic."
  - "The human remains the sole disposition authority; the shadow recommends but never decides plan changes."
requirements_mutable:
  - "Concern-ledger storage format and location (ephemeral session scratch vs task-attached)."
  - "Re-anchor nudge threshold (how many consecutive accept-verbatim dispositions trigger it)."
  - "Whether deferred concerns become drafts (aitasks/new/) or committed child tasks."

# --- assumptions (NEW) ---
assumption_advisory_contract: "The read-only/advisory guardrail is the right invariant; the steerability problem is human cognitive delegation, not the shadow typing into the pane."
assumption_intent_capturable: "The user can state, in 1-2 sentences, the actual intent of the current task at the start of a steering session, and that anchor is stable enough to triage concerns against."
assumption_create_batch_available: "aitask_create.sh --batch is present and supports draft mode (writes to aitasks/new/ without --commit), --name, --desc/--desc-file, --priority, --effort, --type, --labels, --parent."
assumption_ephemeral_session: "A shadow run is ephemeral and may be killed when the followed agent dies (aitask_companion_cleanup.sh); durable artifacts must live outside the shadow pane (created drafts + plan edits the user makes), not only in shadow memory."
assumption_loss_aversion_is_the_driver: "Plan bloat is driven by fear of losing concerns; a credible capture mechanism (drafts) removes the incentive to fold every concern into the active plan."

# --- components (NEW) ---
component_intent_anchor: "Session-start capture of the user's stated intent for the current task; the fixed reference every concern is triaged against."
component_concern_triage: "plan-triage.md sub-procedure that classifies each surfaced concern relative to the intent anchor and forces an explicit per-concern disposition (now/defer/drop)."
component_concern_ledger: "Session-scoped markdown table that records every surfaced concern + its disposition so nothing is silently lost and the active plan can stay lean."
component_spinoff_helper: "aitask_shadow_spinoff.sh — whitelisted wrapper over aitask_create.sh --batch that turns a deferred ledger row into a reviewable aitask draft linked back to the current task."
component_steerability_guardrail: "Output-shape contract + delegation nudge: shadow emits a decision sheet (not a rewritten plan) and re-anchors the user when it detects accept-verbatim delegation."

# --- tradeoffs (NEW) ---
tradeoff_scope_creep_reduction: "Forces concern-by-concern disposition against intent, so the active plan stays small and directly steerable — at the cost of one extra decision step per concern the user previously absorbed implicitly."
tradeoff_extra_friction: "The triage gate adds interaction turns; mitigate with batch disposition ('defer all of section 3 as drafts') and sensible recommended defaults so the common path is one keystroke."
tradeoff_ledger_persistence: "An ephemeral ledger can be lost if the shadow pane is killed mid-session; mitigate by flushing the ledger to a stable path (e.g. .aitask-shadow/ledger_<task>_<ts>.md) on every disposition rather than holding it only in shadow memory."
tradeoff_intent_anchor_overhead: "Asking for an intent statement up front costs a turn and can feel redundant when intent is obvious; mitigate by pre-filling the anchor from the task title/description and letting the user accept or edit it."
tradeoff_draft_review_backlog: "Spilling concerns into aitasks/new/ trades plan bloat for a draft backlog that must be triaged later; mitigate by labeling drafts (deferred-from-<task>) and depends-linking them so the backlog is filterable and ordered, not an undifferentiated pile."
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview -->
## Overview

**Intent-Anchored Concern Triage.** The baseline problem is not that the shadow
*acts* on the followed agent — the advisory-only guardrail already prevents that.
The problem is **cognitive delegation**: the shadow's analyses (`plan-challenge`,
`plan-assumptions`, `plan-socratic`) surface so many valid-looking concerns that
the user, unwilling to *lose* any of them, folds them all back into the active
plan. The result is a "complete" plan that no longer reflects the user's own
intent and is no longer directly steerable — the exact inverse of the aitasks
philosophy (decompose into many small, intent-aligned tasks).

This approach changes **what the shadow does with the concerns it surfaces**,
not its read-only stance. Two new behaviors are inserted between "surface a
concern" and "the user edits the plan":

1. **Anchor on intent.** At the start of a steering session the shadow captures
   (or pre-fills from the task) a 1-2 sentence statement of *what the user
   actually wants this task to do*. This anchor is the reference every concern is
   judged against.
2. **Triage, don't dump.** Every surfaced concern is routed through an explicit
   per-concern disposition — **address now / defer as a draft task / drop** —
   evaluated against the intent anchor. Deferred concerns are *captured as
   aitask drafts* (`aitasks/new/`) by a new spillover helper, so the user can
   defer without fear of loss, and the active plan stays lean.

The shadow's output shape also changes: it emits a **decision sheet the user
fills in**, never a pre-revised plan, and it actively nudges the user back to
their intent when it detects accept-verbatim delegation. The human stays the
design authority; the shadow stays advisory.

How it differs from the baseline: the baseline shadow is a *concern generator*
(it surfaces issues and the user decides what to do with each, unaided). This
approach makes the shadow a *concern router* — it generates concerns **and**
provides the intent-anchored triage + capture machinery that keeps those
concerns from collapsing the plan's steerability.
<!-- /section: overview -->

<!-- section: architecture -->
## Architecture

The skill remains a static, user-invocable command
(`/aitask-shadow <pane_id> [<task_id>]`) with the same capture → context → serve
pipeline. Five additions/extensions implement the new behavior; nothing in the
advisory-only contract or spawn/binding path changes.

**1. Intent Anchor (skill-level, in `SKILL.md`).** A new Step 2.5 that runs once
per steering session, the first time the user asks for a *plan* analysis
(challenge/assumptions/socratic/explain) rather than a plain "what is this
agent doing?". It pre-fills a candidate intent statement from the resolved task
file's title + first description paragraph (via the existing
`aitask_shadow_context.sh`) and asks the user to **accept or edit** it. The
accepted string is held for the rest of the session and written into the ledger
header. It is advisory scaffolding, never a gate: the user can decline and
proceed.

**2. Concern Triage sub-procedure (`plan-triage.md`, NEW).** The existing
structured analyses are refactored so that they *feed* triage instead of
emitting prose. When `plan-challenge.md` / `plan-assumptions.md` /
`plan-socratic.md` produce concerns, the skill reads-and-follows
`plan-triage.md`, which for each concern:
   - states the concern in one line,
   - classifies its **relation to intent**: `serves-intent`,
     `tangential-but-valid`, or `out-of-scope`,
   - proposes a **recommended disposition** (`now` for serves-intent;
     `defer` for tangential/out-of-scope; `drop` for low-value),
   - and requires the user to confirm or override the disposition.
   Dispositions can be applied in batch ("defer all tangential") to control
   friction.

**3. Concern Ledger (session artifact).** Every concern + disposition is appended
to a ledger file `.aitask-shadow/ledger_<task_id>_<launch_ts>.md` (a table:
`# | concern | source | intent-relation | disposition | target`). It is flushed
on **every** disposition, not held only in shadow memory, so an
auto-killed shadow pane never loses the record. The ledger is the anti-loss
guarantee that makes leaving concerns *out* of the active plan psychologically
safe.

**4. Spillover helper (`aitask_shadow_spinoff.sh`, NEW).** A whitelisted wrapper
over `aitask_create.sh --batch` (no `--commit`) that converts each `defer` row
into a **draft** in `aitasks/new/`: `--name` from a slugified concern title,
`--desc-file -` from the concern body + a back-reference line
(`Deferred from t<task_id> during shadow steering`), `--labels
deferred-from-<task_id>`, priority/effort defaulted low/medium. Drafts (not
committed tasks) keep the board clean while guaranteeing capture. The helper has
a dedicated unit test (`tests/test_aitask_shadow_spinoff.sh`) per the framework's
"encapsulate workflow bash in a helper with a test" convention.

**5. Steerability Guardrail extension (in `SKILL.md`).** Two output-shape rules
added to the existing advisory-only guardrail section:
   - **Decision-sheet, not revised-plan.** The shadow's serve output for plan
     work is the triage table + the list of drafts it can create — it never
     emits a ready-to-paste rewritten plan. The user makes the plan edits.
   - **Delegation nudge.** The shadow counts consecutive dispositions where the
     user accepted its recommendation verbatim; after a threshold (mutable,
     default 4) it asks one re-anchoring question
     ("we've accepted several of my calls in a row — does the plan still match
     your intent: '<anchor>'?"). This is a single advisory prompt, never a gate.
<!-- /section: architecture -->

<!-- section: data_flow -->
## Data Flow

1. **Launch.** Minimonitor `e` spawns the shadow with `<pane_id> [<task_id>]`
   (unchanged). Shadow greets and captures the screen
   (`aitask_shadow_capture.sh`).
2. **First plan ask.** User asks "challenge this plan" (or similar). Shadow
   resolves source context (`aitask_shadow_context.sh <task_id>`), then runs the
   **Intent Anchor** step: pre-fills intent from the task title/description, user
   accepts/edits → anchor string stored, ledger file created with the anchor in
   its header.
3. **Analysis → concerns.** The relevant analysis sub-procedure
   (`plan-challenge.md` etc.) produces a raw concern list.
4. **Triage.** `plan-triage.md` classifies each concern against the anchor and
   presents the **decision sheet**: per-concern `intent-relation` +
   `recommended disposition`. User confirms/overrides (individually or in batch).
   Each disposition is appended to the ledger immediately.
5. **Spillover.** For every `defer` row, `aitask_shadow_spinoff.sh` creates a
   draft in `aitasks/new/` labeled `deferred-from-<task_id>` with a back-reference
   to the current task. The ledger row's `target` column records the draft path.
6. **Lean plan edits.** The shadow tells the user which `now` concerns to fold
   into the active plan (a short list) — the user edits the plan themselves. The
   active plan absorbs only intent-serving concerns; everything else lives as a
   draft or a ledger `drop` note.
7. **Re-anchor (conditional).** If the delegation counter trips, the shadow asks
   its single re-anchoring question before continuing.
8. **Refetch loop.** On any later capture the proactive-suggestion behavior
   (unchanged) may offer triage again for a new on-screen plan; a new analysis
   reuses the same session anchor and ledger.

The only durable outputs are: the ledger file, the created drafts, and the
plan edits the user chooses to make. No state is written into the followed
agent's pane.
<!-- /section: data_flow -->

<!-- section: components [dimensions: component_*] -->
## Components

<!-- section: component_intent_anchor [dimensions: component_intent_anchor] -->
### Intent Anchor
- **Where:** new Step 2.5 in `SKILL.md`; no new file.
- **Tech:** AskUserQuestion (or a plain prompt) pre-filled from
  `aitask_shadow_context.sh` output (TASK_FILE title + first description
  paragraph).
- **Config:** none; runs once per session on the first plan-analysis ask. Stores
  the accepted string in shadow working memory and the ledger header.
- **Contract:** advisory scaffolding, skippable; never blocks a request.
<!-- /section: component_intent_anchor -->

<!-- section: component_concern_triage [dimensions: component_concern_triage] -->
### Concern Triage (`plan-triage.md`)
- **Where:** new `.claude/skills/aitask-shadow/plan-triage.md`, read-and-followed
  from Step 3, fed by the existing analysis sub-procedures.
- **Methodology:** for each concern emit `{one-line, intent-relation ∈
  {serves-intent, tangential-but-valid, out-of-scope}, recommended ∈
  {now, defer, drop}}`; require user confirm/override; support batch disposition.
- **Output:** the decision sheet (markdown table), plus the set of `now` concerns
  to fold and `defer` concerns to spill.
<!-- /section: component_concern_triage -->

<!-- section: component_concern_ledger [dimensions: component_concern_ledger] -->
### Concern Ledger
- **Where:** `.aitask-shadow/ledger_<task_id>_<launch_ts>.md` (stable path,
  survives shadow-pane death).
- **Schema (markdown table):** `# | concern | source | intent-relation |
  disposition | target` with a header block carrying the intent anchor and task
  id.
- **Lifecycle:** appended on every disposition (flush-per-row, not buffered);
  referenced by the spillover helper to set `target` paths.
<!-- /section: component_concern_ledger -->

<!-- section: component_spinoff_helper [dimensions: component_spinoff_helper] -->
### Spillover Helper (`aitask_shadow_spinoff.sh`)
- **Where:** new `.aitask-scripts/aitask_shadow_spinoff.sh`, whitelisted; test at
  `tests/test_aitask_shadow_spinoff.sh`.
- **Interface:** `aitask_shadow_spinoff.sh --from-task <id> --title <slug>
  [--priority low] [--effort medium]` reading the concern body on stdin.
- **Tech:** thin wrapper over `aitask_create.sh --batch --name <slug>
  --desc-file - --labels deferred-from-<id> --priority low --effort medium`
  (no `--commit` → draft in `aitasks/new/`). Prepends a
  `Deferred from t<id> during shadow steering` back-reference line to the body.
- **Why a helper, not inline:** keeps multi-flag create logic out of the skill
  markdown, gives it a unit test, and shrinks the procedure to one call (per the
  framework helper-encapsulation convention).
<!-- /section: component_spinoff_helper -->

<!-- section: component_steerability_guardrail [dimensions: component_steerability_guardrail] -->
### Steerability Guardrail (extension)
- **Where:** extends the existing "advisory only" guardrail section in
  `SKILL.md`.
- **Rules:** (a) plan-work output is a decision sheet + draftable spillovers,
  never a pre-revised plan; (b) delegation nudge — count consecutive
  accept-verbatim dispositions, re-anchor after the threshold (mutable,
  default 4) with one advisory question.
- **Contract:** both rules are advisory prompts; neither gates what the user can
  ask, preserving the one-flow design.
<!-- /section: component_steerability_guardrail -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

- **assumption_advisory_contract** (NEW): The read-only/advisory guardrail is the
  correct invariant; the steerability failure is human cognitive delegation, not
  the shadow driving the pane. *Load-bearing:* if the real problem were the
  shadow acting, this whole approach (which leaves the guardrail untouched) would
  miss the target.
- **assumption_intent_capturable** (NEW): The user can state the current task's
  intent in 1-2 sentences at session start, and that anchor is stable enough to
  triage concerns against. *Load-bearing and partly unverified* — if intent is
  genuinely fuzzy, the anchor weakens; mitigated by pre-filling from the task and
  allowing edits/re-anchoring.
- **assumption_create_batch_available** (NEW): `aitask_create.sh --batch` exists
  and supports draft mode (`aitasks/new/` without `--commit`), `--name`,
  `--desc-file -`, `--priority`, `--effort`, `--labels`. *Verified* against the
  current `aitask_create.sh` help/flag table.
- **assumption_ephemeral_session** (NEW): A shadow run is ephemeral and may be
  auto-killed when the followed agent dies, so durable artifacts (ledger,
  drafts, plan edits) must live outside the shadow pane. *Verified* against
  `aitask_companion_cleanup.sh` behavior described in `shadow_agent.md`.
- **assumption_loss_aversion_is_the_driver** (NEW): Plan bloat is driven by fear
  of losing concerns; a credible capture mechanism removes the incentive to fold
  every concern into the active plan. *Load-bearing* — the spillover-to-draft
  mechanism only fixes the problem if loss-aversion (not completeness-as-a-goal)
  is the actual driver.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

- **tradeoff_scope_creep_reduction** (NEW): *Advantage.* Forcing concern-by-concern
  disposition against intent keeps the active plan small and directly steerable,
  restoring alignment with the decompose-into-small-tasks philosophy. *Cost:* one
  explicit decision per concern that the user previously absorbed implicitly.
- **tradeoff_extra_friction** (NEW): *Risk.* The triage gate adds interaction
  turns and can feel heavy on a plan with 15 concerns. *Mitigation:* batch
  disposition by intent-relation ("defer all tangential as drafts") and
  pre-computed recommended defaults so the common path is a single confirm.
- **tradeoff_ledger_persistence** (NEW): *Risk.* An in-memory ledger is lost if
  the shadow pane is auto-killed mid-session. *Mitigation:* flush the ledger to
  `.aitask-shadow/ledger_<task>_<ts>.md` on every disposition; on relaunch the
  shadow can re-read an existing ledger for the same task.
- **tradeoff_intent_anchor_overhead** (NEW): *Risk.* Asking for intent up front
  costs a turn and feels redundant when intent is obvious. *Mitigation:*
  pre-fill the anchor from the task title/description; the user accepts with one
  keystroke or edits.
- **tradeoff_draft_review_backlog** (NEW): *Risk.* Spilling concerns into
  `aitasks/new/` trades plan bloat for a draft backlog that still needs triage
  later. *Mitigation:* label drafts `deferred-from-<task_id>` and record their
  origin so the backlog is filterable and ordered (finalize via
  `ait create --batch --finalize-all`), not an undifferentiated pile —
  this is the intended aitasks shape (many small tasks) rather than a regression.
<!-- /section: tradeoffs -->
--- PROPOSAL_END ---
--- NEW_DIMENSIONS ---
requirements_fixed, requirements_mutable, assumption_advisory_contract, assumption_intent_capturable, assumption_create_batch_available, assumption_ephemeral_session, assumption_loss_aversion_is_the_driver, component_intent_anchor, component_concern_triage, component_concern_ledger, component_spinoff_helper, component_steerability_guardrail, tradeoff_scope_creep_reduction, tradeoff_extra_friction, tradeoff_ledger_persistence, tradeoff_intent_anchor_overhead, tradeoff_draft_review_backlog
