---
priority: low
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [documentation, website, frozen_agents, sitrep]
file_references: [website/content/docs/workflows/freeze-and-restore-agents.md:76-92, website/content/docs/workflows/sitrep.md:41]
premise_baseline: 72bdd15db100fcb8a344f167ac12e23363e47589 @ 2026-11-24 12:35
created_at: 2026-11-24 12:35
updated_at: 2026-11-24 12:35
---

Close three small gaps in the user docs for the frozen-agent sitrep badge (t2337), the
words shown after `frozen` on a frozen agent's row in `ait monitor` / `ait minimonitor`.

The badge words are already documented in
`website/content/docs/workflows/freeze-and-restore-agents.md` (step 6, "Drop the agent
when you are done with it", around lines 76-92), and
`website/content/docs/workflows/sitrep.md:41` points there. Gaps found in review:

1. **`triaged` has no gloss.** The list gives `triage (still to triage)`, `closed
   (dismissed or otherwise closed)`, `review (...)`, `? (...)`, but `triaged` is bare.
   Add a short meaning: every linked triage question has been triaged (done).
2. **No pointer to what to do.** For `triage` and `review`, link to where the user acts:
   the sitrep page's triage step (step 4, "Triage the wrap-ups") and its
   "Output the harvest could not read" section. Use `{{< relref >}}` with anchors.
3. **`drop ok, triage` reads as "don't drop yet".** State explicitly that the follow-up
   word never blocks a drop: the open triage / review item stays in the sitrep list
   after the agent is dropped, so dropping is still lossless.

Ground truth for each state is `aidocs/framework/sitrep.md` ("Frozen-agent badge
(t2337)", around line 683) and the module docstring of `.aitask-scripts/lib/frozen_sitrep.py`.
Keep the website prose at user level (the derivation rules stay in aidocs). Follow
`aidocs/framework/documentation_conventions.md` and `aitasks/metadata/doc_update_guide.md`
(current-state only, no version history).

Verification: `cd website && hugo build --gc --minify && python3 check_links.py --build`.
