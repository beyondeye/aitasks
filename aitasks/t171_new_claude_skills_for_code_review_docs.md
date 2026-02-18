---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [aitask_review]
created_at: 2026-02-18 22:16
updated_at: 2026-02-18 23:45
---

We have introduced claude code skills for code review and for managing reviewguides files (reviewguides-classify and reviewguides-merge and reviewguides-import) need to document all this new skills and update the workflow section of the documentation on how to use them: the idea is that instead of giving the llm instructions on best practices on how to write code that can poison the llm context, is to have separate review tasks for reviewing the code quality once it is already implemented. this separation of concern (first make something that work, then refactor, fix style issues and so on) is more efficient usage of the llm context, although it require multiple processing steps. at least this is the idea. review skill allow to apply any of the review_modes available that match the specific code that we want to review, and create a well defined aitask to do it. the additional claude code skills: aitask-reviewguide-classify, aitask-reviewguide-merge, and aitask-reviewguide-import are used to optimize reviewguide usage, removing duplicate rules, extending existing reviewguides with additional rules, with all the tedious work made easy by the llm. scan the claude skills and create separate specific doc for each like aother skills but also adding cross-reference for cases where one of those skill is complementary to the other and propose typical workflow to using them and add them the workflow section of the documentation
