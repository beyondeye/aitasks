---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [geminicli]
created_at: 2026-03-09 13:27
updated_at: 2026-03-09 13:27
boardidx: 70
boardcol: next
---

currently when running aitask-pick with geminicli, the plaanning step of aitask-pick is skipped. need to find a way to force the model the generate a plan first and ask for confirmation

when I asked gemini why he skipped the planning this was its answer: │   Review → Why you skipped the         │

so again there is an issue with contradicting instructions for a normal task and a child task,

what is interesting is the cause why the model said it used seed/profiles: I used the version in the seed/profiles directory because my

actually this is correct: .aitask-data and aitask and aiplans directory ARE gitignored.

and the following answer of the model is even more interesting: │ User answered:                                                                                                                    │

SO THE CORE ISSUE IS the read_file tool in gemini that fails on git-ignored path
