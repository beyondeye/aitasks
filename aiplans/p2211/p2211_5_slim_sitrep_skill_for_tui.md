---
Task: t2211_5_slim_sitrep_skill_for_tui.md
Parent Task: aitasks/t2211_sitrep_two_pane_window_with_sitrep_tui.md
Sibling Tasks: aitasks/t2211/t2211_1_*.md, aitasks/t2211/t2211_2_*.md, aitasks/t2211/t2211_3_*.md, aitasks/t2211/t2211_4_*.md, aitasks/t2211/t2211_6_*.md
Archived Sibling Plans: aiplans/archived/p2211/p2211_*_*.md
Base branch: main
Output branch: main
---

# t2211_5 — Slim the sitrep skill

Parent plan: `aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`. The task file holds
the current section map and the test assertions that change.

## Steps

1. **Rebase check.**
   - Re-read `.claude/skills/aitask-sitrep/SKILL.md.j2`, the goldens,
     `tests/test_sitrep_skill_contract.sh` and `tests/test_skill_render_aitask_sitrep.sh` as
     landed (t2175_6), and the landed `AGENT_REQUESTS` (t2211_4).
   - `git diff HEAD -- <files>` must be empty.
2. **Edit the template.**
   - Step 0: root check, then `list` + `read todo`, then the greeting. Exit 4 → point to
     the TUI's restore.
   - Remove `>s`, `>r` and `>x` (or one-line "use the sitrep TUI" pointers; pick one form
     for all three).
   - Keep `>t`, `>w`, `>q`, `>tr`, `>p`, `>?` and `>c`.
   - New "Requests from the sitrep TUI" section listing exactly the `AGENT_REQUESTS` codes:
     the same authority as typed input, still confirm before writing.
   - Guardrail sentence: the TUI types into the agent, never the reverse.
   - Agent-invariant: no `{% if agent %}` (Test 1b).
3. **Goldens.** Regenerate the default/fast/remote goldens with the
   `skill_authoring_conventions.md` loop, in the same commit.
4. **Tests.**
   - Render test 2s `SHORTCODES`.
   - Contract: the L190 refresh assertion, the dismiss example + the follow-up refresh
     assertion (move to a writer-level test or keep if `>x` keeps an example), the advisory
     string.

### Post-phase (risk mitigations)

1. [sitrep_tui_skill_request_parity] Add a parity test that imports `AGENT_REQUESTS`
   (Python, called from `tests/test_sitrep_skill_contract.sh` or standalone). Every template
   must start with a code listed in the rendered skill's "Requests from the sitrep TUI"
   section, and that code's `### \`>x\`` heading must exist. A mutant (a table copy with an
   unknown code) must turn it red.

## Final steps

5. `./.aitask-scripts/aitask_skill_verify.sh`.
6. Note to t2199 via `/aitask-note` (or `./ait note 2199 --from 2211_5 --with-live --file
   -`): the slimmed menu, no startup harvest, the TUI request section. Hedge that it was
   written against the committed SHA.

## Verification

- `bash tests/test_skill_render_aitask_sitrep.sh`, `bash tests/test_sitrep_skill_contract.sh`,
  `./.aitask-scripts/aitask_skill_verify.sh`.
- Manual: `ait sitrep`. The agent greets without harvesting. A TUI `t` request is triaged
  with one confirmation.

## Step 9

Commit with `enhancement: … (t2211_5)` and archive.
