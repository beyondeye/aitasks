---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_board]
children_to_implement: [t228_1, t228_2, t228_3, t228_4]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-24 08:13
updated_at: 2026-02-24 09:14
---

the ait sync script and the sync functionality in ait board handle syncing and automatic merging for aitask definitions I would like to improve automatic merging of aitask metadata according the the following rules 1) conflict on boardcol and boardidx: retain local defintion discard value from remote 2) updated_at field: retain latest date/time 3) labels: merge list 4) depends: merge list 5) priority and effort: ask but by default retain value defined in remote.  It would be best to implement this merge rules in the ait sync itself, so that it will be available everywhere. I am asking myself if implementing this feature is feasible in bash. perhaps it would be better to create an ad-hoc python script (with integrate TUI interface with contextual) that is spawned by ait sync. In this case we need to make sure that the new version of ait sync is properly integrated in ait board. perhaps a full TUI is not needed, especially if the auto-merge rules suffices. perhaps in the python script run first the automerge rules and if cannot resolve then fire up the full TUI. this is a complex task that should be split in child tasks. also there should be proper documentation of all this: the automerge rules, the  tui and son
