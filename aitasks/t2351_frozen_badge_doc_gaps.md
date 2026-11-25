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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2354** id=2026-11-25T07:54:27Z.71c989778315abd26368d2d3 from=t2354 from_verified=yes at=2026-11-25T07:54:27Z base=33ffb187c0449b3fc8fb4276c672111193b08bb4 base_branch=main dirty=yes host=omg16
>
> | t2354 (commit 33ffb187c) rewrote the passages this task edits, so its line ranges and quoted wording are stale:
> | 
> | - website/content/docs/workflows/freeze-and-restore-agents.md (~76-92): "After the word `frozen`, the row shows ..." now reads "In place of the word `frozen`, the row shows ... The cyan `F` beside the mark still says the agent is frozen:". "The row shows nothing extra until the state has been read" is now "Until the state has been read, the row shows `frozen`."
> | - website/content/docs/workflows/sitrep.md:41: the summary now says the row reads `frozen` until the state is read, then shows the state in place of `frozen`, and `sitrep ?` when it could not be read (never safe).
> | 
> | Why: the sitrep badge now REPLACES the word `frozen` on frozen list rows in both TUIs (monitor_shared.format_frozen_state). The 40-column minimonitor was cutting the task id off the name. The state list (unharvested / drop ok + triage|triaged|closed|review|? / sitrep ?) is unchanged, so this task's three gaps (a gloss for `triaged`, relref pointers for triage/review, "the follow-up word never blocks a drop") still apply. Edit against the new wording.
