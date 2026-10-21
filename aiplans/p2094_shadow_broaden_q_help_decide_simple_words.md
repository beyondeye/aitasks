---
Task: t2094_shadow_broaden_q_help_decide_simple_words.md
Base branch: main
Output branch: main
---

# t2094 — Broaden shadow `>q` into "help me decide what to do now"

## Context

`>q` in the shadow skill only covers one situation: the followed agent is showing
an `AskUserQuestion`. It doesn't re-capture first, doesn't explain the situation,
has no plain-language rule, and does nothing defined when the agent is stuck,
erroring, waiting on a plan, finished or still working. The user currently types
"refetch, explain in simple words, and help me decide what to do" by hand. This
task makes `>q` that one-code shortcut. `>e` stays explain-only (no
recommendation) so the two codes don't overlap. Prose-only change to a skill
template + its docs; no script behaviour changes.

Brainstorm-discuss's own `>q` and multi-code messages are out of scope.

## Steps

1. **`.claude/skills/aitask-shadow/SKILL.md.j2`**
   - Frontmatter `description` (line 3): replace "helps answer an
     AskUserQuestion" with "helps the user decide what to do next (including
     answering an AskUserQuestion)".
   - Line ~18, "(explain something, help answer a prompt, or pressure-test a
     plan)" → "(explain something, help decide what to do next, or pressure-test
     a plan)".
   - Proactive-offer sentence (~line 145–146): "the screen now shows an
     `AskUserQuestion` → offer to help the user decide" → "the screen now shows
     an `AskUserQuestion`, or the agent has stopped and is waiting on the user →
     offer `>q` to help the user decide what to do".
   - `>e` bullet: append one sentence — "Explanation only: give no
     recommendation; when the user wants to know what to *do*, that is `>q`."
   - Replace the `>q` bullet with:
     ```
     - `>q` — **Help me decide what to do now** ("help me decide", "what should
       I do?", "what do I answer?", "explain it simply and help me decide") — in
       **every** state the followed agent can be in, not only when it is asking
       a question:
       1. **Capture the screen again first.** Run Step 1
          and re-read `--phase`, even if you captured recently.
       2. **Gather whatever context the decision needs** — you are not limited
          to the followed agent's captured output.
       3. **Explain the situation in simple words.**
       4. **Then the decision.**
          - **An `AskUserQuestion` is on screen:** explain each option and its
            trade-offs and **suggest** an answer with your reasoning.
          - **Any other state** (still working, stuck or erroring, a plan
            waiting for approval, finished): list the realistic next moves —
            wait, approve the plan, answer, interrupt or redirect the agent, or
            ask for a deeper shadow capability such as `>d`, `>pc` or `>i` — and
            recommend one with a short reason. A deeper capability is
            **offered by its shortcode, never started on your own**; the user
            asks for it.
       5. Remind the user that whatever they decide, they type it into the
          followed agent themselves — you do not.
     ```
   - Wording check: no `refuse` / `do not run` / `not available` etc. within 2
     lines of the word "phase" (the Layer-2 sweep in
     `tests/test_shadow_phase_advisory.sh`).

2. **Stub descriptions** — same new description string in
   `.claude/skills/aitask-shadow/SKILL.md`, `.agents/skills/aitask-shadow/SKILL.md`,
   `.opencode/skills/aitask-shadow/SKILL.md`, `.opencode/commands/aitask-shadow.md`.

3. **`.aitask-scripts/aitask_shadow_capture.sh`** — comment-only: the list of
   ordinary reads "(explain-output, help-answer-prompt, diagnose-errors)" →
   "(explain-output, help-decide, diagnose-errors)".

4. **Goldens** — regenerate `tests/golden/skills/aitask-shadow/SKILL-{default,fast,remote}-claude.md`
   with the loop from `aidocs/framework/skill_authoring_conventions.md`
   ("Regenerate goldens…"); review the diff is only the template edits. Also
   re-render the per-profile variants (`aitask_skill_render.sh aitask-shadow
   --profile <p> --agent <a>`) if they are tracked/needed by tests.

5. **`tests/test_skill_render_aitask_shadow.sh`** — new `Test 2q` after Test 2s,
   per profile render of the template:
   - contains: `` `>q` — **Help me decide what to do now** ``,
     `**Capture the screen again first.**`, `re-read `--phase``,
     `**Explain the situation in simple words.**`,
     `you are not limited`,
     `**An `AskUserQuestion` is on screen:**`,
     `**Any other state**`, `never started on your own`,
     `Explanation only: give no recommendation`
   - not contains the old title `Help answer an `AskUserQuestion``.
   - Stub check: each of the 4 stubs contains the new description phrase
     "helps the user decide what to do next".

6. **`aidocs/framework/shadow_agent.md`** — line ~113 proactive example
   ("an `AskUserQuestion` is up, or the agent is waiting on the user → offer
   `>q`"); lines ~122–124 inline asks: describe `>q` as help deciding what to do
   now (re-capture, plain-words situation, then options + suggestion for an
   `AskUserQuestion`, or next moves + recommendation in any other state, deeper
   capabilities only offered; context-gathering is not limited to the agent's
   captured output),
   `>e` explain-only; line ~184 "`>q` help with the
   prompt" → "`>q` help decide what to do now".

7. **`website/content/docs/workflows/shadow-agent.md`** — line 35 proactive
   example; table row `>q` → "Explain the situation simply and help you decide
   what to do now"; `>e` row unchanged; rename section "### Help you answer a
   prompt" → "### Help you decide what to do" and rewrite the paragraph to the
   new contract, stating that the shadow is not limited to the agent's screen
   when gathering context for its advice (no inbound anchors to the old heading — grep found none). Add
   to the `>e` paragraph that it explains without recommending (use `>q` for
   that). Run `python3 check_links.py --build` in `website/`.

## Verification

- `bash tests/test_skill_render_aitask_shadow.sh` (goldens + new Test 2q)
- `bash tests/test_shadow_phase_advisory.sh` (Layer-2 sweep stays clean)
- `bash tests/test_audit_wrappers_render_opencode_command.sh` (opencode
  command stub description)
- `./.aitask-scripts/aitask_skill_verify.sh`
- `cd website && python3 check_links.py --build`
- `shellcheck .aitask-scripts/aitask_shadow_capture.sh`

## Step 9

Post-implementation: commit code + goldens + docs together
(`enhancement: … (t2094)`), plan via `aitask_task_commit.sh`, then archive per
task-workflow Step 9.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
