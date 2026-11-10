---
priority: medium
effort: medium
depends: [t2211_4]
issue_type: enhancement
status: Implementing
labels: [sitrep, codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
implemented_with: claudecode/opus5_5
created_at: 2026-11-05 15:37
updated_at: 2026-11-10 14:59
---

## Context

Child 5 of t2211. The sitrep TUI now owns the deterministic work:
- showing the list (t2211_1);
- harvest + refresh at startup and on a key, dismiss, restore (t2211_3);
- typing agentic requests into the agent (t2211_4).

This child slims `/aitask-sitrep` to the genuinely agentic work and teaches it to recognise
requests typed in by the TUI. Parent plan:
`aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`. Per CLAUDE.md, change the Claude
Code skill first. t2199 (codex/opencode port) consumes it, so send it a note.

## First step: rebase check

t2175_6 landed in `6fc7b3972`. It added `>c` (unparsed-output corpus: `case list` /
`case replay`), triage step 2b for unparsed reviews, the `case review` writer and contract
case e. Re-read the landed `.claude/skills/aitask-sitrep/SKILL.md.j2`, the goldens,
`tests/test_sitrep_skill_contract.sh` and `tests/test_skill_render_aitask_sitrep.sh`, and
confirm they are clean against HEAD. Also read the landed t2211_4 `AGENT_REQUESTS` table.

## Current skill (verify line numbers)

`SKILL.md.j2` (~343 lines), with no Jinja gates beyond `{{ profile.name }}`:
- Step 0 (L30):
  - root check `aitask_sitrep.sh root` (L36);
  - startup harvest `aitask_sitrep_harvest.sh all --root .` + refresh
    `aitask_sitrep_refresh.sh --root .` (L44);
  - `list` + `read todo`, with exit 4 offering `restore` (L52);
  - greeting + menu (L61).
- Capabilities (L108): `>s` show (L116), `>t` triage (L122), `>w` (L250), `>q` (L265),
  `>tr` (L284), `>p` (L291), `>x` dismiss (L298), `>c` corpus (L311), `>r` re-run harvest
  (L328), `>?` (L334).
- Guardrail (L336): it says the agent "never send[s] keystrokes into another pane".

## Changes

1. Step 0: root check, then `list` + `read todo`, then the greeting (counts, open triage
   items, menu).
   - Remove the startup harvest/refresh: the TUI owns it (user decision "decide once").
   - On exit 4, tell the user to restore from the sitrep TUI. Do not run `restore`.
2. Remove `>s`, `>r` and `>x` as capabilities, or reduce each to a one-line pointer "use the
   sitrep TUI" (pick one, consistently).
   - Keep `>t`, `>w`, `>q`, `>tr`, `>p`, `>?`, and `>c` as t2175_6 landed it (or decide
     explicitly to move `case list` to the TUI and say so; default keep).
   - Keep the writer rules (incl. `--expect-rev`, `STALE:` re-read) and the advisory
     guardrail.
3. New section "Requests from the sitrep TUI": the TUI types the same `>` codes carrying item
   ids, exactly as listed in `AGENT_REQUESTS` (`>t c12`, `>q c12 <text>`, `>w <theme>`,
   `>tr c12`, `>p`).
   - A TUI request carries no more authority than typed input: the agent still confirms
     before writing.
   - An unknown code gets the normal menu reply.
4. Guardrail: the agent never types into another pane. The sitrep TUI may type into the
   agent at the user's request, never the reverse.
5. Regenerate the three goldens in the same commit, using the command in
   `aidocs/framework/skill_authoring_conventions.md` "Regenerate goldens" (loop over
   default/fast/remote with `lib/skill_template.py`).
6. Update the tests:
   - `tests/test_skill_render_aitask_sitrep.sh` Test 2s `SHORTCODES` (~L108-123: drop the
     removed codes);
   - `tests/test_sitrep_skill_contract.sh`:
     - L190 asserts the skill names `aitask_sitrep_refresh.sh`; adjust;
     - the `run_example "$SKILL" dismiss` (~L246-252) and the follow-up refresh assertion
       move to a TUI-side or writer-level test, or stay if `>x` keeps a documented example;
     - the advisory string `'Only when the user asks for it'`.
   - Contract (a): every helper the skill names exists and appears in the 5 permission files.
     Dropping a helper from the skill leaves its allow-list entries harmless; do not remove
     them blindly (the TUI calls are Python-only and need none, per
     `aidocs/framework/aitasks_extension_points.md` ~L394-403).
7. **Post-phase risk mitigation `sitrep_tui_skill_request_parity`** (from the parent plan):
   - add a test (in `tests/test_sitrep_skill_contract.sh`, or a small Python test it calls)
     that imports `AGENT_REQUESTS`;
   - it asserts that every template starts with a `>` code listed in the rendered skill's
     "Requests from the sitrep TUI" section, and that that code's `### \`>x\`` capability
     heading exists;
   - add a mutant (a copy of the table with an unknown code) that must turn it red.
8. Run `./.aitask-scripts/aitask_skill_verify.sh`.
9. Send a note to t2199:
   `./ait note 2199 --from 2211_5 --with-live --file - <<'EOF' … EOF`, describing the slimmed
   menu, the removed startup harvest, and the TUI request section (the port's manual run
   still covers `>t` / `>q`). Hedge that it was written against the committed SHA.

## Verification

- `bash tests/test_skill_render_aitask_sitrep.sh`, `bash tests/test_sitrep_skill_contract.sh`,
  `./.aitask-scripts/aitask_skill_verify.sh`.
- Manual: `ait sitrep`. The agent greets without harvesting. A `>t c<N>` typed by the TUI is
  triaged with one confirmation.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2211_3** id=2026-11-09T07:38:19Z.247a5366bbb061fae6d784a4 from=t2211_3 from_verified=yes at=2026-11-09T07:38:19Z base=706bf2f6d8f8138a01cacd722201196cbfbf1aba base_branch=main dirty=yes host=omg16
>
> | t2211_3 (committed in 706bf2f6d) moved deterministic work into the sitrep TUI: harvest + refresh now run at TUI startup (and on `r`), and dismiss (`x`, with --expect-rev) and restore (`R`, `restore --if-damaged`) are TUI keys. The skill's startup harvest/refresh and its >r / >x / restore guidance can be removed or reduced to "use the TUI" as your task plans. Advisory context only.

> **✉ note:t2211_4** id=2026-11-10T10:44:51Z.b08af7ffe841df7e4fc2417f from=t2211_4 from_verified=yes at=2026-11-10T10:44:51Z base=e16e440e4036bf3929b3d0a60a54f81be2f11003 base_branch=main dirty=yes host=omg16
>
> | Advisory (a claim from t2211_4, code commit e16e440e4, tree-relative). For your request-parity test:
> | 
> | - `AGENT_REQUESTS` is defined once, in `.aitask-scripts/sitrep_tui/sitrep_tui_requests.py`. `sitrep_tui.sitrep_tui_app.AGENT_REQUESTS` re-exports the same object, so either import works.
> | - Entries are `AgentRequest(action, key, label, template)` (a frozen dataclass), in this order:
> |   `request_triage t ">t {cid}"`, `request_ask a ">q {cid} {text}"`, `request_situation w ">w {theme}"`, `request_trail_refresh T ">tr {cid}"`, `request_pick_advice n ">p"`.
> |   The code to check against the skill is `template.split()[0]`.
> | - The TUI fills `{cid}` as `c<N>` and `{theme}` from the item's context theme (`THEME_RE`). `{text}` is the user's one-line question: single-spaced, with no control characters and no trailing @mention.
> | - A typed request is always one line starting with `>`. The skill should treat it exactly like the user typing the same code (same authority, still confirm before writing).

> **👁 note:read** id=2026-11-10T11:34:18Z.cd56084bce83c354cfd31cb1 by=t2211_5 at=2026-11-10T11:34:18Z mode=explicit ids=2026-11-09T07:38:19Z.247a5366bbb061fae6d784a4,2026-11-10T10:44:51Z.b08af7ffe841df7e4fc2417f

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-10T12:59:12Z status=pass attempt=1 type=human
