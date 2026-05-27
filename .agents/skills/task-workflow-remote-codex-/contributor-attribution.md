# Contributor Attribution Procedure

This procedure is referenced from Step 8 wherever code changes are being committed. It checks whether the task carries imported contributor metadata and, if so, formats the commit message to credit the original contributor.

**When to execute:** Before the code commit in Step 8 ("If Commit changes"), to determine whether the final commit message needs a contributor trailer block.

**Procedure:**

- Read the task file's frontmatter and check for `contributor`, `contributor_email`, `pull_request`, and `issue` fields.

- **If both `contributor` and `contributor_email` are present**, the final code commit message MUST include a contributor attribution block.
  - **If `pull_request` is present**, use:
    ```text
    Based on PR: <pull_request_url>

    Co-Authored-By: <contributor> <<contributor_email>>
    ```
  - **Otherwise** (for example, contributor metadata imported from an issue), use:
    ```text
    Co-Authored-By: <contributor> <<contributor_email>>
    ```
  Example for PR-imported work:
  ```text
  Based on PR: https://github.com/owner/repo/pull/15

  Co-Authored-By: octocat <12345+octocat@users.noreply.github.com>
  ```
  Example for issue-imported work:
  ```text
  Co-Authored-By: contributor-name <contributor@example.com>
  ```
  This block is composed into the final commit message together with any code-agent trailer from the **Code-Agent Commit Attribution Procedure** (see `code-agent-commit-attribution.md`).

- **If only `contributor` is present without `contributor_email`:** Skip the `Co-Authored-By` trailer (platforms require a valid email for attribution linking). Use the normal subject line, plus the code-agent trailer if available.

- **If neither field is present:** No contributor attribution block is needed. Use the normal subject line, plus the code-agent trailer if available.

## Multi-Contributor Attribution (Merged Issues)

When a task has both `contributor`/`contributor_email` (primary) and a `contributors:` list (secondary contributors from merged issues), the commit message includes:

- **Primary contributor:** `Co-Authored-By` trailer (as above, unchanged)
- **Secondary contributors:** Listed in the commit body text, between the subject line and the `Co-Authored-By` trailers:
  ```text
  Also based on contributions from: bob (#38), charlie (#15)
  ```

**Procedure for reading `contributors:`:**

- Read the task file's frontmatter. If `contributors:` is present, it is a YAML list of objects:
  ```yaml
  contributors:
    - name: bob
      email: bob@example.com
      issue: https://github.com/owner/repo/issues/38
  ```
- Extract each contributor's name and issue number (from the URL).
- Format as: `Also based on contributions from: <name1> (#<issue_num1>), <name2> (#<issue_num2>)`
- Place this line after the subject, before the `Co-Authored-By` trailer.

**Example with primary + secondary contributors and code-agent:**

```bash
git commit -m "$(cat <<'EOF'
feature: Add dark mode and theme support (t42)

Also based on contributions from: bob (#38), charlie (#15)

Co-Authored-By: primary-author <primary@example.com>
Co-Authored-By: Codex/GPT5.4 <codex@aitasks.io>
EOF
)"
```

- The `related_issues:` frontmatter field is informational only (no commit message impact). It records all source issue URLs for traceability.

**Notes:**
- `Co-Authored-By` is preferred over `--author` — the contributor inspired the work but the current implementer wrote this specific code
- The `contributor_email` can be pre-computed during PR import or extracted by `ait issue-import` from `aitask-contribute` metadata — no API call is needed at commit time
- Both GitHub and GitLab display `Co-Authored-By` contributors in the commit UI and count them as contributions
