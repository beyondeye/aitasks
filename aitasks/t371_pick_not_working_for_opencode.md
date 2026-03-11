---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board, aitask_pick, codeagent]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-11 15:09
updated_at: 2026-03-11 15:34
---

I have now task pick configured to use open code, but the resolved command to run to start pick is opencode --model opencode/gpt-5.4 365 . this is wrong

when claudecode is selected the resolved command is correct. when codex is selected also the after the recent renaming of task-pick -> pick the ait settings still refer to pick as task-pick, this is wrong. check also if codex and gemini generated commands look correct or also hase problems
