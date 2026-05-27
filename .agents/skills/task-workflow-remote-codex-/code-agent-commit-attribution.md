# Code-Agent Commit Attribution Procedure

This procedure is referenced from Step 8 wherever code changes are being committed. It resolves a `Co-Authored-By` trailer for the code agent recorded in `implemented_with`.

**When to execute:** After the Contributor Attribution Procedure (see `contributor-attribution.md`) and before the final `git commit`, so the contributor trailer and code-agent trailer can be composed into one commit message.

**Procedure:**

- Read the task file's frontmatter and check `implemented_with`.

- **If `implemented_with` is empty or missing:** Skip agent commit attribution.

- **If `implemented_with` is present:**
  - Resolve the trailer with:
    ```bash
    ait codeagent coauthor "<implemented_with>"
    ```
  - Parse the machine-readable output:
    - `AGENT_COAUTHOR_NAME:<display_name>`
    - `AGENT_COAUTHOR_EMAIL:<email>`
    - `AGENT_COAUTHOR_TRAILER:<full trailer>`

- **If the resolver succeeds:** Append `AGENT_COAUTHOR_TRAILER` after any contributor trailer block. **IMPORTANT:** The resolver trailer is the sole coauthor attribution for the implementing agent. Do NOT add any additional native or hardcoded coauthor trailers (e.g., Claude Code's default `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`). The resolver output replaces any such defaults.

- **If the resolver fails** (unsupported agent, invalid agent string, missing config, or other command error): skip only the code-agent trailer and continue with the commit flow. Do NOT drop or alter an existing contributor attribution block because agent attribution failed.

**Final commit composition:** Compose the commit message following the format in the **Contributor Attribution Procedure** (see `contributor-attribution.md`) (subject line, optional contributor block, optional secondary contributors line), then append the code-agent `Co-Authored-By` trailer as the last trailer. See the combined example in the Multi-Contributor Attribution section of `contributor-attribution.md`.
