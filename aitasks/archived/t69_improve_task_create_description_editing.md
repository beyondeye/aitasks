---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [scripting, bash, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-09 10:30
updated_at: 2026-02-09 16:14
completed_at: 2026-02-09 16:14
---

Currently editing task description when we run the aitask_create.sh bash script in interactive mode have a few problems 1) it is not possible to navigate the text with left and right arrow: when pressing the left arrow it insert the charaters [D  and when pressing the right arrow it insert the characters [C , also when the cursor go beyond the end of line in the terminal window it is not possible in any way to go back to the previous descirption line, even by deleting all text of the current line. in brief it is not a great editing experience even for the standards of text editing in the terminal. need to improve this. I am not sure if there are standard linux packages that can be integrated in a bash script to do this (without opening an exernal text editor) I would like to keep the editing very bare anyway. the idea is that the task description is like flow of consciousness. not allowing to much editing force the user to just "spit out" everything without trying to organize. but at least being able to use left/right arrows and going back to previous line seems to me needed.
