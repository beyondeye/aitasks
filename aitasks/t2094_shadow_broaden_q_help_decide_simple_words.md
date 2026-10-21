---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [shadow, skills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-21 12:13
updated_at: 2026-10-21 12:33
---

## Goal

Broaden the shadow agent's `>q` shortcode from "help answer an
`AskUserQuestion`" into a general **"help me decide what to do now"**, so one
code gives what the user currently has to type in full:
*"refetch, explain in simple words, and help me decide what to do"*.

## Current state (found during exploration)

`>q` is an **inline** capability in `.claude/skills/aitask-shadow/SKILL.md.j2`
(Step 3, the `>q` bullet, ~lines 278–282). Compared with the target prompt it:

1. **Has no explicit re-capture.** Step 1 says to re-capture "whenever fresh
   state is needed", so this is left to the shadow's judgement. If the agent has
   moved on since the last capture, `>q` can answer about an old screen.
2. **Only covers one situation:** the followed agent is showing an
   `AskUserQuestion` with options. It has no defined behaviour when the agent is
   stuck, erroring, waiting on a plan, finished, or still working.
3. **Goes straight to the options.** It doesn't first explain the situation
   (where the agent is and why it stopped). `>e` explains but gives no
   recommendation.
4. **Has no plain-language requirement.** Trade-offs can come out in the
   plan's technical terms.

There is no combined form: only `>r<code>` composition is defined, and
several codes in one message (`>f >e >q`) is not defined.

## Proposed new `>q` contract

1. **Always capture the screen again first.** Run Step 1
   (`aitask_shadow_capture.sh`, argument-free) and re-read `--phase`, so the
   answer is about the current screen.
2. **Explain the situation in simple words:** a few sentences on what the agent
   is doing, what it is waiting on, and why. Avoid jargon, or define any
   technical term it can't avoid in one clause.
3. **Then the decision:**
   - **`AskUserQuestion` on screen:** keep today's behaviour (fetch source
     context via Step 2 if needed, explain each option and its trade-offs, and
     suggest an answer with reasoning), now in plain words.
   - **Any other state:** list the realistic next moves (wait, approve the
     plan, answer, interrupt or redirect the agent, or run a deeper shadow
     capability such as `>d`, `>pc` or `>i`) and recommend one with a short
     reason. Deeper capabilities are **offered, never run automatically**.
4. **Advisory-only, unchanged:** the user types any answer into the followed
   agent themselves.

`>e` stays as "explain only, no recommendation", so the two codes don't overlap.
Free-text asks like "help me decide what to do" should now go to `>q` in every
state, not only when an `AskUserQuestion` is up.

## Touchpoints

- `.claude/skills/aitask-shadow/SKILL.md.j2`: the `>q` bullet (title + body),
  and the proactive-offer sentence (~line 146, "an `AskUserQuestion` → offer to
  help the user decide"). Also consider the frontmatter `description`
  ("helps answer an AskUserQuestion"); if it changes, update the matching
  `description` in the stubs `.agents/skills/aitask-shadow/SKILL.md` and
  `.opencode/skills/aitask-shadow/SKILL.md`.
- Goldens: regenerate `tests/golden/skills/aitask-shadow/SKILL-{default,fast,remote}-claude.md`
  in the same commit (see "Regenerate goldens after any `.md.j2` or closure
  edit" in `aidocs/framework/skill_authoring_conventions.md`). Run
  `./.aitask-scripts/aitask_skill_verify.sh` before committing.
- `tests/test_skill_render_aitask_shadow.sh`: line ~268 only checks that `>q`
  is present. Add assertions for the new contract (re-capture first, simple
  words, a defined behaviour when no `AskUserQuestion` is on screen, deeper
  capabilities only offered).
- `aidocs/framework/shadow_agent.md`: ~lines 113, 122, 184 describe `>q` as
  "help answer an AskUserQuestion" / "help with the prompt".
- `website/content/docs/workflows/shadow-agent.md`: shortcode table row
  (~line 46) and the `>q` paragraph (~line 78). Run
  `python3 check_links.py --build` in `website/` afterwards.

No Codex or OpenCode port tasks are needed: their shadow skills are
profile-aware stubs that render from the same Claude `.md.j2` template.

## Out of scope

- The brainstorm-discuss skill's own `>q` ("ask anything") is a separate code
  namespace. Leave it unchanged.
- Defining general multi-code messages (`>f >e >q`).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-21T09:33:36Z status=pass attempt=1 type=human
