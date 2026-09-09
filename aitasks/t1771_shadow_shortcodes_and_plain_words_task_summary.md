---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [shadow, claudeskills]
gates: [risk_evaluated]
created_at: 2026-09-09 19:31
updated_at: 2026-09-09 19:31
---

## Goal

Two additions to the shadow companion skill (`/aitask-shadow`):

1. **Shortcodes for every shadow capability.** Each capability in Step 3 of
   `SKILL.md.j2` gets a short code so the user does not have to type the full
   ask ("challenge the plan", "review the implementation at the advanced
   tier", …). The codes are listed in the Step 0 greeting ("what the shadow can
   do"), and the implementation-review codes select a specific effort tier.
2. **A new on-demand sub-procedure — "the task in simple words".** When the
   followed agent is working a task (a `<source_task_id>` is known), the shadow
   can produce a plain-language description of what that task is about, based
   on the task description and — when one exists — the current plan, so a
   human who did not read the task or plan gets the idea in a minute. It is
   **never shown automatically**; it is reachable through its shortcode (or by
   asking in words), and the greeting names it.

## Decisions already taken (from the exploration)

- **Shortcode form:** single letters with a `>` prefix as the canonical
  spelling (`>e`, `>t`, `>i3`, …). A message that is *exactly* a bare code
  (`t`, `i3`) is also routed; a prefixed code is recognised even when embedded
  in a sentence (`>i3 but only the callers` → advanced review, scoped). `>`
  was chosen because it is not a reserved leading character in any supported
  agent's input (Claude Code: `/` `!` `@` `#`; Codex CLI: `/` `@`; OpenCode:
  `/` `!` `@`) and does not clash with the `<name>:<path>` cross-repo notation
  a `:` prefix would.
- **Tier shortcodes:** separate digit codes — `>i1` quick, `>i2` default,
  `>i3` advanced, `>i4` deep. Bare `>i` runs the existing resolution ladder
  (wording > profile `shadow_impl_review_tier` > ask). A digit code counts as
  **explicit wording** (rank 1 in `impl-challenge.md`'s "Resolution order"),
  so it overrides the profile default and, like any named tier, needs no
  "inferred tier" announcement.
- **Auto-show policy for the task summary:** never automatic. (The original
  idea of showing it at startup unless the followed agent is asking a question
  was dropped in favour of shortcode-only access; do not add a startup
  auto-show.)

## Proposed shortcode table (adjust letters during planning if they collide)

| code | capability | serves via |
|---|---|---|
| `>e` | explain the screen / "what is the agent doing?" | inline (Step 3) |
| `>q` | help answer the `AskUserQuestion` on screen | inline (Step 3) |
| `>t` | the task in simple words (task + current plan) | **new** `task-summary.md` |
| `>x` | explain the plan to a non-expert | `plan-explain.md` |
| `>c` | adversarially challenge the plan | `plan-challenge.md` |
| `>i` / `>i1`–`>i4` | review the implementation (tier per ladder / quick / default / advanced / deep) | `impl-challenge.md` |
| `>r` | recheck round — refetch and re-run the last review sub-procedure | Step 3 recheck rule |
| `>s` | socratic questioning of the plan | `plan-socratic.md` |
| `>a` | surface the plan's assumptions | `plan-assumptions.md` |
| `>d` | diagnose skill/helper errors in the followed agent | `plan-diagnose-errors.md` |
| `>l` | learn a skill from what the followed agent did | `spawn-learn-skill.md` |
| `>f` | refetch the followed agent's screen now | Step 1 |
| `>?` | print the shortcode list again | Step 0 greeting text |

## Where the pieces live (exploration findings)

- Source of truth: `.claude/skills/aitask-shadow/SKILL.md.j2` (profile-aware
  stub + template, resolver key `shadow`) plus nine sub-procedures. **Step 0
  derives the greeting's capability list from Step 3** — a maintainer note
  forbids a second hardcoded copy — so the shortcode for each capability must
  be declared **next to its Step 3 entry** (e.g. as a leading `` `>c` `` token
  on each bullet, or a compact table at the top of Step 3), and Step 0 renders
  the code with each phrase. Step 0 must also state the `>`-prefix / bare
  whole-message rule in one line, and mention `>?`.
- `impl-challenge.md` "Tier selection" — add the four digit codes to the
  explicit-wording bullets (`>i1` → Quick, …) so they sit at rank 1 of the
  resolution order. This file is Jinja-gated on `shadow_impl_review_tier`;
  keep both arms consistent.
- New `task-summary.md` (name to be settled in planning; keep the
  `<topic>-<verb>.md` shape used by the siblings). Inputs: Step 2's
  `./.aitask-scripts/aitask_shadow_context.sh <source_task_id>` — read
  `TASK_FILE:` and, when not `NOT_FOUND`, `PLAN_FILE:`. **No new helper is
  needed.** Output: a few short paragraphs in everyday language — what the
  task is trying to achieve and why, what will change for a user, and (when a
  plan exists) how the agent intends to get there and roughly how far along
  it is; no jargon unless immediately unpacked; lead with outcomes. Degrade
  gracefully: no task id → ask once, else say it cannot summarise without one;
  `PLAN_FILE:NOT_FOUND` → summarise the task alone and say no plan exists yet.
  Distinct from `plan-explain.md` (plan-only, interactive per-subject
  introductions): this one is non-interactive and task-first.
- Resolve the source task id via Step 2's existing rules (argument → window
  name `agent-pick-<id>` / screen → ask once).

## Pinned contracts that must be extended in the same change

- `tests/test_shadow_phase_advisory.sh` — `CAPABILITIES` array lists every
  sub-procedure filename that must remain dispatched from every rendered
  closure (`.claude/`, `.agents/`, `.opencode/` trees); add the new file.
  It also sweeps for phase-conditioned refusals: the new sub-procedure and the
  shortcodes must **never** gate on `PHASE`/`WAITING` (every capability at
  every phase; a shortcode is just a spelling of the ask).
- `tests/test_skill_render_aitask_shadow.sh` + goldens under
  `tests/golden/skills/aitask-shadow/SKILL-<profile>-claude.md` and
  `tests/golden/procs/aitask-shadow/impl-challenge-<profile>.md` — regenerate
  in the same commit after the `.md.j2` / `impl-challenge.md` edits, and
  review the diff (see `aidocs/framework/skill_authoring_conventions.md`,
  "Regenerate goldens after any `.md.j2` or closure edit"). Add an assertion
  that each tier digit code appears in the explicit-wording bullets of both
  Jinja arms, and one that the greeting-side rule text (prefix + bare form)
  survives rendering.
- `aidocs/framework/shadow_agent.md` "The skill" section — the sub-procedure
  count ("nine") and the per-sub-procedure list; add the new one and a short
  "Shortcodes" paragraph (canonical prefix, bare-whole-message rule, tier
  digits, `>?`).
- Run `./.aitask-scripts/aitask_skill_verify.sh` before committing.
- `seed/` mirrors of shadow-related config are unaffected (no new helper, no
  new profile key).

## Out of scope / follow-ups to spawn

- Porting to the other agent trees: `.agents/skills/aitask-shadow*` (Codex)
  and `.opencode/skills/aitask-shadow*` are rendered from the same template
  by `aitask_skill_render.sh`, so they follow automatically — but verify the
  rendered closures there and create separate follow-up tasks if any
  hand-maintained wrapper (`.opencode/commands/aitask-shadow.md`) needs the
  shortcode list.
- Any minimonitor-side key that would *send* a shortcode to the shadow pane
  is a separate feature (t1118 covers driving the shadow over applink).

## Acceptance criteria

- Greeting (Step 0) lists every capability with its shortcode, states the
  `>`-prefix / bare-whole-message rule, and names `>?`.
- Sending `>t` (or `t`) with a known source task id produces a plain-words
  summary built from the task file and, if present, the current plan; it is
  never emitted unprompted at startup or after a refetch.
- `>i3` runs the advanced implementation review with no tier prompt and no
  "inferred tier" line, regardless of the profile's `shadow_impl_review_tier`;
  `>i` behaves exactly as today's "review the implementation".
- All shadow tests listed above pass; goldens regenerated; skill_verify clean.
