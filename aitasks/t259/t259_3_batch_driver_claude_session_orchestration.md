---
priority: high
effort: high
depends: [t259_2]
issue_type: feature
status: Ready
labels: [aitask_review]
created_at: 2026-02-26 18:42
updated_at: 2026-02-26 18:42
---

## Context

This task extends the batch driver script (t259_2) with Claude Code session orchestration. It handles building system prompts, invoking Claude in --print mode with --json-schema for structured output, parallel session management, output parsing, and failure handling.

Depends on: t259_2 (batch driver core must exist first)

## Key Files to Modify

- aiscripts/aitask_review_batch_run.sh (extend) — add session orchestration functions

## Reference Files for Patterns

- aiscripts/codebrowser/explain_manager.py — pattern for subprocess orchestration
- aiscripts/aitask_review_detect_env.sh — review guide content loading

## Implementation Plan

### Step 1: Build system prompt

- Read selected review guide markdown content (strip YAML frontmatter)
- Construct system prompt instructing Claude to review files and output findings in exact format
- Include the YAML schema definition in the prompt

### Step 2: Define JSON schema for structured output

- Create JSON schema matching the per-file findings YAML format
- Schema should validate: file path, findings array with id, guide, severity, category, line, description, suggested_fix
- Use claude --json-schema flag for guaranteed structured output

### Step 3: Claude session invocation

- For each batch file list:
  claude --print --json-schema <schema> --allowedTools "Read,Grep,Glob" --dangerously-skip-permissions --max-budget-usd 0.50 --model <model> "Review these files: <list>"
- Capture stdout to per-session output file
- Configurable --model flag (default: sonnet)

### Step 4: Parallel session management

- Background PIDs with semaphore pattern
- Track active_pids array, wait when at max_parallel
- Per-session: sessions/<session_id>/output.json, sessions/<session_id>/status
- timeout command for per-session timeout

### Step 5: Output parsing

- Parse JSON output from each session
- Write per-file .findings.yaml files under findings/
- Generate finding IDs (f001, f002, ...) per file

### Step 6: Manifest update

- Update manifest.yaml session entries with status, timing
- Compute summary: total_files, files_reviewed, files_failed, total_findings, by_severity, by_guide
- Set overall status: completed, partial, or failed

### Step 7: Add ait dispatcher command

- Add review-batch-run command to ait case statement

### Step 8: Failure handling

- Session timeout: kill, mark failed, record error
- Parse failure: save raw output, mark failed
- Partial results: set run status to partial

## Verification Steps

- shellcheck aiscripts/aitask_review_batch_run.sh
- Test with 2-3 files and 1 review guide
- Verify JSON schema produces valid structured output
- Test timeout handling (set very low timeout)
- Test parallel sessions (2+ concurrent)
