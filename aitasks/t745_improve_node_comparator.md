---
priority: high
effort: high
depends: []
issue_type: enhancement
status: Ready
labels: [ait_brainstorm]
children_to_implement: [t745_5]
created_at: 2026-05-04 18:51
updated_at: 2026-05-05 08:52
boardidx: 10
---

in ait brainstorm in the compare tab we can compare proposals from two nodes. we want to improve how compare work. there are several issues: once a comparison is generated apparently it remains there: if there are shortcut to generate a new one and override current, they are not shown. there is a general issue with shortcuts in ait brainstorm: shortcuts for switching between tab should not be shown in footer: in the footer we should show the currently context-aware shortcuts active. also about the comparison itself: we have the list of dimensions and the corresponding value for the two nodes being compared: we print the full value even if the value matches between the two nodes (see brainstorm-635, for the two currently existing nodes). also when two dimensions are actually different we should show WHAT is actually different using some diff engine (like the existing diff tui). also we currently cannot open actual diff view of the two compared nodes proposal: no diff tui integration yet. this is the time to add the integration. this is a complex task that need to be split in child tasks
