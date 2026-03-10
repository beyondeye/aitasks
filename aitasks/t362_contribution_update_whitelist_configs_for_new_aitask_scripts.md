---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [contribution, whitelists]
issue: https://github.com/beyondeye/aitasks/issues/4
contributor: beyondeye
contributor_email: 5619462+beyondeye@users.noreply.github.com
created_at: 2026-03-10 14:46
updated_at: 2026-03-10 14:46
---

Issue created: 2026-03-09 22:05:20

## [Contribution] Update whitelist configs for new aitask scripts

## Contribution: Update whitelist configs for new aitask scripts

### Scope
bug_fix

### Motivation
Without updated whitelists, new scripts like aitask_contribute.sh, aitask_codemap.sh etc. require manual approval on every invocation, degrading the user experience

### Proposed Merge Approach
Clean merge

### Framework Version
0.9.0

### Changed Files

| File | Status |
|------|--------|
| `.claude/settings.local.json` | Modified |
| `.gemini/policies/aitasks-whitelist.toml` | Modified |
| `seed/claude_settings.local.json` | Modified |
| `seed/geminicli_policies/aitasks-whitelist.toml` | Modified |
| `seed/opencode_config.seed.json` | Modified |

### Code Changes

#### `.claude/settings.local.json`

*Preview — full diff available in raw view of this issue*

```diff
--- c/.claude/settings.local.json
+++ w/.claude/settings.local.json
@@ -28,28 +28,35 @@
       "Bash(./.aitask-scripts/aitask_ls.sh:*)",
       "Bash(./.aitask-scripts/aitask_update.sh:*)",
       "Bash(./.aitask-scripts/aitask_create.sh:*)",
-      "Bash(./.aitask-scripts/aitask_clear_old.sh:*)",
+      "Bash(./.aitask-scripts/aitask_claim_id.sh:*)",
+      "Bash(./.aitask-scripts/aitask_codeagent.sh:*)",
+      "Bash(./.aitask-scripts/aitask_codemap.sh:*)",
+      "Bash(./.aitask-scripts/aitask_contribute.sh:*)",
       "Bash(./.aitask-scripts/aitask_stats.sh:*)",
       "Bash(./.aitask-scripts/aitask_issue_update.sh:*)",
       "Bash(./.aitask-scripts/aitask_changelog.sh:*)",
       "Bash(shellcheck:*)",
       "Bash(./.aitask-scripts/aitask_lock.sh:*)",
       "Bash(/home/ddt/Work/aitasks/.aitask-scripts/aitask_lock.sh:*)",
+      "Bash(./.aitask-scripts/aitask_lock_diag.sh:*)",
       "Bash(./.aitask-scripts/aitask_review_commits.sh:*)",
       "Bash(./.aitask-scripts/aitask_review_detect_env.sh:*)",
       "Bash(wc:*)",
       "Bash(./.aitask-scripts/aitask_archive.sh:*)",
+      "Bash(./.aitask-scripts/aitask_opencode_models.sh:*)",
       "Bash(./.aitask-scripts/aitask_pick_own.sh:*)",
       "WebFetch(domain:docs.gitlab.com)",
       "Bash(glab issue list:*)",
       "Bash(glab issue view:*)",
       "Bash(./.aitask-scripts/aitask_issue_import.sh:*)",
       "Bash(/home/ddt/Work/aitasks/.aitask-scripts/aitask_issue_import.sh:*)",
+      "Bash(./.aitask-scripts/aitask_pr_close.sh:*)",
+      "Bash(./.aitask-scripts/aitask_pr_import.sh:*)",
+      "Bash(./.aitask-scripts/aitask_sync.sh:*)",
       "Bash(./.aitask-scripts/aitask_zip_old.sh:*)",
       "Bash(bkt issue list:*)",
       "Bash(bkt context:*)",
       "Bash(bkt issue create:*)",
-      "Bash(./.aitask-scripts/aitask_reviewmode_scan.sh:*)",
       "WebFetch(domain:www.docsy.dev)",
       "WebSearch",
       "Bash(printf:*)",
@@ -81,7 +88,17 @@
       "WebFetch(domain:platform.claude.com)",
       "WebFetch(domain:ai.google.dev)",
       "WebFetch(domain:platform.openai.com)",
-      "WebFetch(domain:opencode.ai)"
+      "WebFetch(domain:opencode.ai)",
+      "Bash(./aiscripts/aitask_ls.sh:*)",
+      "Bash(./aiscripts/aitask_update.sh:*)",
+      "Bash(./aiscripts/aitask_create.sh:*)",
+      "Bash(./aiscripts/aitask_zip_old.sh:*)",
```

<!-- full-diff:.claude/settings.local.json
```diff
--- c/.claude/settings.local.json
+++ w/.claude/settings.local.json
@@ -28,28 +28,35 @@
       "Bash(./.aitask-scripts/aitask_ls.sh:*)",
       "Bash(./.aitask-scripts/aitask_update.sh:*)",
       "Bash(./.aitask-scripts/aitask_create.sh:*)",
-      "Bash(./.aitask-scripts/aitask_clear_old.sh:*)",
+      "Bash(./.aitask-scripts/aitask_claim_id.sh:*)",
+      "Bash(./.aitask-scripts/aitask_codeagent.sh:*)",
+      "Bash(./.aitask-scripts/aitask_codemap.sh:*)",
+      "Bash(./.aitask-scripts/aitask_contribute.sh:*)",
       "Bash(./.aitask-scripts/aitask_stats.sh:*)",
       "Bash(./.aitask-scripts/aitask_issue_update.sh:*)",
       "Bash(./.aitask-scripts/aitask_changelog.sh:*)",
       "Bash(shellcheck:*)",
       "Bash(./.aitask-scripts/aitask_lock.sh:*)",
       "Bash(/home/ddt/Work/aitasks/.aitask-scripts/aitask_lock.sh:*)",
+      "Bash(./.aitask-scripts/aitask_lock_diag.sh:*)",
       "Bash(./.aitask-scripts/aitask_review_commits.sh:*)",
       "Bash(./.aitask-scripts/aitask_review_detect_env.sh:*)",
       "Bash(wc:*)",
       "Bash(./.aitask-scripts/aitask_archive.sh:*)",
+      "Bash(./.aitask-scripts/aitask_opencode_models.sh:*)",
       "Bash(./.aitask-scripts/aitask_pick_own.sh:*)",
       "WebFetch(domain:docs.gitlab.com)",
       "Bash(glab issue list:*)",
       "Bash(glab issue view:*)",
       "Bash(./.aitask-scripts/aitask_issue_import.sh:*)",
       "Bash(/home/ddt/Work/aitasks/.aitask-scripts/aitask_issue_import.sh:*)",
+      "Bash(./.aitask-scripts/aitask_pr_close.sh:*)",
+      "Bash(./.aitask-scripts/aitask_pr_import.sh:*)",
+      "Bash(./.aitask-scripts/aitask_sync.sh:*)",
       "Bash(./.aitask-scripts/aitask_zip_old.sh:*)",
       "Bash(bkt issue list:*)",
       "Bash(bkt context:*)",
       "Bash(bkt issue create:*)",
-      "Bash(./.aitask-scripts/aitask_reviewmode_scan.sh:*)",
       "WebFetch(domain:www.docsy.dev)",
       "WebSearch",
       "Bash(printf:*)",
@@ -81,7 +88,17 @@
       "WebFetch(domain:platform.claude.com)",
       "WebFetch(domain:ai.google.dev)",
       "WebFetch(domain:platform.openai.com)",
-      "WebFetch(domain:opencode.ai)"
+      "WebFetch(domain:opencode.ai)",
+      "Bash(./aiscripts/aitask_ls.sh:*)",
+      "Bash(./aiscripts/aitask_update.sh:*)",
+      "Bash(./aiscripts/aitask_create.sh:*)",
+      "Bash(./aiscripts/aitask_zip_old.sh:*)",
+      "Bash(./aiscripts/aitask_stats.sh:*)",
+      "Bash(./aiscripts/aitask_issue_update.sh:*)",
+      "Bash(./aiscripts/aitask_lock.sh:*)",
+      "Bash(./aiscripts/aitask_review_commits.sh:*)",
+      "Bash(./aiscripts/aitask_review_detect_env.sh:*)",
+      "Bash(./aiscripts/aitask_archive.sh:*)"
     ]
   }
 }
```
-->

#### `.gemini/policies/aitasks-whitelist.toml`

*Preview — full diff available in raw view of this issue*

```diff
--- c/.gemini/policies/aitasks-whitelist.toml
+++ w/.gemini/policies/aitasks-whitelist.toml
@@ -162,7 +162,25 @@ priority = 100
 
 [[rule]]
 toolName = "run_shell_command"
-commandPrefix = "./.aitask-scripts/aitask_clear_old.sh"
+commandPrefix = "./.aitask-scripts/aitask_claim_id.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_codeagent.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_codemap.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_contribute.sh"
 decision = "allow"
 priority = 100
 
@@ -202,6 +220,18 @@ commandRegex = ".*/.aitask-scripts/aitask_lock\\.sh.*"
 decision = "allow"
 priority = 100
 
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_lock_diag.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_opencode_models.sh"
+decision = "allow"
+priority = 100
+
 [[rule]]
 toolName = "run_shell_command"
 commandPrefix = "./.aitask-scripts/aitask_review_commits.sh"
@@ -256,6 +286,24 @@ commandRegex = ".*/.aitask-scripts/aitask_issue_import\\.sh.*"
 decision = "allow"
```

<!-- full-diff:.gemini/policies/aitasks-whitelist.toml
```diff
--- c/.gemini/policies/aitasks-whitelist.toml
+++ w/.gemini/policies/aitasks-whitelist.toml
@@ -162,7 +162,25 @@ priority = 100
 
 [[rule]]
 toolName = "run_shell_command"
-commandPrefix = "./.aitask-scripts/aitask_clear_old.sh"
+commandPrefix = "./.aitask-scripts/aitask_claim_id.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_codeagent.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_codemap.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_contribute.sh"
 decision = "allow"
 priority = 100
 
@@ -202,6 +220,18 @@ commandRegex = ".*/.aitask-scripts/aitask_lock\\.sh.*"
 decision = "allow"
 priority = 100
 
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_lock_diag.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_opencode_models.sh"
+decision = "allow"
+priority = 100
+
 [[rule]]
 toolName = "run_shell_command"
 commandPrefix = "./.aitask-scripts/aitask_review_commits.sh"
@@ -256,6 +286,24 @@ commandRegex = ".*/.aitask-scripts/aitask_issue_import\\.sh.*"
 decision = "allow"
 priority = 100
 
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_pr_close.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_pr_import.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_sync.sh"
+decision = "allow"
+priority = 100
+
 [[rule]]
 toolName = "run_shell_command"
 commandPrefix = "./.aitask-scripts/aitask_zip_old.sh"
@@ -280,12 +328,6 @@ commandPrefix = "bkt issue create"
 decision = "allow"
 priority = 100
 
-[[rule]]
-toolName = "run_shell_command"
-commandPrefix = "./.aitask-scripts/aitask_reviewmode_scan.sh"
-decision = "allow"
-priority = 100
-
 [[rule]]
 toolName = "run_shell_command"
 commandPrefix = "printf"
```
-->

#### `seed/claude_settings.local.json`

```diff
--- c/seed/claude_settings.local.json
+++ w/seed/claude_settings.local.json
@@ -28,6 +28,9 @@
       "Bash(./.aitask-scripts/aitask_archive.sh:*)",
       "Bash(./.aitask-scripts/aitask_changelog.sh:*)",
       "Bash(./.aitask-scripts/aitask_claim_id.sh:*)",
+      "Bash(./.aitask-scripts/aitask_codeagent.sh:*)",
+      "Bash(./.aitask-scripts/aitask_codemap.sh:*)",
+      "Bash(./.aitask-scripts/aitask_contribute.sh:*)",
       "Bash(./.aitask-scripts/aitask_create.sh:*)",
       "Bash(./.aitask-scripts/aitask_explain_extract_raw_data.sh:*)",
       "Bash(./.aitask-scripts/aitask_explain_runs.sh:*)",
@@ -39,6 +42,7 @@
       "Bash(./.aitask-scripts/aitask_lock.sh:*)",
       "Bash(./.aitask-scripts/aitask_lock_diag.sh:*)",
       "Bash(./.aitask-scripts/aitask_ls.sh:*)",
+      "Bash(./.aitask-scripts/aitask_opencode_models.sh:*)",
       "Bash(./.aitask-scripts/aitask_pick_own.sh:*)",
       "Bash(./.aitask-scripts/aitask_pr_close.sh:*)",
       "Bash(./.aitask-scripts/aitask_pr_import.sh:*)",
```

#### `seed/geminicli_policies/aitasks-whitelist.toml`

*Preview — full diff available in raw view of this issue*

```diff
--- c/seed/geminicli_policies/aitasks-whitelist.toml
+++ w/seed/geminicli_policies/aitasks-whitelist.toml
@@ -162,7 +162,25 @@ priority = 100
 
 [[rule]]
 toolName = "run_shell_command"
-commandPrefix = "./.aitask-scripts/aitask_clear_old.sh"
+commandPrefix = "./.aitask-scripts/aitask_claim_id.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_codeagent.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_codemap.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_contribute.sh"
 decision = "allow"
 priority = 100
 
@@ -202,6 +220,18 @@ commandRegex = ".*/.aitask-scripts/aitask_lock\\.sh.*"
 decision = "allow"
 priority = 100
 
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_lock_diag.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_opencode_models.sh"
+decision = "allow"
+priority = 100
+
 [[rule]]
 toolName = "run_shell_command"
 commandPrefix = "./.aitask-scripts/aitask_review_commits.sh"
@@ -256,6 +286,24 @@ commandRegex = ".*/.aitask-scripts/aitask_issue_import\\.sh.*"
 decision = "allow"
```

<!-- full-diff:seed/geminicli_policies/aitasks-whitelist.toml
```diff
--- c/seed/geminicli_policies/aitasks-whitelist.toml
+++ w/seed/geminicli_policies/aitasks-whitelist.toml
@@ -162,7 +162,25 @@ priority = 100
 
 [[rule]]
 toolName = "run_shell_command"
-commandPrefix = "./.aitask-scripts/aitask_clear_old.sh"
+commandPrefix = "./.aitask-scripts/aitask_claim_id.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_codeagent.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_codemap.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_contribute.sh"
 decision = "allow"
 priority = 100
 
@@ -202,6 +220,18 @@ commandRegex = ".*/.aitask-scripts/aitask_lock\\.sh.*"
 decision = "allow"
 priority = 100
 
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_lock_diag.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_opencode_models.sh"
+decision = "allow"
+priority = 100
+
 [[rule]]
 toolName = "run_shell_command"
 commandPrefix = "./.aitask-scripts/aitask_review_commits.sh"
@@ -256,6 +286,24 @@ commandRegex = ".*/.aitask-scripts/aitask_issue_import\\.sh.*"
 decision = "allow"
 priority = 100
 
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_pr_close.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_pr_import.sh"
+decision = "allow"
+priority = 100
+
+[[rule]]
+toolName = "run_shell_command"
+commandPrefix = "./.aitask-scripts/aitask_sync.sh"
+decision = "allow"
+priority = 100
+
 [[rule]]
 toolName = "run_shell_command"
 commandPrefix = "./.aitask-scripts/aitask_zip_old.sh"
@@ -280,12 +328,6 @@ commandPrefix = "bkt issue create"
 decision = "allow"
 priority = 100
 
-[[rule]]
-toolName = "run_shell_command"
-commandPrefix = "./.aitask-scripts/aitask_reviewmode_scan.sh"
-decision = "allow"
-priority = 100
-
 [[rule]]
 toolName = "run_shell_command"
 commandPrefix = "printf"
```
-->

#### `seed/opencode_config.seed.json`

```diff
--- c/seed/opencode_config.seed.json
+++ w/seed/opencode_config.seed.json
@@ -17,6 +17,9 @@
       "./.aitask-scripts/aitask_archive.sh *": "allow",
       "./.aitask-scripts/aitask_changelog.sh *": "allow",
       "./.aitask-scripts/aitask_claim_id.sh *": "allow",
+      "./.aitask-scripts/aitask_codeagent.sh *": "allow",
+      "./.aitask-scripts/aitask_codemap.sh *": "allow",
+      "./.aitask-scripts/aitask_contribute.sh *": "allow",
       "./.aitask-scripts/aitask_create.sh *": "allow",
       "./.aitask-scripts/aitask_explain_extract_raw_data.sh *": "allow",
       "./.aitask-scripts/aitask_explain_runs.sh *": "allow",
@@ -28,6 +31,7 @@
       "./.aitask-scripts/aitask_lock.sh *": "allow",
       "./.aitask-scripts/aitask_lock_diag.sh *": "allow",
       "./.aitask-scripts/aitask_ls.sh *": "allow",
+      "./.aitask-scripts/aitask_opencode_models.sh *": "allow",
       "./.aitask-scripts/aitask_pick_own.sh *": "allow",
       "./.aitask-scripts/aitask_pr_close.sh *": "allow",
       "./.aitask-scripts/aitask_pr_import.sh *": "allow",
```


<!-- aitask-contribute-metadata
contributor: beyondeye
contributor_email: 5619462+beyondeye@users.noreply.github.com
based_on_version: 0.9.0
-->
