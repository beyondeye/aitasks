---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [minimonitor, switcher, website]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
anchor: 2174
followup_kind: upstream_defect
created_at: 2026-10-31 22:00
updated_at: 2026-10-31 22:19
---

## Origin

Spawned from t2174 during Step 8b review.

## Upstream defect

- `website/content/docs/tuis/minimonitor/how-to.md:394-401` — "How to Jump to Another TUI" lists `minimonitor` as a switcher entry ("the current TUI"), although the switcher never lists it, and it omits trails, stats, syncer, applink, chatlink and frozenagent.

## Diagnostic context

While documenting t2174 (Shift+M in the TUI switcher adds a minimonitor beside the host TUI), the switcher sections of the TUI docs were cross-checked against `.aitask-scripts/lib/tui_registry.py` / `_build_tui_list`. `website/content/docs/tuis/_index.md` states, correctly, that minimonitor is not listed in the switcher. t2174 fixed the same inaccuracy in `website/content/docs/tuis/monitor/_index.md` (it listed minimonitor), but left this how-to list alone because it was out of scope.

## Suggested fix

Rewrite the list from the switcher's registry (`switcher_tuis()` in `.aitask-scripts/lib/tui_registry.py`) or replace it with a link to the canonical switcher description in `website/content/docs/tuis/_index.md`. Drop the minimonitor row. Run `cd website && python3 check_links.py --build` afterwards.
