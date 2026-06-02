# Gemini CLI (`geminicli`) to Antigravity CLI (`agy`) Migration Guide

This guide details findings from the existing Gemini CLI configuration inside the `aitasks` project and provides step-by-step instructions for migrating this configuration (both whitelist policies and custom slash commands) to the Antigravity CLI platform.

---

## 1. Findings: Existing Gemini CLI Configuration

The `aitasks` project contains a legacy `.gemini/` configuration directory with the following structure:
* **Settings ([.gemini/settings.json](file:///home/ddt/Work/aitasks/.gemini/settings.json))**: Configures the default approval mode and directs Gemini CLI to load rules from local project paths:
  ```json
  {
    "general": { "defaultApprovalMode": "default" },
    "policyPaths": [ ".gemini/policies/" ]
  }
  ```
* **Policies ([.gemini/policies/aitasks-whitelist.toml](file:///home/ddt/Work/aitasks/.gemini/policies/aitasks-whitelist.toml))**: A comprehensive list containing over 780 lines of rules. These rules whitelist:
  * Standard system commands (`ls`, `cat`, `echo`, `grep`, `sed`, etc.).
  * Git operations (`git add`, `git commit`, `git push`, etc.).
  * Custom task scripts inside `./.aitask-scripts/` (e.g., `aitask_stats.sh`, `aitask_update.sh`, `aitask_lock.sh`).
  * Explicit permissions for the `activate_skill` tool for various procedural skills (e.g., `aitask-changelog`, `aitask-review`, `aitask-wrap`).
* **Commands (`.gemini/commands/`)**: Contains 23 TOML files representing custom slash commands (e.g., `/aitask-explore`, `/aitask-qa`). Each file maps a command description and a template prompt.
* **Skills (`.gemini/skills/`)**: Contains profile-specific procedural stubs and adaptation documents such as:
  * [geminicli_planmode_prereqs.md](file:///home/ddt/Work/aitasks/.gemini/skills/geminicli_planmode_prereqs.md)
  * [geminicli_tool_mapping.md](file:///home/ddt/Work/aitasks/.gemini/skills/geminicli_tool_mapping.md)

---

## 2. Key Security & Architectural Differences

Before migrating, it is essential to understand how the two CLI tools handle security and customization differently:

1. **Policy Loading (Local vs. Global)**:
   * **Gemini CLI**: Allowed repository-local `.gemini/settings.json` to define `policyPaths` and self-load rules. This posed a security risk, as a cloned malicious repository could whitelist dangerous shell commands without the user knowing.
   * **Antigravity CLI**: Disables automatic local policy overrides. All active whitelist configurations are read from the global policies directory (e.g., `~/.gemini/policies/`) to keep control strictly in the user's hands.
2. **Execution Context (Host vs. Sandbox)**:
   * **Gemini CLI**: Relied on static TOML rules to approve/block shell execution on the host machine.
   * **Antigravity CLI**: Employs a **native Terminal Sandbox** container (using tools like `nsjail` on Linux). Commands run in isolation, preventing the agent from modifying files outside of trusted paths or accessing unauthorized network segments.
3. **Custom Slash Commands (TOML vs. Markdown)**:
   * **Gemini CLI**: Defined slash commands using TOML files inside `.gemini/commands/`.
   * **Antigravity CLI**: Replaces command TOML files with **Agent Skills** written in Markdown (containing YAML frontmatter for metadata) inside `.agents/skills/<name>/SKILL.md`.

---

## 3. Migration Plan

### Step 1: Migrate Whitelists to the Global Directory
Because Antigravity CLI does not auto-load workspace-level `policyPaths`, you must copy the local rules into the global policy store.

1. Map the project path in your global settings:
   * **File**: `~/.gemini/projects.json`
   * **Content**:
     ```json
     {
       "projects": {
         "/home/ddt/Work/aitasks": "aitasks"
       }
     }
     ```
2. Copy the whitelist file into the global policy directory, renaming it to match the project key:
   ```bash
   cp .gemini/policies/aitasks-whitelist.toml ~/.gemini/policies/aitasks-whitelist.toml
   ```
3. Mark the project folder as trusted to allow basic file modifications:
   * **File**: `~/.gemini/trustedFolders.json`
   * **Content**:
     ```json
     {
       "/home/ddt/Work/aitasks": "TRUST_FOLDER"
     }
     ```

### Step 2: Convert Custom Slash Commands to Agent Skills
Convert the command definitions from `.gemini/commands/*.toml` into Markdown Agent Skills.

#### Legacy TOML Command (`.gemini/commands/aitask-add-model.toml`)
```toml
description = "Register a known code-agent model..."
prompt = """
Execute the following Claude Code skill...
Arguments: {{args}}
@.claude/skills/aitask-add-model/SKILL.md
"""
```

#### Migrated Markdown Skill (`.agents/skills/aitask-add-model/SKILL.md`)
Create a folder under `.agents/skills/` and put the metadata in YAML frontmatter and the prompt template in the body:
```markdown
---
id: aitask-add-model
name: Register Model
description: Register a known code-agent model...
---

Execute the following Claude Code skill. Follow each step precisely, translating tool references per the mapping.

Arguments: {{args}}

@.agents/skills/aitask-add-model/SKILL.md
```

### Step 3: Align Tool References inside Custom Skills
Verify and update tool name references inside custom skill prompts to match the Antigravity system API:
* Change `run_shell_command(...)` references to `run_command(...)`.
* Change `web_fetch(...)` to `read_url_content(...)`.
* Ensure that paths pointing to legacy directories (e.g. `@.gemini/skills/`) are updated to point to the new location (e.g. `@.agents/skills/`).
