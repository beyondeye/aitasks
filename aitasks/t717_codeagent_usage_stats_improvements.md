---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [verifiedstats, statistics]
children_to_implement: [t717_3, t717_4, t717_5, t717_6]
created_at: 2026-04-29 22:40
updated_at: 2026-04-30 12:04
---

currently in many skills we have the verified stats  accumulation, to help surface models with best perfomance. we want to improve how we accumulate stats because of several exsisting issues. 1) new models vs old models": it is not useful to keep proposing to the user old models with high scores when new model came out, so the should have separate stats for current+last calendar month and all time. 2) we should have a separate stats count for only usage counts, without the user given 1-5 score: we have codeagents like codex that will skill all askuserquestions after we exti plan mode, so also the verifieduser question, but we can still register simple usage count for each model (same two bins: current+last calendar mont, and all time). we can already gather this kind of statistics using the ait stats batch script that scan aitasks and commits, but it would be useful to have the count precalculated and stored. once we have this stat we can use it for example in the agentcommanddialog that we use in tuis when we want to select a codeagent for running an action, currently one of the list we show are the list of codeagents with top scores: we can extend that dialog and add more lists (that we select with left/right arrow) to choose from: that is agents with most usage count, by the way, the stats we should use there in the agencommand dialog where we choose the codeagent should be the current+lastcalendar month.  we should also update the ait stats bash script and the ait stats tui to support the new modified way to accumulate model stats. ask me questions if you need clarifications. this is a complex task. that should be split in child tasks
