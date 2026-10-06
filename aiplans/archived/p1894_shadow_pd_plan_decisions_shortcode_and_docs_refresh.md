---
Task: t1894_shadow_pd_plan_decisions_shortcode_and_docs_refresh.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1894 — shadow `>pd` (plan decisions) + shadow shortcode docs refresh

## Context

Users repeatedly ask the shadow agent: *"explain the task in simple words and the
design decisions incorporated in the plan and the probable pros and cons"*. No
existing capability answers it: `>t` summarises the task but does not name the
plan's decisions; `>pa` lists premises as concerns; `>px` is an interactive
subject walkthrough. Add `>pd` as a plain-prose, on-request-only sub-procedure,
and make the website shortcode docs readable (table instead of a 110-word
bullet, a code on every capability section).

Exploration findings that shape the plan:
- No hardcoded shortcode/capability list exists in `.aitask-scripts/monitor/`,
  minimonitor or `lib/` — Step 3 of the template is the single registry.
- **Codex and OpenCode need no port.** `.agents/skills/aitask-shadow/SKILL.md`
  and `.opencode/skills/aitask-shadow/SKILL.md` are profile stubs that render
  the same `.claude/skills/aitask-shadow/SKILL.md.j2` with `--agent codex` /
  `opencode`; their closures (`.agents/skills/aitask-shadow-*-codex-/`, gitignored)
  already carry `task-summarize.md` etc. The "create port follow-ups" item in the
  task is therefore moot — the plan re-renders them instead, and the final
  report says so.
- The phase-advisory sweep (`tests/test_shadow_phase_advisory.sh`) globs **all
  nine** on-disk closures (claude/codex/opencode × 3 profiles). After adding
  `plan-decisions.md` to `CAPABILITIES`, every stale closure fails until it is
  re-rendered (the t1779 caveat) — so re-render all nine before running it.
- The worktree is shared and dirty with another session's edits
  (`concern-format.md`, `concern_parser.py`, `website/content/docs/{skills,workflows}/_index.md`, …).
  None overlap this task's files; commit with explicit paths only.

- A new procedure file joins **three** inventories, not one: Test 0's
  `PROC_FILES_INVARIANT` (it checks the arrays against the files on disk and
  fails otherwise), the phase-advisory `CAPABILITIES`, and the prose counts in
  `aidocs/framework/shadow_agent.md`.

Revised after review: (1) design decisions keep the alternatives a plan
explicitly rejects separate from comparisons the shadow adds itself, in the
procedure, the routing bullet and the docs; (2) the Step 5 inventory now
covers Test 0.

Working on current branch (`main`), profile `fast`.

## Steps

### 1. New sub-procedure `.claude/skills/aitask-shadow/plan-decisions.md`

Modelled section-for-section on `task-summarize.md`:
- Title "The Plan's Design Decisions, in Plain Words"; shortcode `>pd`; when to
  use; how it differs from `>t` (task-first, no decisions), `>pa` (concern
  producer), `>px` (interactive subjects), `>pc` (adversarial).
- **Never emitted unprompted.** **Not a concern producer** — no concern block,
  rejection store, snapshot or round header; `concern-format.md` does not apply;
  of `round-preamble.md` only §1 (audience) and §6's source selection apply.
- **Inputs:** shadow Step 2 task id → `aitask_shadow_context.sh <id>` →
  `TASK_FILE:` / `PLAN_FILE:`. Same `PLAN_FILE:NOT_FOUND` paragraph as
  `task-summarize.md` (ladder: single `~/.claude/plans/<name>.md` on the deep
  capture → deep capture itself, possibly partial; "could not be found from
  here", never "none exists").
- **Audience** + **Advisory-only** paragraphs (same wording pattern).
- **Procedure:**
  1. Resolve task id (degrade: no id → offer `>e`; `TASK_FILE:NOT_FOUND` → stop).
  2. Read task, then plan from the ladder; say in one line where the plan came
     from (and "possibly partial" for a capture). No plan → task part only, and
     say decisions need a plan (offer `>t` is not needed; just stop after part 1).
  3. Output, in order:
     - **The task in simple words** — what it achieves and why; a short version
       of `>t`'s first paragraph, not a repeat of the whole `>t`.
     - **The design decisions** — each: the choice (quoted/grounded in the
       plan text), then the alternatives, kept in **two distinct, labelled
       kinds** that are never merged:
       - **Rejected in the plan** — an alternative the plan text itself names
         and turns down. Only these may be called "rejected". Give the plan's
         reason, or "not stated in the plan" when it names the alternative but
         gives no reason.
       - **Possible comparison (not discussed in the plan)** — an alternative
         *you* bring in so the reader can see what the choice is being weighed
         against. Always labelled as such; never phrased as something the plan
         considered, chose against, or "implicitly rejected".
       A decision with neither kind just states the choice. Why the plan went
       this way: the plan's stated rationale, or "not stated in the plan" —
       never an invented one. Pick the decisions that shape the outcome (aim
       for 3–6), not every step.
     - **Probable pros and cons** — per decision (or for the overall approach
       when decisions are tightly coupled): what it buys, what it costs, what to
       watch for. Labelled *probable* — a judgement, not a finding.
  4. Writing rules (outcomes first, jargon unpacked, no paths/function names,
     a couple of minutes to read).
  5. One-line follow-up offer: `>pc` to challenge, `>pa` for assumptions, `>px`
     for a subject-by-subject walkthrough.

### 2. `.claude/skills/aitask-shadow/SKILL.md.j2` Step 3

Add a bullet right after `>t` under "Structured analyses":
`- `>pd` — **The plan's design decisions, with pros and cons** ("explain the
design decisions", "pros and cons of this plan", "why did it choose this
approach?") → read and follow `plan-decisions.md`. Plain prose for a
non-expert: the task in brief, each decision with the alternatives the plan
itself turns down (kept apart from comparisons the shadow adds, which are
labelled as not discussed in the plan) and the plan's stated reasons, and the
probable pros and cons. Not a concern producer, so it does not compose
with `>r`. **Never emit it unprompted** …`
The `>r` composition list and the "Only these four compose" sentence stay
unchanged. Step 0 derives the greeting from Step 3, so nothing else changes.

### 3. `.claude/skills/aitask-shadow/task-summarize.md` step 5

Follow-up line becomes: `>px` deeper walkthrough, `>pd` the plan's design
decisions and their pros and cons, `>pc` challenge, `>pa` assumptions.

### 4. Regenerate goldens + re-render closures

- Regenerate `tests/golden/skills/aitask-shadow/SKILL-{default,fast,remote}-claude.md`
  with the loop from `aidocs/framework/skill_authoring_conventions.md`
  ("Regenerate goldens…"); review the diff = only the new bullet.
- Re-render all nine closures:
  `aitask_skill_render.sh aitask-shadow --profile <p> --agent <a> --force` for
  p ∈ default/fast/remote, a ∈ claude/codex/opencode; confirm
  `plan-decisions.md` lands in each closure dir.

### 5. Tests — every procedure inventory, not just the shortcode list

`grep -rn task-summarize tests/ aidocs/` found every list a new procedure must
join. Without the first item, Test 0 fails, because it checks the arrays
against the skill dir on disk:

- `tests/test_skill_render_aitask_shadow.sh`:
  - `PROC_FILES_INVARIANT` (~line 69): add `plan-decisions`. The procedure is
    Jinja-free, so it is covered by Test 1i's profile×agent invariance sweep
    and needs no proc golden (only `impl-challenge` has goldens under
    `tests/golden/procs/aitask-shadow/`).
  - the comment above it: "the other ten are identity transforms" → "eleven".
  - Test 2s: add `` '`>pd`' `` to `SHORTCODES` and `` '`plan-decisions.md`' ``
    to `SHORTCODE_RULES`.
  - Add one content assertion (rendered `plan-decisions.md`, fast/claude, as
    the angles block does at ~line 363) that pins the grounding rule. It
    checks for the "Rejected in the plan" and "Possible comparison (not
    discussed in the plan)" labels and for "not stated in the plan", so
    removing the explicit-vs-inferred distinction later fails a test.
- `tests/test_shadow_phase_advisory.sh`: add `"plan-decisions.md"` to
  `CAPABILITIES`.

### 6. Website: `website/content/docs/workflows/shadow-agent.md`

- "What happens once it is running": replace "Two things are worth knowing:"
  with a count-free lead-in; keep the three remaining bullets (refetch,
  proactive offers, on-request-only — add "or explain the plan's design
  decisions" to the latter).
- Move the shortcode bullet into a new `### Shortcodes` subsection (end of
  that section) with a `| Code | What it does |` table: `>e`, `>q`, `>t`,
  `>pd`, `>px`, `>pc`, `>ps`, `>pa`, `>i` / `>i1`–`>i4`, `>r` / `>rpc` `>ri`
  `>rpa` `>rd`, `>d`, `>l`, `>f`, `>?`. Below the table, the rules as short
  bullets: `>` always required (a bare `t` is a message); works embedded when
  asking for it; mentioning one is not invoking it; `>?` reprints the list;
  only the four reviews (`pc`, `i`, `pa`, `d`) compose with `>r`; an
  unrecognised code is reported, not guessed.
- Name each section's code: Explain (`>e`), Help answer a prompt (`>q`),
  Interrogate a plan modes (`>px`/`>pc`/`>ps`/`>pa` inline in each bullet),
  Diagnose (`>d`), Learn a skill (`>l`); `>r` is already in "Follow where the
  review is heading" — add one sentence about `>r` to the Review the
  implementation section's tier paragraph only if absent (it isn't described
  there; leave the existing "Follow where…" mention as the home).
- "Interrogate a plan": "four distinct ways" → "five"; add a first bullet
  **Explain its design decisions** (`>pd`) — the task briefly, then each
  decision with the alternatives the plan itself turns down and its stated
  reason ("not stated in the plan" when it gives none); any other option the
  shadow mentions for contrast is labelled as not discussed in the plan, never
  presented as something the plan rejected; then the probable pros and cons.
  On request only, prose, no concerns. The shortcode table row and the aidocs
  bullet (Step 7) use the same explicit-vs-comparison wording.
- Current-state-only prose (documentation_conventions.md).

### 7. `aidocs/framework/shadow_agent.md`

- Prose counts: "eleven sub-procedure `.md` files (five `plan-*.md`, …,
  `task-summarize.md`)" (~line 72) → "twelve … (six `plan-*.md`, …)"; "the
  eleven sub-procedures are rendered into the Codex and OpenCode trees"
  (~line 86) → "twelve".
- Sub-procedure list: count sentence gains "one explains the plan's design
  decisions"; add a `plan-decisions.md` bullet after `task-summarize.md`
  (`>pd`, on request only, not a concern producer, §1 + §6 source selection
  only, does not compose with `>r`).
- Shortcodes paragraph: add `>pd` the plan's design decisions to the code list.

### 8. Small consistency touch

`.aitask-scripts/aitask_shadow_capture.sh` comment (~line 78) listing the
plan-* sub-procedures that use `--deep`: add `plan-decisions`.
Concept page and minimonitor/monitor how-to pages enumerate capabilities only
generically (no shortcode lists) — no change.

### Post-phase (risk mitigations)

1. [pd_rerender_all_closures] Before running `tests/test_shadow_phase_advisory.sh`,
   run `./.aitask-scripts/aitask_skill_render.sh aitask-shadow --profile <p> --agent <a> --force`
   for every p ∈ {default, fast, remote} × a ∈ {claude, codex, opencode}, then
   `ls` each of the nine closure dirs (`.claude/skills/aitask-shadow-<p>-/`,
   `.agents/skills/aitask-shadow-<p>-codex-/`, `.opencode/skills/aitask-shadow-<p>-/`)
   and confirm `plan-decisions.md` is present and the closure `SKILL.md`
   contains `plan-decisions.md`. Only then trust a red/green sweep result.

## Verification

- `bash tests/test_skill_render_aitask_shadow.sh` (goldens + Test 2s)
- `bash tests/test_shadow_phase_advisory.sh` (after the nine re-renders)
- `./.aitask-scripts/aitask_skill_verify.sh`
- `cd website && python3 check_links.py --build` (anchors: `#shortcodes`, any
  renamed headings — none are renamed)
- `shellcheck .aitask-scripts/aitask_shadow_capture.sh` (comment-only edit; sanity)
- Commit (code + goldens + tests + docs together, explicit paths only):
  `enhancement: Add shadow >pd plan-decisions shortcode and refresh shortcode docs (t1894)`

Step 9 (Post-Implementation) handles archival; current-branch mode, no merge.
Final report notes: no Codex/OpenCode port tasks needed (shared template);
t1780 may want a `>pd` manual-verification item (send an `ait note`, not a task).

## Risk

### Code-health risk: low
- The phase-advisory sweep reads on-disk closures without re-rendering (t1779); adding `plan-decisions.md` to `CAPABILITIES` turns every stale closure (all nine, incl. codex/opencode) red until re-rendered · severity: low (residual — addressed by inline post-phase pd_rerender_all_closures) · → mitigation: inline post-phase pd_rerender_all_closures
- Shared dirty worktree: another session's uncommitted shadow/website edits sit beside this task's files; a directory-wide stage would sweep them in · severity: low · → mitigation: none (covered by the explicit-path commit in Verification)

### Goal-achievement risk: low
- `>pd` output could drift into repeating `>t`, inventing rationale, or presenting alternatives the plan never considered as "rejected"; the procedure separates "Rejected in the plan" from labelled "Possible comparison (not discussed in the plan)", forces "not stated in the plan" for missing reasons, and Step 5 pins those labels with a test assertion · severity: low · → mitigation: none (covered by Step 1 wording + Step 5 assertion)
- A new procedure that misses one of the inventories (Test 0's `PROC_FILES_INVARIANT`, the phase-advisory `CAPABILITIES`, the aidocs counts) fails CI or goes stale · severity: low · → mitigation: none (Step 5/7 enumerate every inventory found by `grep -rn task-summarize`)

### Planned mitigations
- timing: post-phase | name: pd_rerender_all_closures | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: stale-closure false red in the phase-advisory sweep (t1779) | desc: force-re-render all nine shadow closures and confirm plan-decisions.md is in each before running the sweep

## Final Implementation Notes
- **Actual work done:** New `.claude/skills/aitask-shadow/plan-decisions.md` (`>pd`), modelled on `task-summarize.md`: on request only, not a concern producer, same inputs/plan-source ladder/audience rule; output = task in brief → 3–6 design decisions with alternatives in two never-merged kinds ("Rejected in the plan" vs labelled "Possible comparison (not discussed in the plan)"), stated rationale or "not stated in the plan" → probable pros and cons → follow-up offer. `SKILL.md.j2` Step 3 gained the `>pd` bullet after `>t`; `task-summarize.md` step 5 offers `>pd`. Three claude goldens regenerated (diff = the new bullet only). Tests: `PROC_FILES_INVARIANT` + comment count (Test 0), Test 2s codes/rules, a new grounding-rule content assertion block on the rendered `plan-decisions.md`, and the phase-advisory `CAPABILITIES`. Website `workflows/shadow-agent.md`: shortcode bullet replaced by a `### Shortcodes` table + rule bullets, every capability section names its code, "Two things" → "A few things", "four distinct ways" → "five" with a new `>pd` mode, on-request-only bullet gains design decisions. `aidocs/framework/shadow_agent.md`: counts eleven→twelve / five→six `plan-*.md`, sub-procedure bullet, shortcode list. `aitask_shadow_capture.sh` comment names `plan-decisions` among the `--deep` users (rewrapped).
- **Deviations from plan:** None in substance. The capture-script comment was rewrapped across the whole paragraph rather than a one-word insertion, to keep the line width.
- **Issues encountered:** None. All nine closures (claude/codex/opencode × 3 profiles) were force-re-rendered before the phase-advisory sweep (inline post-phase `pd_rerender_all_closures`); each carries `plan-decisions.md`. Results: render test 744/744, phase sweep 55/55, `aitask_skill_verify.sh` OK, `check_links.py --build` PASSED; shellcheck on the capture script reports only the pre-existing SC1091 infos.
- **Key decisions:** Codex/OpenCode need no port tasks — their `aitask-shadow` stubs render the same `.claude` template, so re-rendering delivers `>pd` there. `>pd` kept out of the `>r` composition list (not a round-headed concern producer). Proc goldens not needed: `plan-decisions.md` is Jinja-free and covered by Test 1i invariance.
- **Upstream defects identified:** None
