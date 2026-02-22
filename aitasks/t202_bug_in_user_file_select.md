---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-22 13:39
updated_at: 2026-02-22 14:40
---

in the user file select skill, we search for files or keywords and the present to the user a list and suggest a range of specific list of indexes between the find results to select as return result of the skill. the problem is that when using claude AskUserInput tool with multiple answers, by pressing a number that is also one of the numbered list of options, it automatically select that option, even if currently we selected the option "enter something" that would allow us to enter the range or lists of specific indexes in find results. need to tell the user in the label of that option to enter the list of find results inside parenthesis like (1,2) or (1-2,3). this is only to avoid the issue with the AskUserInput tool. verify that this change of format in the answer does not affect the proper return results for the skill
