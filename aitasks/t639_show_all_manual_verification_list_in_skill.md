---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [manual_verification]
created_at: 2026-04-24 08:01
updated_at: 2026-04-24 08:01
boardidx: 50
---

in aitask-pick skill we have a dedicated flow for handling manual verification tasks, that shows the one by one a list of test and askuserquestion for result. change the flow so each time, before asking a new question, show the full NUMBERED list of manual tests, and add istructions in the skill that if the user enter in other a number plus a test result or directive (the same directives that are asked explicitly one by one for each test item) them the skill should handle those items and update the test status (so basically multiple items will be resolved and updated in a single askuser question). need also to update the skill docs in website and the workflow page associated to the skill in website
