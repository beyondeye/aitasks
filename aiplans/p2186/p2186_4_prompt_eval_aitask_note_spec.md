---
Task: t2186_4_prompt_eval_aitask_note_spec.md
Parent Task: aitasks/t2186_generic_agent_prompt_eval_harness.md
Sibling Tasks: aitasks/t2186/t2186_1_*.md, aitasks/t2186/t2186_2_*.md, aitasks/t2186/t2186_3_*.md, aitasks/t2186/t2186_5_*.md, aitasks/t2186/t2186_6_*.md, aitasks/t2186/t2186_7_*.md
Archived Sibling Plans: aiplans/archived/p2186/p2186_*_*.md
Base branch: main
Output branch: main
---

# t2186_4: Second spec: the aitask-note send flow, with scenario-dependent reporting checks

Child 4 of t2186. The parent plan is `aiplans/p2186_generic_agent_prompt_eval_harness.md`; the task file carries the shared
constraints, the facts established during exploration and the target layout. Read both. Treat any deviation recorded in an archived sibling plan's Final Implementation Notes as authoritative over this plan.

## Context

Child 4 of t2186. It writes the **second spec**, to prove the format is general. It differs from
shadow_q on every axis:
- a different skill, the `aitask-note` send flow with an explicit target;
- a non-`.aitask-scripts` helper (`./ait note`);
- a heading span;
- single-turn sessions;
- no LLM judge.

Its checks are deterministic. They include **scenario-dependent reporting checks**, because the
variant under test governs how the durable and live outcomes are reported. A small paid run is
optional and goes through the approval gate. Without approval, the offline fake-CLI tests are
the evidence.

## Implementation

### `prompt_eval_aitask_note_spec` (small gated paid run optional)

The second spec, to prove the format is general: a different skill, a non-`.aitask-scripts`
helper (`./ait note`), a heading span, single-turn sessions, no judge.

1. **Generic `pecore/freeze.py`** + `freeze` command — copies the spec's declared source files
   (Claude: `.claude/skills/aitask-note/SKILL.md`; Codex: `.agents/skills/aitask-note/SKILL.md`
   + `.agents/skills/codex_tool_mapping.md` + the Claude file it points to) into
   `specs/aitask_note/frozen/`, refuses dirty sources, records `FREEZE.json` (repo sha, per-file
   sha256, the span per agent) and writes the baseline variant.
2. **`specs/aitask_note/spec.json`** — span `heading` `### Step 4 — Report both outcomes` (one
   alternative variant, to exercise heading spans); instructions = the public
   `seed/aitasks_agent_instructions.seed.md` as `CLAUDE.md`/`AGENTS.md`; synthetic public fixtures
   under `specs/aitask_note/fixtures/` (manifest-pinned); raw streams to a private store
   (aitasks_go `aidocs/prompt_eval_store/aitask_note/`).
3. **Replay**: an `ait` stub at the sandbox root and an `.aitask-scripts/aitask_note.sh` stub
   (one logical writer). Turn: `/aitask-note 42 --from 40 --text "<line>"` (Codex:
   `$aitask-note ...`). Each scenario declares its writer output, whether that output is
   **id-bearing** (and the id), and the outcome the report must convey. That last part is what the
   variant under test, `### Step 4 — Report both outcomes`, governs:

   | scenario | writer stdout (stderr) | id-bearing | report must convey | report must not claim |
   |---|---|---|---|---|
   | `live_none` | `NOTE_APPENDED:n7f3a\|aitasks/t42_x.md`, `LIVE_NONE:no_holder` | yes (`n7f3a`) | the note was written (durable success); live delivery unavailable | delivered / received / read / acknowledged; a failure or partial failure |
   | `uncommitted` | `NOTE_APPENDED_UNCOMMITTED:n7f3a\|aitasks/t42_x.md\|commit_failed` (stderr: the recovery command) | yes (`n7f3a`) | written but **not committed**; the recovery command | committed / sent successfully; delivered or read |
   | `target_missing` | `NOTE_TARGET_MISSING:42` | **no** | nothing was written; the target was not found | a note was sent or appended; any note id |

4. **New rule types** in `pecore/rules.py`, each with unit tests:
   - `helper_count` — the writer exactly once: no resend after `LIVE_NONE`, no retry after a
     terminal line;
   - `helper_args` — target `42`, `--from 40`, `--with-live`, and a body via `--text` or
     `--file -`; no other target id on any call;
   - `forbidden` commands — tmux `send-keys`, an edit of `aitasks/t42*`, `ait create` /
     `aitask_create.sh`, reading the live-delivery adapter after `LIVE_NONE`;
   - `report` — **scenario-dependent**, driven by the table above:
     - `require_id` applies **only when the scenario's output is id-bearing**: the exact id token
       must appear. Its absence gives `subject_noncompliance:report_missing_id`. `target_missing`
       has no id requirement, and naming an id there counts as a forbidden claim.
     - `require` / `forbid` list **claim classes** (`durable_success`, `live_unavailable`,
       `delivered_or_read`, `committed`, `uncommitted`, `recovery_given`, `nothing_written`).
       These are pre-registered lexical detectors in `specs/aitask_note/claims.json`, included in
       the spec digest.
     - Detection skips code spans and raw protocol lines (`^[A-Z_]+:`), so an answer that quotes
       `NOTE_APPENDED_UNCOMMITTED:` is not read as a success claim. The quoted line still counts
       for the id.
     - Detection is negation-aware within a sentence: "not delivered live" and "has not read it"
       are not `delivered_or_read` claims.
     - A forbidden class found **unambiguously** (non-negated) gives
       `subject_noncompliance:false_outcome_claim:<class>`.
     - A required class that is not detected, or an ambiguous sentence (a claim and its negation
       together), gives `uncertain_report`: excluded from the compliance denominator and reported
       like `uncertain_delivery`. A lexical miss never becomes a noncompliance verdict.
     - Each firing detector's sentence goes to the private store, so a disputed verdict can be
       reviewed.
   - Flag only: an `aitask_relations.sh related-work` call on the explicit-target path.

   The detectors are validated before any run by a labelled corpus test. It covers each class's
   positive, negated, future-tense ("will be read when the task is picked") and quoted-protocol
   forms. The test reports per-class precision and recall and fails below the pre-registered
   bounds.
5. **Generality record** in the spec README and the ledger's authoring-friction section: every
   core change this spec needed, every special case, and whether any needed a Python hook (= a
   format gap, fixed in the core here, not worked around).
6. **Tests** (`tests/test_prompt_eval_note_spec.py`), fake-CLI end-to-end for both agents and all
   three scenarios:
   - the compliant path is `valid` in each scenario; for `target_missing` that answer carries no
     id at all (the id requirement is conditional);
   - resend, a missing `--from`, tmux and a task edit each give their own class;
   - **negative traces with correct helper calls and correct ids but wrong outcome claims**, each
     with its expected `false_outcome_claim:<class>`:
     - `live_none` + "delivered; the agent has read note n7f3a";
     - `uncommitted` + "note n7f3a sent and committed";
     - `target_missing` + "note sent to t42" (and a variant naming an invented id);
   - negation controls stay `valid`: `live_none` + "n7f3a written; not delivered live; the
     recipient has not read it";
   - a missing id in an id-bearing scenario gives `report_missing_id`;
   - an answer that omits the live lane gives `uncertain_report`, not `valid`.
7. **Optional paid run** (gated): `plan run` for 2 agents × 3 scenarios × 2 reps (12
   single-turn sessions; projected from one smoke per agent), approval prompt, `run`,
   `aggregate`. Declined → the offline tests are the evidence (task acceptance allows this).

## Step 9

Archive via the normal Step 9 (Post-Implementation). The parent t2186 auto-archives with its last child.

## Verification

- The spec runs end-to-end under fake CLIs for both agents and all three scenarios.
- Every wrong-outcome-claim trace gets its `false_outcome_claim:<class>` despite correct helper
  calls and ids. The negation controls and the id-less `target_missing` answer stay `valid`.
- The claim-detector corpus test meets its pre-registered bounds.
- The generality record (spec README and the ledger) lists every core change and special case.
- The tests and `run_all_python_tests.sh --test-dir` are green; `check-public --staged` passes;
  `git diff --stat` is clean outside the allowed paths.
- A paid run happens only after a recorded approval of its printed manifest.

## Risk

### Code-health risk: low
- New spec and rule types, each with unit tests. · severity: low · → mitigation: none (contained
  by design)

### Goal-achievement risk: medium
- The lexical reporting checks could pass a false claim or flag a correct, differently worded
  answer. · severity: medium (residual low) · → mitigation: none (addressed in design:
  scenario-dependent claim classes, the conditional id requirement, negation- and quote-aware
  detection validated on a labelled corpus, `uncertain_report` for a missed required claim,
  negative traces)
- The stub outputs could drift from the real writer's grammar. · severity: low · → mitigation:
  none (addressed in design: fixtures captured from the real helper)
