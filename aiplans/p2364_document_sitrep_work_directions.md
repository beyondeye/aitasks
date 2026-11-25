---
Task: t2364_document_sitrep_work_directions.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Define work directions in the Sitrep workflow guide. Explain how the agent groups items during triage and how trail evidence helps identify blockers and the next work to land.

## Files Modified

- `website/content/docs/workflows/sitrep.md` gains a short **Work directions** section before **Crashed agents**.

## User Intent

Give website readers a concise definition that makes clear who decides which items fit together and when that grouping is saved.

## Final Implementation Notes

- The definition describes the current triage flow. The agent reads wrap-ups, proposes a grouping, and saves the items after the user confirms.
- The broader website comparison between directions and implementation trails is tracked in t2335_4.
- `python3 check_links.py --build` passed in `website/` with zero broken links. `git diff --check` passed for the website edit.
