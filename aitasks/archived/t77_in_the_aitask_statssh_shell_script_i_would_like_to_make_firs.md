---
priority: medium
effort: low
depends: []
issue_type: feature
status: Done
labels: [aitasks, statistics, bash]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-10 10:37
updated_at: 2026-02-10 11:35
completed_at: 2026-02-10 11:35
---

in the aitask_stats.sh shell script, i would like to make first day of week configurable: add an option that takes a string param that is matched with days of week, for example aitask_stats -w sun will match the passed string with Sunday and will know that requested first day of the week is sunday. if now match is found or ambigous then revert to default Monday (but show a warning message to user, before proceed with statistics. just a warning, proceed in any case
