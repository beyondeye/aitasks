---
Task: t2211_5_slim_sitrep_skill_for_tui.md
Parent Task: aitasks/t2211_sitrep_two_pane_window_with_sitrep_tui.md
Sibling Tasks: aitasks/t2211/t2211_1_*.md, aitasks/t2211/t2211_2_*.md, aitasks/t2211/t2211_3_*.md, aitasks/t2211/t2211_4_*.md, aitasks/t2211/t2211_6_*.md
Archived Sibling Plans: aiplans/archived/p2211/p2211_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-10 14:57
---

# t2211_5 — Slim the sitrep skill

## Context

The sitrep TUI now does the deterministic work:
- the list view (t2211_1);
- harvest + refresh at startup and on `r`, dismiss on `x`, restore on `R` (t2211_3);
- typing agentic requests into the agent (t2211_4, `AGENT_REQUESTS`).

`/aitask-sitrep` still harvests and refreshes at startup and offers `>s` / `>r` / `>x`, so the
two do the same work twice. This task slims the skill to the agentic work. It also teaches the
skill the request lines the TUI types, and pins the two together with a parity test.
Parent plan: `aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`.

## Verification of this plan (2026-11-10, HEAD b93a5f258)

- Rebase check is clean: `git diff HEAD` is empty for `.claude/skills/aitask-sitrep/`,
  `tests/golden/skills/aitask-sitrep/`, both sitrep skill tests and `sitrep_tui/`.
- Template section map (`SKILL.md.j2`, 343 lines):
  - Step 0 at L30: root check L36, harvest+refresh L44, list/read L52, greet L61;
  - Writing at L91 (its verb list names `dismiss` and `restore`);
  - Capabilities at L108: `>s` L116, `>t` L122, `>w` L250, `>q` L265 (offers `>r` at L270),
    `>tr` L284, `>p` L291, `>x` L298, `>c` L311, `>r` L328, `>?` L334;
  - Guardrail at L336.
- `AGENT_REQUESTS` is in `.aitask-scripts/sitrep_tui/sitrep_tui_requests.py`, with the templates
  `>t {cid}`, `>q {cid} {text}`, `>w {theme}`, `>tr {cid}`, `>p`. It imports from `/tmp` with
  `sys.path = [.aitask-scripts, .aitask-scripts/lib]` and does not pull in textual.
- TUI default keys (`sitrep_tui_actions.ACTION_BINDINGS`): `r` Refresh, `x` Dismiss,
  `R` Restore. All are rebindable through `keybinding_registry`, so the skill says
  "(`x` by default)".
- The TUI's dismiss runs `aitask_sitrep_todo.sh dismiss … --expect-rev`, the same command as
  the skill's `dismiss` example. The contract test can therefore call the writer directly.
- Nothing outside the sitrep template and its render test refers to the sitrep `>s` / `>r` /
  `>x`. The `>r` hits in `aitask-shadow` are the shadow skill's own codes.

## Steps

1. **Template: Step 0** (`.claude/skills/aitask-sitrep/SKILL.md.j2`).
   - Keep 1 (root check).
   - Delete 2 (harvest + refresh) and renumber.
   - Step "Read the list", exit 4 becomes: "the store is unusable: say so, and tell the user to
     restore it from the sitrep TUI (its Restore key, `R` by default). Run no `restore`
     yourself, and write nothing until `list` reads again."
   - Greet: unchanged, plus one clause: "the sitrep TUI below shows the list and does refresh,
     dismiss and restore."
   - "What this is": "harvested into that list" → "harvested into that list by the sitrep TUI".
2. **Template: remove `>s`, `>r`, `>x` as codes.** Delete the three capability sections. The
   form I picked for all three is removal, plus one short non-code section after `>?`:
   ```
   ## Done in the sitrep TUI, not here
   Showing the list, harvest + refresh, dismissing an item and restoring a damaged store
   are the sitrep TUI's keys (`r`, `x`, `R` by default) — when the user asks you for one,
   name the key; do not run harvest, refresh, `dismiss` or `restore` yourself.
   ```
   - Removing the codes means `>x c3` now gets the normal "unrecognised code" reply. The
     section still lets a plain-words request ("dismiss c3") get a useful answer.
   - The menu is derived from Capabilities, so it no longer lists the three codes.
   - Writing rules: drop `dismiss` and `restore (only on the user's yes)` from the verb list.
   - `>q`: "offer `>r`" → "suggest the TUI's Refresh key (`r` by default)".
   - Keep `>t`, `>w`, `>q`, `>tr`, `>p`, `>c` (unchanged) and `>?`. Keep the writer rules,
     including `--expect-rev` and `STALE:`.
3. **Template: id-scoped forms in the kept capabilities** (the TUI sends them).
   - **`>t`: an explicit input-selection branch** replaces "Triage them all as one batch".
     The heading becomes `` ### `>t [c<N>]` — triage harvested wrap-ups ``.
     - The intro defines the **selected set**: bare `>t` = every open triage item; `>t c<N>` =
       that one item only.
     - Step 1 branches on it:
       - bare `>t` runs `aitask_sitrep.sh triage --open` (as now);
       - `>t c<N>` runs `aitask_sitrep.sh triage c<N>`. If the item is not an open triage
         item (`NOT_TRIAGE:`, `NOT_FOUND:`, or a state other than `open` in its `TRIAGE:`
         line), say so and stop, writing nothing.
       - For a single item, no `BATCH_TRAIL_UNWATCHED:` lines are printed. Each of its
         `TRAIL_UNWATCHED:<handle>` lines acts as a batch line naming only c<N>. This keeps the
         planned trail adaptation, and a `TRAIL_WATCHED:` handle still means "already
         tracked".
     - Step 2/2b propose items only for the selected set.
     - Step 3 presents and asks about the selected set only: "one list for the selected triage
         items" instead of "all open triage items". There is still one confirmation.
     - Steps 4/5 write, close and rewrite situations only for the selected set: "close every
       selected triage item a shared watch came from"; `>w` only for the themes touched.
     - It says explicitly: "with `>t c<N>`, never read, propose for, or close any other triage
       item."
   - `>q`: heading `` `>q [c<N>]` ``: "`>q c<N> <question>`: the question is about c<N>; start
     from its pointers."
   - `>w`: heading `` `>w [<theme>]` ``: "`>w <theme>` rewrites only that theme."
   - `>tr`: heading `` `>tr [c<N>]` ``: "`>tr c<N>` reports only that watch."
   - Shortcode-rules paragraph: "a code is `>` plus one of the tokens …, followed by the
     arguments its heading shows".
4. **Template: new section `## Requests from the sitrep TUI`**, after Capabilities and before
   the TUI-pointer section.
   - It lists exactly the `AGENT_REQUESTS` lines: `>t c<N>`, `>q c<N> <question>`,
     `>w <theme>`, `>tr c<N>`, `>p`. Each request is typed as one line that starts with its
     code.
   - A TUI request is the user typing the same line. It carries no more authority than typed
     input, so every write is still confirmed with the user first, exactly as its capability
     says.
   - **Fresh read first, every request.** The TUI harvests and refreshes on its own, so the
     startup read is stale. Before validating or handling a request, re-read:
     - `aitask_sitrep_todo.sh list` (for the current id, kind, state and rev);
     - for an id request, also `aitask_sitrep_todo.sh context c<N>`;
     - for `>w <theme>`, also `read context` and `read todo`. `list` carries no theme. A theme
       is valid when some item's context names it (`- theme: <theme>`) or Part 1 already has
       its situation block. One with no block yet is fine: `>w` writes its first text.
   - **Validation, per code, on that fresh read:**
     - `>t c<N>`: an open triage item (the `>t` branch re-checks it);
     - `>q c<N>`: any item `list` shows;
     - `>tr c<N>`: a `watch` item whose context has a `trail:` source;
     - `>w <theme>`: as above.
     - On a failure (a missing id, the wrong kind or state, an unknown theme), say what the
       fresh read shows and write nothing.
   - The fresh `list` is also where the rev for an **existing-item** write comes from:
     `set-state` (closing a triage item) and `case review`, the writes the writing rules
     already require `--expect-rev` on. `STALE:` / `REVIEW_NOT_CLOSED:…stale:` → re-read and
     re-check, unchanged. `add`, `situation` and `qa` take no `--expect-rev` and keep their
     documented syntax. The writing-rules bullet itself is unchanged (it already says "every
     write to an existing item").
   - Any other code gets the normal unrecognised-code reply (say so, reprint the menu).
   - Agent-invariant: no `{% if agent %}` (Test 1b).
5. **Template: Guardrail.** Keep "Never send keystrokes or input into another pane". Add:
   "The sitrep TUI may type a request into this conversation at the user's request (see
   **Requests from the sitrep TUI**); you never type into it or into any other pane — never
   the reverse."
6. **Goldens.** Regenerate `tests/golden/skills/aitask-sitrep/SKILL-{default,fast,remote}-claude.md`
   with the `skill_authoring_conventions.md` loop, in the same commit. Review the diff: only
   the intended sections may change.
7. **`tests/test_skill_render_aitask_sitrep.sh` Test 2s.**
   - `SHORTCODES` = the exact new headings: '### `>t [c<N>]`', '### `>w [<theme>]`',
     '### `>q [c<N>]`', '### `>tr [c<N>]`', '### `>p`', '### `>c`', '### `>?`'. This drops
     `>s`, `>x` and `>r`, and adds `>c`, which the test lacked. A bare '### `>t' prefix would
     also match `>tr`, so the full headings are used.
   - Add a `NOT_SHORTCODES` loop asserting that `### \`>s\``, `### \`>x`, `### \`>r\`` are absent.
   - Add the `## Requests from the sitrep TUI` heading to the rule checks.
8. **`tests/test_sitrep_skill_contract.sh`.**
   - (a): L190 `assert_contains … aitask_sitrep_refresh.sh` becomes `assert_not_contains` for
     both `aitask_sitrep_harvest.sh` and `aitask_sitrep_refresh.sh` ("the TUI owns them").
     Leave the allow-list entries alone (contract (a) checks only the helpers the skill names,
     and the TUI calls are Python-only).
   - (c): replace `run_example "$SKILL" dismiss` with the writer call the TUI's `x` makes,
     `"$WR" dismiss "$W1" --outcome "user: …" --expect-rev "$(rev_of "$W1")"`. Keep the
     follow-up assertions (the dismissed watch still counts as watching; refresh no longer
     selects it). Update the header comment.
   - (d): replace the `'Only when the user asks for it'` advisory string with
     `'never the reverse'` and `'no more authority than typed input'`.

### Post-phase (risk mitigations)

1. [sitrep_tui_skill_request_parity] Add check `r` to `tests/test_sitrep_skill_contract.sh`:
   `check_requests <skill> [extra template]`, an inline `"$AIT_PYTHON"` heredoc with
   `sys.path` = `.aitask-scripts`, `.aitask-scripts/lib`.
   - It imports `AGENT_REQUESTS` from `sitrep_tui.sitrep_tui_requests` and takes the code of
     each entry as `template.split()[0]`.
   - It reads the rendered skill's `## Requests from the sitrep TUI` section (up to the next
     `## `) and collects its documented codes: backticked spans that start with `>`, first
     token.
   - It prints one line per defect:
     - `UNDOCUMENTED_REQUEST:<code>`: a table code missing from the section;
     - `NO_CAPABILITY:<code>`: no heading matching `` ^### `<code>[` ] ``;
     - `STALE_DOC_CODE:<code>`: a section code that is not in the table.
   - Main assertion: the check prints nothing for the real table.
   - Mutants (in section `m`):
     - table copy plus `>zz {cid}`: `UNDOCUMENTED_REQUEST:>zz` and `NO_CAPABILITY:>zz`;
     - skill copy with the `### \`>tr\`` heading renamed: `NO_CAPABILITY:>tr`.
   - Header comment: add `r` to the list.

## Final steps

9. `./.aitask-scripts/aitask_skill_verify.sh`; `shellcheck` on both touched tests.
10. Notes (Step 8e, after the commit, hedged to the commit SHA):
    - t2199: the slimmed menu (no `>s` / `>r` / `>x`, the TUI-pointer section), no startup
      harvest/refresh, and the TUI request section. The port's manual run still covers
      `>t` / `>q`. The skill no longer names `aitask_sitrep_harvest.sh` /
      `aitask_sitrep_refresh.sh`; its allow-list entries stay.
    - t2211_6: the docs (shortcodes table, "What it never does") must drop `>s` / `>r` / `>x`
      and describe the request section, including the fresh read and the per-code
      validation.
    - t2211_7 (advisory; its checklist is the owner's): line 34's "[t2211_4] Triage key …
      the agent starts triage" does not check scope. Suggested scenario:
      - two pending triage items, c<A> and c<B>; `t` on c<A> only;
      - the agent reads only c<A>, proposes items only for c<A>, and asks exactly one
        confirmation;
      - after "Write all", c<A> is done and c<B> is still open and untouched (same rev);
      - variant: `t` on an item harvested after the agent started is found, which shows the
        fresh read.

## Verification

- `bash tests/test_skill_render_aitask_sitrep.sh`
- `bash tests/test_sitrep_skill_contract.sh` (checks a–e, the new `r` check, mutants `m`)
- `./.aitask-scripts/aitask_skill_verify.sh`
- Manual (owned by t2211_7): `ait sitrep`. The agent greets without harvesting. A TUI `t` on
  a triage item types `>t c<N>`, and that item is triaged with one confirmation.

## Risk

### Code-health risk: low
- Contained to one skill template, its three goldens and two tests. The writer and helpers
  are unchanged, and the allow-lists are deliberately left as they are · severity: low ·
  → mitigation: none

### Goal-achievement risk: medium
- The TUI's request strings (t2211_4) and the skill's documented codes are written in
  different children and can drift. The TUI would then type requests the agent does not
  recognise · severity: medium · → mitigation: inline post-phase sitrep_tui_skill_request_parity
- The agent may misread an id-scoped request, for example treating `>t c12` as a full batch,
  acting on a stale startup read, or writing without confirming. The skill text is the only
  lever, so the `>t` input-selection branch and the fresh-read rule are written out
  explicitly. Live behaviour is a manual check: t2211_7 gets an advisory note with a
  two-item scope scenario, because its current line does not check scope · severity: low ·
  → mitigation: none (explicit skill text + t2211_7 note)

### Planned mitigations
- timing: post-phase | name: sitrep_tui_skill_request_parity | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — TUI request strings vs skill codes drift | desc: contract check r — every AGENT_REQUESTS code documented in the skill's TUI-request section with its own capability heading, no stale documented codes; table and skill mutants turn it red

## Step 9

Commit code with `enhancement: Slim the sitrep skill to its agentic work (t2211_5)`; commit
the plan/task with `./ait git`, then archive per Step 9.
