---
Task: t986_6_shadow_docs.md
Parent Task: aitasks/t986_shadow_agent.md
Sibling Tasks: aitasks/t986/t986_2_phase_autodetection_module.md, aitasks/t986/t986_7_manual_verification_shadow_agent.md
Archived Sibling Plans: aiplans/archived/p986/p986_1_multi_agent_window_substrate.md, aiplans/archived/p986/p986_3_task_plan_context_fetch.md, aiplans/archived/p986/p986_4_shadow_skill.md, aiplans/archived/p986/p986_5_minimonitor_trigger_spawn_config.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-15 18:28
---

# Plan: t986_6 — Docs (aidocs + website) for the shadow agent

## Context

The shadow agent feature (parent t986) has fully landed across children
t986_1..t986_5: a minimonitor-triggered (`e`) advisory companion coding agent
that captures a followed agent's tmux terminal output and, in one
instruction-driven flow, explains it / helps answer a prompt / critically
challenges a plan. It launches in the **same tmux window** by default,
classified as a helper pane (excluded from agent lists) via the
`@aitask_shadow_target` pane user option, and is read-only/advisory toward the
source agent. The supporting refactor re-keyed monitor state by `pane_id` so a
tmux window can robustly hold N real agents.

This task documents that landed behavior in the `aidocs/` specialist rules and
the website. A v0.25.0 blog post already introduces the shadow at a changelog
level — this task adds the durable **reference** docs.

### Verification findings (verify path, 2026-06-15)

- Deps **all landed & archived** (t986_1..t986_5); plan assumptions confirmed
  against the archived plans and the current tree.
- **t986_2 (phase autodetection) was Postponed/dropped** — no `phase_detect.py`,
  no AskUserQuestion/phase markers were added. So the original plan's step to
  touch `monitor_idle_and_prompt_detection.md` **drops out** (no change). The
  architecture is **capture → context-fetch → skill** (no phase-detect stage);
  phase is a one-line deferred/advisory note only.
- Concrete facts to document (from the archived plans):
  - `@aitask_shadow_target` pane user option = authoritative shadow classifier
    **and** lifecycle binding (t986_1); a same-window shadow shares the agent's
    window name, so the option — not the window name — identifies it.
  - minimonitor `e` → `action_launch_shadow` (t986_5).
  - Config: `defaults.shadow` codeagent default (seed `claudecode/opus4_8`,
    project `claudecode/sonnet4_6`) + `tmux.shadow_same_window` placement toggle.
  - `/aitask-shadow <followed_pane_id> [<task_id>]` user-invocable command;
    captures on demand via `aitask_shadow_capture.sh` (t986_4).
  - Advisory-only: never injects keystrokes/answers into the source pane.

### Current `aitask-shadow` skill surface (read 2026-06-15 — document THIS)

The skill has evolved since t986_4 landed; the docs must describe its **current**
shape, not the archived-plan description. Confirmed by reading
`.claude/skills/aitask-shadow/` today:

- **Invocation:** `/aitask-shadow <followed_pane_id> [<source_task_id>]`,
  `user-invocable: true`. Static skill: `SKILL.md` + four `plan-*.md`
  sub-procedures (no profile/`.j2`/stub).
- **Step 0 — greeting:** on startup, before any capture/fetch, it greets the user
  and presents its capability list **derived from Step 3** (Step 3 is the single
  source of truth; a maintainer note forbids hardcoding a second copy). It also
  tells the user they can refetch the screen any time and can just describe what
  they want in their own words.
- **Step 1 — capture:** `aitask_shadow_capture.sh <pane_id>` (escape-free,
  cleaned; `-` stdin mode cleans pasted output). **Proactive after-every-capture
  suggestion:** on each capture (first and every refetch) it glances at what is
  *visibly* on screen and, if a capability is obviously useful (e.g. an
  AskUserQuestion is up → offer to help decide; a plan awaits approval → offer to
  explain/challenge/surface assumptions), offers it unprompted. This is explicitly
  a lightweight on-screen look, **not** a workflow-phase classifier, and never
  gates what the user can ask.
- **Step 2 — context fetch (only when needed):** `aitask_shadow_context.sh
  <task_id>` → `TASK_FILE:`/`PLAN_FILE:` lines (`--siblings` adds `SIBLING:`
  lines); `aitask_explain_context.sh --max-plans N <files>` for deeper history.
  Degrades gracefully on `NOT_FOUND`/unknown task id.
- **Step 3 — serve (one flow, routed by the ask):**
  - *Inline:* explain output / "what is the agent doing?"; help answer an
    `AskUserQuestion` (lay out options + trade-offs, **suggest** an answer the
    user types themselves).
  - *Structured sub-procedures (read-and-follow):* `plan-explain.md` (surface the
    technical subjects the plan rests on; offer per-subject intro+motivation via a
    multiSelect, then a plain-language walkthrough), `plan-challenge.md`
    (adversarial — attack regressions, edge cases, wrong-shape, blast-radius /
    "edited unaware", verification gaps, unstated deps; prioritized weaknesses;
    fatal vs fixable), `plan-socratic.md` (open-ended non-leading questions, 2–4
    at a time), `plan-assumptions.md` (enumerate env/data/behavior/sequencing/
    intent assumptions; flag load-bearing-and-unverified ones first). Broad asks
    ("review this plan") run several in sequence.
- **Guardrail (load-bearing):** read-only w.r.t. the followed agent — never sends
  keystrokes/answers into its pane.

## Implementation steps

### aidocs
1. **`aidocs/framework/tmux_gateway.md`** — add a short section "Multiple real
   agents per window — key state by `pane_id`": a tmux window may hold N real
   agents; monitor/minimonitor state is keyed by `pane_id`, not `window_name`;
   the shadow companion pane is excluded from agent lists via the
   `@aitask_shadow_target` pane user option (the authoritative classifier).
   Cross-ref the tui_conventions companion-pane section and `shadow_agent.md`.
2. **`aidocs/framework/tui_conventions.md`** — extend the "Companion pane
   auto-despawn" section: the shadow pane is a **second** companion-pane case
   alongside minimonitor (same-window by default); it auto-kills when its bound
   followed agent dies (via `@aitask_shadow_target`), independent of other agents
   in the window; note pane_id-keyed agent accounting.
3. **NEW `aidocs/framework/shadow_agent.md`** — architecture doc reflecting the
   **current** skill (per the surface above): the capture → context-fetch → skill
   pipeline (`aitask_shadow_capture.sh` → `aitask_shadow_context.sh` /
   `aitask_explain_context.sh` → `/aitask-shadow`); the skill's Step 0 greeting +
   Step-3-derived capability list (single source of truth) and the proactive
   after-capture suggestion (on-screen look, not a phase classifier); the four
   structured sub-procedures (explain / challenge / socratic / assumptions); the
   `@aitask_shadow_target` binding; spawn path (minimonitor `e`, `shadow`
   codeagent op, same-window/separate-window config); advisory-only guardrail;
   one-line "phase autodetection deferred (t986_2)" note. Add a one-line pointer
   to it from `CLAUDE.md` near the TUI/monitor docs so it is discoverable.
   - **Skip** `monitor_idle_and_prompt_detection.md` (verification finding above).

### website
4. **`website/content/docs/tuis/minimonitor/how-to.md`** — add a "How to Launch
   a Shadow Agent" section (key `e`: spawns the advisory companion in the same
   window, passes the followed pane id), add an `e` row to the Key Bindings Quick
   Reference table, and document the two settings
   (`tmux.shadow_same_window`, `defaults.shadow` via `ait settings` → Agent
   Defaults). Add a brief mention to `minimonitor/_index.md` distinguishing the
   shadow companion from the minimonitor companion.
5. **NEW `website/content/docs/workflows/shadow-agent.md`** — user-facing
   workflow page describing the **current** skill behavior: what the shadow is;
   launching it from minimonitor (`e`); the startup greeting and that it offers a
   relevant capability whenever it (re)reads the screen; the capabilities —
   explain the output / help answer a prompt the agent is stuck on / and the four
   plan-interrogation modes (explain-to-a-non-expert, adversarial challenge,
   Socratic questioning, assumption surfacing); that it can refetch the screen at
   any time; advisory-only design; same-window default + placement/model config.
   Generic placeholder project names; current-state-only prose.
6. **`website/content/docs/workflows/_index.md`** — add a bullet under the
   **Review & Quality** grouping linking the new page (it is about understanding
   and interrogating an agent's output/plans). The sidebar auto-builds; the index
   body is hand-curated.

## Verification

- `cd website && hugo build --gc --minify` succeeds with **no broken
  references**.
- All `relref`/relative cross-references resolve; the `_index.md` bullet is
  present and the page renders in the Review & Quality group.
- Doc prose follows `aidocs/framework/documentation_conventions.md`:
  current-state-only (no version history in bodies), generic agent naming
  (don't enumerate specific coding agents), invented placeholder project names.
- Spot-check command/key names against the landed surface (`e`,
  `/aitask-shadow`, `@aitask_shadow_target`, `tmux.shadow_same_window`,
  `defaults.shadow`).
- Re-read `.claude/skills/aitask-shadow/SKILL.md` + the four `plan-*.md` files
  just before writing prose and confirm the docs match the **current** skill
  (Step 0 greeting, proactive after-capture suggestion, the four sub-procedures,
  advisory-only) — not the older t986_4 description.

## Risk

### Code-health risk: low
- Docs-only change: one new aidocs file, edits to two existing aidocs, one new
  website page, minimonitor how-to/_index edits, one curated index bullet, and a
  one-line CLAUDE.md pointer. No code paths or load-bearing logic touched ·
  severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The feature is fully landed and was verified against the archived
  t986_1..t986_5 plans, so the docs describe real behavior; the only realistic
  failure mode is a broken Hugo cross-reference, caught by the `hugo build`
  verification step · severity: low · → mitigation: none needed

_No `### Planned mitigations` subsection: both axes are low and mitigated
in-scope by the `hugo build` check and the documentation-conventions review. No
before/after follow-up task would add value._

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9 (child-task path:
archive to `aitasks/archived/t986/` + `aiplans/archived/p986/`; parent t986
archives only when all children complete — t986_7 manual-verification sibling
remains).

## Final Implementation Notes

- **Actual work done:** Documented the landed shadow agent feature across aidocs
  and the website (docs-only, no code touched).
  - `aidocs/framework/tmux_gateway.md` — new "Multiple real agents per window —
    state keyed by `pane_id`" section + a `shadow_agent.md` See-also link.
  - `aidocs/framework/tui_conventions.md` — new "The shadow agent is a second
    companion-pane case" subsection under "Companion pane auto-despawn" (exclusion
    via `@aitask_shadow_target`, pane_id-keyed accounting, bound-agent auto-kill).
  - `aidocs/framework/shadow_agent.md` (NEW) — architecture: capture →
    context-fetch → skill pipeline; the **current** skill surface (Step 0
    greeting + Step-3-derived capability list, proactive after-capture
    suggestion, inline + four `plan-*.md` sub-procedures); `@aitask_shadow_target`
    binding; minimonitor `e` spawn + `shadow` codeagent op; `defaults.shadow` and
    `tmux.shadow_same_window` config; advisory-only; phase-detect deferred.
  - `CLAUDE.md` — pointer to `shadow_agent.md` in the TUI Development section.
  - `website/content/docs/tuis/minimonitor/how-to.md` — "How to Launch a Shadow
    Agent" section, `e` row in the Key Bindings Quick Reference, config note.
  - `website/content/docs/tuis/minimonitor/_index.md` — "Launching a shadow
    agent" subsection distinguishing the shadow companion from minimonitor.
  - `website/content/docs/workflows/shadow-agent.md` (NEW, weight 83) +
    `workflows/_index.md` bullet under the Review & Quality grouping.
- **Deviations from plan:** (1) `monitor_idle_and_prompt_detection.md` was
  **not** touched — verification confirmed t986_2 (phase autodetection) was
  Postponed/dropped, so no AskUserQuestion/phase markers exist to document
  (anticipated in the plan's verification findings). (2) Per user steer mid-pick,
  the docs were written against the **current** `aitask-shadow` skill (read
  2026-06-15: Step 0 greeting, proactive after-capture suggestion, four
  sub-procedures), not the older t986_4 description.
- **Issues encountered:** None. `hugo build --gc --minify` passes (214 pages, no
  broken refs; only pre-existing `LanguageDirection`/`AllPages` deprecation
  warnings, unrelated to this change).
- **Key decisions:** Split user-facing coverage between the minimonitor TUI docs
  (where the `e` trigger lives) and a dedicated workflows page (the feature's
  capabilities), with the durable architecture in a new `aidocs/` specialist
  page; kept agent naming generic in the workflow prose and limited literal
  `claudecode/...` config tokens to config-reference contexts.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t986_7 (manual verification):** the docs now describe the expected live
    behavior to verify — `e` spawns the shadow same-window, it is absent from the
    agent list, killing the followed agent auto-kills the shadow, and the skill's
    greeting + proactive suggestion + advisory-only flow work as documented.
  - **t988 / t989 (Codex / OpenCode `/aitask-shadow` ports):** the
    `shadow_agent.md` and workflow page are agent-agnostic; no doc changes needed
    when those wrappers land unless they introduce agent-specific surfaces.
