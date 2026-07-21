---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1149
created_at: 2026-07-21 13:04
updated_at: 2026-07-21 17:35
---

## Context

Follow-up to t1186_4 (chatlink wizard allowlist live pickers). Raised and
confirmed during the t1186_4 implementation review; dispositioned as a
follow-up rather than an in-task fix.

`AllowlistScreen._apply_fetch` (`.aitask-scripts/chatlink/wizard.py`) treats a
failed fetch as advisory and returns early:

```python
if result is None:
    status.update("! fetch failed — enter ids manually above "
                  "(Next still works)")
    return
```

That is correct for a *first* fetch (the picker was never revealed, so manual
entry is all that is offered). It is wrong for a **refresh**: rows already
visible from a prior successful fetch — or restored from the Back-survivable
cache on re-entry — are left rendered, ticked, and selectable while the status
line says the fetch failed.

## Reproduction (confirmed)

1. Open the wizard, reach "Who may open a bug report", press "Fetch from
   Discord" with a working runner. Rows appear; select one.
2. Press Back, then forward again — the cached rows are restored and revealed.
3. Press "Fetch from Discord" again with the runner now failing.

Observed: status reads `! fetch failed — enter ids manually above`, while the
member/role `SelectionList`s still show the previous rows, still selectable;
`_commit_state` re-caches them (with provenance) on Back/Next.

## Severity / what is NOT wrong

This is a **staleness and clarity** defect, not a wrong-context authorization
leak. The retained rows always belong to the *current* context: `_fetch_key` is
unchanged and `_pending_key` is adopted only on success, so the cache-key
revalidation and picker-origin removal in `_restore_cache` still hold. The risk
is that the operator is told the fetch failed while being shown rows they may
reasonably read as current (a member who has since left, a deleted role).

## Options (pick one during planning)

1. **Clear on failed refresh** — drop `self._fetched`, `self._fetch_key`, and
   hide the picker widgets, so a failed refresh degrades to the same
   manual-entry-only state as a failed first fetch. Simplest and most
   consistent; costs the operator their visible selection context.
2. **Label the retained rows** — keep them but state plainly that they are the
   previous fetch, e.g. `! refresh failed — showing the rows fetched earlier
   (they may be out of date)`. Preserves work; requires the notice to persist
   rather than be overwritten by the next status update.

Option 2 is likely the better UX (it does not punish a transient network blip
by discarding selections), but option 1 is the safer default if the wording
cannot be made prominent enough.

## Key files

- `.aitask-scripts/chatlink/wizard.py` — `AllowlistScreen._apply_fetch`,
  `_reveal_picker`, `_commit_state`.

## Verification

Extend `tests/test_chatlink_tui.sh` (the t1186_4 picker section already has the
`wiz_spy_fetch` seam with a `raise` switch and `canned()` results):

- successful fetch, then a failing refresh → assert the chosen behaviour
  (rows hidden/cleared, or a notice naming them as the earlier fetch);
- the first-fetch failure path still degrades to manual entry and still
  advances (existing assertions must stay green);
- whichever option is chosen, `_commit_state` must not silently re-cache rows
  the UI has declared stale.
