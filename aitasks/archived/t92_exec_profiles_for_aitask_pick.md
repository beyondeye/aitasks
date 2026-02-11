---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [claudeskills, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 12:45
updated_at: 2026-02-11 17:06
completed_at: 2026-02-11 17:06
---

modify aitask_pick skill to ask for an execution profile from available execution profiles in aitasks/metadata. the execution profiles haa anwers to questions in the aitask-pick, to reduce the number of questions asked when the user want to go from starting aitask-pick to implementation phase with the minimum input. need to check all the askuserquestions whose answers can be stored in the execution profile. need to add a way to generate execution profiles. perhaps define a default exection profiles in aitasks metadata that is installed together with scripts. user can modifiy this or copy and create a new one


here is a list of questions whose answers could be stored in the execution profile:

when specific task number selected:
1) Is this the correct task? question: skip or not
2) eamil to track who is working: skip or not (set default value)
3) Claude code local or remote (set default value)
4) Current branch or work tree (set default value)
5) --Question to review plan: bad idea to skip it !!
6)  Post plan write question questions can be added to the execution profile: skip or not
