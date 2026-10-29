---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui_switcher]
followup_kind: upstream_defect
created_at: 2026-10-30 01:16
updated_at: 2026-10-30 01:16
---

## Origin

Spawned from aitasks_go#t19_1 (the Go port of the TUI switcher data model)
during its Step 8b review. The Go port reproduces this behaviour faithfully,
pinned by its Python-oracle fixture, so a fix here will show up there as fixture
drift on regeneration (`app/switcher/testdata/gen_switcher_fixture.py`).

## Upstream defect

- `.aitask-scripts/lib/tui_switcher.py:950-960` (`TuiSwitcherOverlay._populate_list_for`):
  a running `brainstorm-<n>` window is listed twice in the switcher. It appears
  once as the "Brainstorm (t<n>)" TUI entry and again as a plain window row
  under "Other".

## Diagnostic context

`_populate_list_for` adds every `brainstorm-<n>` it finds, from disk and from
running windows, to the TUIs group. The non-TUI loop that follows only skips
names in `_TUI_NAMES`, and `brainstorm-<n>` is not in that set (only the bare
"brainstorm" is). `_classify_window` then returns "tui" for it through the
`BRAINSTORM_PREFIX` rule, and the split there is `cat == "agent"` vs
everything else. So the "tui"-classified window lands in `others` and is
rendered under the "Other" header. Observed at aitasks `cd7ab3b2d`: with
running windows `stats`, `brainstorm-7`, `agent-pick-7`, the list is
`TUIs … Brainstorm (t7)` / `Code Agents: agent-pick-7` /
`Other: brainstorm-7`.

## Suggested fix

In the non-TUI loop, skip any window whose `_classify_window` result is "tui".
That covers both `_TUI_NAMES` and the `brainstorm-` prefix. Alternatively,
make the loop skip `name.startswith(_BRAINSTORM_PREFIX)` as well. Add a test
that a running `brainstorm-<n>` window appears exactly once.
