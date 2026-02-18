---
priority: medium
effort: medium
depends: [163]
issue_type: feature
status: Ready
labels: [claudeskills, aitask_review]
created_at: 2026-02-18 15:39
updated_at: 2026-02-18 15:39
---

in task t163 we have introduce new complementary skills for aitask-review: atiask-review-classify and aitask-review-merge. we want to introduce a new complementary skill to aitask-review: aitask-review-import: the skill given a file or an url to a github source directory or single markdown file, will read the file extract rephrase it in a way that is compatile to instructions for reviewing existing files (it is possible the original file was for defining a workflow, for example, or it contains other content that is not specifically relevant for the review. the new reviewmode file should be written in the reviewmodes (create an appropriate path for it that ignored by the .reviewmodesignore file).important: each file created in this way should have yaml frontmatter metadata with the url of the source file. make sure that the /aitask-review skill IGNORE this url (they should not try to read from this url, this is only for reference). this import skill should also assign appropriate metadata the imported reviewmode file according to conventions as describeed in task t163
