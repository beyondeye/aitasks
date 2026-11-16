---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [sitrep, crash_recovery]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2299
implemented_with: claudecode/opus5_5
created_at: 2026-11-16 17:20
updated_at: 2026-11-16 18:23
---

## Context

t2299_4 taught the `/aitask-sitrep` skill that `crashed-agents` is a **virtual theme**: every crash-recovery item (`ref=recover:t<N>`) belongs to it, even though the crash detector writes recovery contexts with no `theme:` line (`Pass.context_entry`, `.aitask-scripts/lib/sitrep_crash.py`). The skill's "Requests from the sitrep TUI" `>w <theme>` check already accepts `crashed-agents` whenever `list` shows a `recover:` item.

The sitrep TUI's `w` key does not know this. `item_theme()` (`.aitask-scripts/sitrep_tui/sitrep_tui_requests.py:80`) reads only the item's context theme, so for a recovery item it returns `""`:
- the `w` binding is hidden on recovery items (`sitrep_tui_actions.py:691`, `bool(reqs.item_theme(self.store, item))`);
- `build_request` (`sitrep_tui_requests.py:97-100`) refuses to build `>w {theme}`.

So the user has to type `>w crashed-agents` to the agent by hand. This task closes that gap.

## Goal

Pressing `w` on a crash-recovery item (any state the other request keys accept) types `>w crashed-agents` into the sitrep agent, through the existing guarded delivery.

## Approach

- In `item_theme()` (or one small helper it calls): when the item's context has no valid theme and `st.parse_recover_ref(item.ref)` matches, return `crashed-agents`. Keep one source for that name: either a constant shared with the skill's documented theme, or at least one constant in `sitrep_tui_requests.py` that a test pins against the skill text.
- Keep detector ownership: nothing writes a theme into recovery contexts. This is a read-side mapping only.
- An explicit context theme always wins. A recovery item has none today, but the rule should not depend on that.
- `AGENT_REQUESTS` is unchanged (the template is still `>w {theme}`), so the skill-parity check in `tests/test_sitrep_skill_contract.sh` (section `r`) needs no change. Re-run it anyway.

## Docs to update (the "w does not apply" statements t2299_4 wrote)

- `.claude/skills/aitask-sitrep/SKILL.md.j2`, "Requests from the sitrep TUI": "The TUI never types it itself, since recovery contexts name no theme: the user types it." → the TUI types `>w crashed-agents` for a recovery item. Regenerate `tests/golden/skills/aitask-sitrep/SKILL-{default,fast,remote}-claude.md` in the same commit.
- `aidocs/framework/sitrep.md`: the request table's `w` row, and the TUI Actions note ("`w` unavailable on recovery items").
- `website/content/docs/tuis/sitrep/reference.md`: the `w` key row ("Never on a crash-recovery item …").
- `website/content/docs/tuis/sitrep/how-to.md`: the "The **w** key does not apply to crashed-agent items" note in "How to Resume Crashed Work".
- `website/content/docs/workflows/sitrep.md`: "Crashed agents" step 4 ("The TUI's `w` key does not apply to these items").
- Grep for any other "`w`" + "recovery" / "crashed-agents" mention before closing.
- Suggest a follow-up note to t2199 (the codex/opencode port of the skill) if the skill text changes.

## Verification

- `tests/test_sitrep_tui_requests.py`: a recovery item with no context theme → `item_theme` is `crashed-agents` and `build_request` gives `>w crashed-agents`. A non-recovery item with no theme still gives `""` (negative control). A recovery item with an explicit theme keeps it.
- `tests/test_sitrep_tui_actions.py` (or the requests app tests): the `w` binding is available on a recovery item while the agent runs.
- `bash tests/test_sitrep_skill_contract.sh`, `bash tests/test_skill_render_aitask_sitrep.sh`, `./.aitask-scripts/aitask_skill_verify.sh`.
- `cd website && python3 check_links.py --build`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-16T16:23:29Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-16T16:46:43Z status=pass attempt=1 type=human
