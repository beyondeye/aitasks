---
priority: high
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [bash_scripts, git-integration]
children_to_implement: [t260_1, t260_2, t260_3, t260_4]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-26 15:04
updated_at: 2026-03-01 15:31
boardcol: now
boardidx: 20
---

we currently support workflow where we import an issue from github/gitlab to a local aitask. I want to introduce a new workflow where we create an aitask from a pull request. Motivation: if a pull request was created by an external contribution, we need additional checks, in many case we cannot merge the code directly. the idea is to extract from the code changes in the pull request an an aitask/aiplans definition with a new claudecode skill that will help identify the "purpose" behind the the pull request, the "idea" behind the proposed solution, the files that are involved in the solution, and extract implementation details and idea from the pull request but only as kind of a "proposal" that need to be verified and validated. basically there should a bash script that inteeract with gitlab github to extract all the relevant data (description and comments in the pull requests, file affected, actual code changes) and write them in a structured way in some intermediate file, and then the skill to process this intermediate data (interactively with questions to the user if needed, with a plan/review loop similar to current task-pick, to generate the final task and plan (by default do not continue to implementaiton) probably the flow for the new skill will be most similar to current explore skill) we should add metadata to the aitask created with the link to the pull request so that once the aitask created from the pull request is completed and archived we also close/delete the pull request in some way (I don't the exact mechanics of pull reqeuest) there should be a way to still records contributors to the project even if their original pull request was not merged, for example setting the author of the commits of the implementation of the aitask extracted from the pull request with the github/gitlab handle username or email of the contributor, and perhaps a link to the pull request in the commit message. so basically we need two new metadata fild for tasks: the link of the pull request from where the aitask was generated and the github/gitlab username or email or whatever of the contributor (probabily stick to gitlab/github username or similar). must also make sure that all scripts like aitaitask_update or ait board python script don't break down because of this new metadata. this is very complex task and must be broke down in multiple child tasks
