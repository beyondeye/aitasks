---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [git-integration, contribution]
implemented_with: claudecode/opus5_5
created_at: 2026-11-08 21:44
updated_at: 2026-11-08 21:44
completed_at: 2026-11-08 21:44
---

`_gitlab_verify_contribution_label` (`.aitask-scripts/aitask_contribute.sh`) only recognised `https://…/-/issues/<iid>` links in `glab issue create` output. GitLab now links new issues as `/-/work_items/<iid>`: glab 1.126 prints it, and the REST `web_url` uses it on gitlab.com too. Self-managed instances may also serve plain `http`. The read-back therefore never found the issue, the "label was silently dropped" warning added by t2241 never fired, and contributors always got "Could not verify".

The defect was found by the t2248 Part B live run against GitLab CE 19.4.5 (defect D1). The fix accepts `http`/`https` and both the `issues` and `work_items` link forms. It replaces the unit-test fixture with the real captured glab output, and adds a test covering every link form plus a merge-request link, which must still be reported as unverifiable.
