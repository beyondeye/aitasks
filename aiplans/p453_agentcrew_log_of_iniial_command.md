---
Task: t453_agentcrew_log_of_iniial_command.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Fix agentcrew prompt passing and file references

## Context

When the agentcrew runner launches a code agent, it reads the work2do file content and passes the entire text inline via `-p` to `ait codeagent invoke raw`. This causes two problems:
1. The full prompt (100+ lines) is logged to `_log.txt` as part of the command line, bloating logs
2. The work2do templates say "Read your `_input.md` file (see your `_instructions.md` for the path)" but `_instructions.md` never lists the path to `_input.md` or other associated files, leaving the agent unable to find its own files

## Implementation

### Step 1: Update `_instructions.md` template in `aitask_crew_addwork.sh`

**File:** `.aitask-scripts/aitask_crew_addwork.sh` (lines 184-220)

Add a `## Your Files` section to the instructions template after the existing "## Writing Output" section. Use shorthand-to-path mappings so that work2do templates can keep referencing `_input.md`, `_output.md` etc. without change:

```
## Your Files
All your files are in: ${WT_PATH}

- \`_work2do.md\` → ${WT_PATH}/${AGENT_NAME}_work2do.md
- \`_input.md\` → ${WT_PATH}/${AGENT_NAME}_input.md
- \`_output.md\` → ${WT_PATH}/${AGENT_NAME}_output.md
- \`_instructions.md\` → ${WT_PATH}/${AGENT_NAME}_instructions.md
- \`_status.yaml\` → ${WT_PATH}/${AGENT_NAME}_status.yaml
- \`_commands.yaml\` → ${WT_PATH}/${AGENT_NAME}_commands.yaml
- \`_alive.yaml\` → ${WT_PATH}/${AGENT_NAME}_alive.yaml
```

This way work2do templates keep using shorthand names like "Read your `_input.md`" and the agent resolves them via this mapping.

### Step 2: Runner assembles prompt with file references and writes to file

**File:** `.aitask-scripts/agentcrew/agentcrew_runner.py` — `launch_agent()` function (lines 395-458)

**2a.** After reading `work2do_content` (line 407), compose a full prompt:
- Compute `worktree_rel = os.path.relpath(worktree, _repo_root)`
- Build a file-path preamble using shorthand→path mappings (same style as instructions):
  ```
  ## Your Agent Files
  All your files are in: <worktree_rel>
  - `_work2do.md` → <worktree_rel>/<name>_work2do.md
  - `_input.md` → <worktree_rel>/<name>_input.md
  - `_output.md` → <worktree_rel>/<name>_output.md
  - `_instructions.md` → <worktree_rel>/<name>_instructions.md
  ...
  ```
- Concatenate: preamble + separator + work2do_content

**2b.** Write assembled prompt to `<agent>_prompt.md` in the worktree:
```python
prompt_file = os.path.join(worktree, f"{name}_prompt.md")
with open(prompt_file, "w") as pf:
    pf.write(full_prompt)
```

**2c.** Change the command from inline content to a short "read this file" prompt:
```python
# Before:
cmd = [ait_cmd, "codeagent", "--agent-string", agent_string,
       "invoke", "raw", "-p", work2do_content]

# After:
prompt_rel = os.path.relpath(prompt_file, _repo_root) if _repo_root else prompt_file
short_prompt = f"Read and follow all instructions in the file: {prompt_rel}"
cmd = [ait_cmd, "codeagent", "--agent-string", agent_string,
       "invoke", "raw", "-p", short_prompt]
```

**2d.** Add prompt file path to log header:
```python
log_fh.write(f"=== Prompt file: {prompt_rel} ===\n")
```

### Step 3: No changes to brainstorm templates

The 5 brainstorm templates (`.aitask-scripts/brainstorm/templates/{explorer,comparator,synthesizer,detailer,patcher}.md`) keep their existing `_input.md` / `_instructions.md` shorthand references unchanged. The agent resolves these via the shorthand→path mapping in the "Your Files" section (from Step 1 in `_instructions.md` and from the prompt preamble in Step 2).

## Files modified

| File | Change |
|------|--------|
| `.aitask-scripts/aitask_crew_addwork.sh` | Add "Your Files" section with shorthand→path mappings to instructions template |
| `.aitask-scripts/agentcrew/agentcrew_runner.py` | Assemble prompt file with file reference preamble, pass short reference instead of inline |

## What does NOT change

- `aitask_codeagent.sh` — No changes needed. The `raw` operation passes args through; the `-p` flag still works, just with shorter content now.

## Verification

1. Run `ait crew addwork` for a test crew and verify `_instructions.md` includes the "Your Files" section with correct paths
2. Launch a crew agent and verify:
   - `_prompt.md` file is created with file reference table + work2do content
   - `_log.txt` shows short command (file path reference) instead of full prompt
   - The agent can actually find and read its `_input.md` and `_instructions.md` files

## Final Implementation Notes
- **Actual work done:** Implemented both changes as planned — prompt file assembly in runner + "Your Files" section in addwork instructions template
- **Deviations from plan:** None. Originally considered updating brainstorm templates but user suggested keeping shorthand names unchanged with mapping in "Your Files" section instead — cleaner approach
- **Issues encountered:** Initial backtick escaping in the addwork template used triple-backslash (`\\\``) instead of matching the existing single-backslash pattern (`\``). Fixed immediately.
- **Key decisions:** Used Unicode arrow (→) for shorthand→path mappings in both the instructions template and the runner's prompt preamble for consistency

## Step 9: Post-Implementation

Archive task, push changes.
