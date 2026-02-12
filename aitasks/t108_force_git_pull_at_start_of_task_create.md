---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitasks, bash]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-13 01:09
updated_at: 2026-02-13 01:13
---

when creating tasks from multiple PCs that connect to the same project repo, there will issue of the same task number used for different task added with aitask_create from different pc. This will create all sorts of problems. this issue has no simple solution. beads for this reason do not use consecutive task numbers. a possiblity to partially solve the issue is force git pull BEFORE creating an issue and force git push after creating a new issue. but even this (not at all desirable solution since it forces running potentially problematic git pull git push) can still fails of the desync happen in-between when two user in parellel are editing a new task. probably a better solution is create a separate script ait sanitizeids that will 1) run git pull 2) check for duplicate taskids 3) rename confliclting tasks) 4) push updated tasks with new numbers. and force to run git sanitize taskids at beginning of task pick, and add check in all scripts that rely on a single unique file with a specific task ids to use a helper function that identifiy conflict and run sanitize taskids. in any case, since sanitize taskid also require calling git pull and git push ther should be a safeguard in case there are merge conflick when running git pull or git push. in brief this require careful design  on integration with existing scripts and workflow. but it is probably the best solution, to have specialized aitask_sanitizeid and design its integration in existing aitask scripts and skills. ask me questions if you need clarificaitons. Suggest alternative solutions if possible, and compare pros and cons with the proposed solution
