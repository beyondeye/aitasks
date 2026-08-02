---
priority: medium
effort: low
depends: []
issue_type: test
status: Ready
labels: [aitask_monitor, aitask_monitormini, tui]
gates: [risk_evaluated]
anchor: 1326
created_at: 2026-07-30 10:34
updated_at: 2026-07-30 10:34
boardidx: 840
---

## Context

Risk-mitigation "after" task for **t1326**, generalizing a guard it pinned for
one key only.

t1326 added a bare `space` App-level binding and, while testing it, established a
fact worth spreading: **Textual does not dispatch App-level `BINDINGS` while a
`ModalScreen` is active**, so a bare single-key binding cannot fire from inside a
dialog. That was *measured*, not assumed — an initial implementation comment
claimed the protection came from the action's own focus guard, and a negative
control disproved it (`tests/test_monitor_modal_space_dispatch.py`).

t1326 pins that behaviour for `space` only.

## Goal

Audit every bare single-key App-level binding in both monitor TUIs for modal
leakage, and pin the ones that are unguarded.

Bare single-key bindings at the time of writing —
`minimonitor_app.py`: `k n p e E c j q s i I m M d space`;
`monitor_app.py`: `j q s i r z t k n R A M L d c space`.

## Acceptance criteria

- [ ] Enumerate the bare single-key App bindings in both TUIs from `BINDINGS`
      rather than a hand-copied list, so the audit cannot silently go stale
- [ ] A test drives `pilot.press(<key>)` with a real `ModalScreen` pushed and
      asserts the action does not fire, for every key in that set
- [ ] Each negative assertion is paired with a positive control proving the key
      DOES route with no modal — otherwise the test passes for the wrong reason
- [ ] The guard is expressed once (parametrized), not copy-pasted per key
- [ ] If any binding turns out NOT to be protected, fix it and note which

## Reference

- `tests/test_monitor_modal_space_dispatch.py` — the shape to generalize,
  including its explicit note on what actually protects the modal case
