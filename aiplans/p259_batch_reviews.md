---
Task: t259_batch_reviews.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: t259 — Batch Reviews

## Context

The current `aitask-review` skill is designed for interactive single-session use: select a file, pick review guides, review, interactively choose fixes, create tasks. This breaks down when reviewing many files or entire repositories because (1) a single Claude Code context can't handle the volume, and (2) interactive per-finding selection interrupts batch flow.

This task creates a batch review pipeline: a bash driver script spawns multiple Claude Code sessions (each reviewing a small file batch), findings are written to a standardized YAML format, and a Python Textual TUI lets users browse and act on findings.

## Architecture Overview

```
User → ait review-batch-run (bash driver)
           ├── fzf file/directory selection (supports external paths)
           ├── fzf review guide selection (reuses aitask_review_detect_env.sh)
           ├── Partition files into batches
           └── For each batch:
                 └── claude --print --json-schema ... (non-interactive)
                       └── Writes per-file findings YAML to aireviews/<run_dir>/

User → ait reviewbrowser (Python Textual TUI)
           ├── Virtual file tree from findings (via ReviewRunManager)
           ├── Directory summaries (severity, guide, category)
           ├── Finding detail view with code context
           └── Task creation from findings (aitask_create.sh --batch)

User → ait review-runs (bash management)
           ├── List all review runs (grouped by source directory)
           ├── Delete specific runs or all runs
           └── Cleanup stale runs (keep newest per directory key)
```

## Data Organization (mirrors `aiexplains/` architecture)

### Directory Key Encoding

Same convention as `aiexplains/`: source directory paths are converted to keys by replacing `/` with `__`. Root directory becomes `_root_`.

- `src/utils/` → `src__utils`
- `/home/user/external-project/lib/` → `_ext__home__user__external-project__lib` (external paths get `_ext` prefix)
- `.` → `_root_`

### Run Directory Naming: `<dir_key>__<YYYYMMDD_HHMMSS>`

```
aireviews/                                    # Root (gitignored, like aiexplains/)
  src__utils__20260226_143052/                # Run for src/utils/
    manifest.yaml                             # Run metadata and session tracking
    findings/                                 # Mirrors source tree (relative to source_root)
      helper.py.findings.yaml
      parser.py.findings.yaml
  _root___20260226_150000/                    # Run for project root
    manifest.yaml
    findings/
      main.py.findings.yaml
      src/
        auth.py.findings.yaml
```

### Cleanup Logic: Newest-Per-Key

Same as `aiexplains/`: for each directory key, keep only the newest run (by timestamp). Older runs are automatically removed. This is triggered:
- After a new batch review run completes
- By `ait review-cleanup` command
- On TUI startup (via ReviewRunManager)

### Run Manifest: `manifest.yaml`

```yaml
run_id: "src__utils__20260226_143052"
dir_key: "src__utils"
started_at: "2026-02-26T14:30:52"
completed_at: "2026-02-26T14:45:18"
status: completed  # running | completed | partial | failed
source_root: "/home/user/projects/myapp"
source_is_external: false
review_guides:
  - path: "general/security.md"
    name: "Security"
  - path: "python/python_style_guide.md"
    name: "Python Style Guide"
sessions:
  - session_id: "sess_001"
    status: completed
    files: ["src/auth.py", "src/login.py"]
    started_at: "2026-02-26T14:30:55"
    completed_at: "2026-02-26T14:35:12"
  - session_id: "sess_002"
    status: failed
    files: ["src/api/routes.py"]
    error: "Session timeout after 600s"
summary:
  total_files: 15
  files_reviewed: 14
  files_failed: 1
  total_findings: 42
  by_severity: {high: 5, medium: 22, low: 15}
  by_guide: {"Security": 18, "Python Style Guide": 24}
```

### Per-File Findings: `findings/<relative_path>.findings.yaml`

```yaml
file: "src/auth.py"
reviewed_at: "2026-02-26T14:33:00"
session_id: "sess_001"
findings:
  - id: "f001"
    guide: "Security"
    guide_path: "general/security.md"
    severity: high
    category: "injection"
    line: 42
    end_line: 45
    code_snippet: |
      query = f"SELECT * FROM users WHERE name = '{user_input}'"
    description: "SQL injection via string interpolation"
    suggested_fix: "Use parameterized queries"
    task_created: null  # populated when task is created: "t270"
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data organization | Mirror `aiexplains/` architecture | Proven pattern: dir_key encoding, timestamp runs, newest-per-key cleanup |
| Per-file vs monolithic findings | Per-file YAML | Parallel write safety, lazy loading |
| Storage location | `aireviews/` top-level | Follows `aiexplains/`, `aireviewguides/` naming |
| Gitignored | Yes | Ephemeral run data |
| Claude invocation | `claude --print --json-schema` | Non-interactive, structured output guaranteed |
| Model | Configurable `--model` flag, default `sonnet` | Balance cost/quality; user overrides per run |
| New skill vs extending aitask-review | New `aitask-review-batched` skill | Fundamentally different UX paradigm |
| TUI file tree | Virtual tree from paths | Works with external repos, shows only reviewed files |
| Directory summaries | Computed at render time | Avoids staleness, single source of truth |
| Management scripts | Mirror `explain_runs.sh` / `explain_cleanup.sh` | Consistent CLI patterns, proven management UX |
| Python manager class | `ReviewRunManager` mirroring `ExplainManager` | LRU caching, lazy loading, auto-cleanup on init |

## Child Task Breakdown (11 tasks)

### t259_1: Findings YAML Data Model and Parser
**No dependencies**

- Create `aiscripts/reviewbrowser/findings_data.py` with dataclasses: `Finding`, `FileFindings`, `SessionInfo`, `ReviewRun`
- YAML parsing: `ReviewRun.load(run_dir)`, `load_file_findings(rel_path)`
- Directory aggregation: `aggregate_directory(dir_path)` computes severity/guide/category counts
- Create `__init__.py`
- Write unit tests with sample YAML fixtures

**Key files:** `aiscripts/reviewbrowser/findings_data.py` (new), `aiscripts/codebrowser/annotation_data.py` (pattern ref)

### t259_2: Batch Driver Script — Core
**No dependencies**

- Create `aiscripts/aitask_review_batch_run.sh` with dual interactive/batch modes
- Interactive mode: fzf-based target selection (supports external paths via path input), review guide selection (reuses `aitask_review_detect_env.sh --files-stdin`)
- Batch mode: `--batch --targets "src/ lib/" --source-root /path --guides "general/security.md" --max-parallel 3 --timeout 600 --max-files-per-session 5 --model sonnet`
- File discovery: `git ls-files` for git repos, `find` for external paths, with extension filtering
- File partitioning: group by language, respect size limits (50KB or 5 files per batch)
- Run directory creation using `<dir_key>__<YYYYMMDD_HHMMSS>` naming convention:
  - Derive `dir_key` from target directory (same `dir_to_key()` function as aiexplains)
  - For external paths, prefix with `_ext` and encode the absolute path
  - Write initial `manifest.yaml` with `dir_key` field
- Source `lib/terminal_compat.sh` and `lib/task_utils.sh`
- Auto-cleanup: after run completes, remove older runs for the same `dir_key`

**Key files:** `aiscripts/aitask_review_batch_run.sh` (new), `aiscripts/aitask_create.sh` (pattern ref), `aiscripts/aitask_explain_extract_raw_data.sh` (pattern ref for dir_to_key)

### t259_3: Batch Driver — Claude Session Orchestration
**Depends on: t259_2**

- Build system prompt dynamically from selected review guide contents
- Define JSON schema for structured output (per-file findings)
- Invoke `claude --print --json-schema <schema> --allowedTools "Read,Grep,Glob" --dangerously-skip-permissions --max-budget-usd 0.50 --model <model>`
- Configurable `--model` flag (default: `sonnet`). User can override per run (e.g., `--model opus` for security, `--model haiku` for style)
- Parallel session management: background PIDs with semaphore pattern, configurable max parallelism
- Per-session output capture, timeout handling (`timeout` command)
- Parse JSON output into per-file `.findings.yaml` files under `findings/`
- Update `manifest.yaml` with session results and summary
- Failure handling: timeout, parse errors, partial completion marking

**Key files:** `aiscripts/aitask_review_batch_run.sh` (extend)

### t259_4: Review Run Management Scripts
**No dependencies**

Create bash scripts mirroring `aitask_explain_runs.sh` and `aitask_explain_cleanup.sh`:

**`aiscripts/aitask_review_runs.sh`** — List, delete, info for review runs:
- `--list`: Display all runs grouped by directory key, showing timestamp, status, file count, finding count
- `--info <run_dir>`: Show detailed manifest info for a run
- `--delete <run_dir>`: Delete a specific run (with realpath safety validation)
- `--delete-all`: Remove all runs
- Interactive mode (no args): fzf-based run selection with preview
- Add `review-runs` command to `ait` dispatcher

**`aiscripts/aitask_review_cleanup.sh`** — Cleanup stale runs:
- Keep newest per directory key (same algorithm as `aitask_explain_cleanup.sh`)
- `--target DIR`: Clean specific directory (default: `aireviews/`)
- `--dry-run`: Show what would be removed
- `--quiet`: Suppress output
- Marker validation: run dir must contain `manifest.yaml` to be valid
- Add `review-cleanup` command to `ait` dispatcher

**Key files:** `aiscripts/aitask_review_runs.sh` (new), `aiscripts/aitask_review_cleanup.sh` (new), `aiscripts/aitask_explain_runs.sh` (pattern ref), `aiscripts/aitask_explain_cleanup.sh` (pattern ref), `ait` (add commands)

### t259_5: Review Findings TUI — App Shell and File Tree
**Depends on: t259_1, t259_4**

- Create `aiscripts/reviewbrowser/reviewbrowser_app.py` — Textual App with two-panel layout (tree left, detail right)
- Create `aiscripts/reviewbrowser/findings_tree.py` — virtual `Tree` widget from reviewed file paths
- Create `aiscripts/reviewbrowser/review_run_manager.py` — Python manager class mirroring `ExplainManager`:
  - `load_run(run_dir)` → parse manifest and lazy-load findings
  - `find_latest_run(dir_key)` → find newest run for a directory key
  - `list_runs()` → list all available runs
  - `cleanup_stale_runs()` → keep newest per key (called on init)
  - LRU caching for per-file findings (like ExplainManager's task content cache)
- Tree nodes: files show `filename (N findings)` with severity color, directories show `dirname/ (N findings)`
- Run selection dialog when multiple runs exist in `aireviews/`
- Create `aiscripts/aitask_reviewbrowser.sh` launcher (follows `aitask_codebrowser.sh` pattern)
- Add `reviewbrowser` command to `ait` dispatcher
- Add `aiscripts/reviewbrowser/__pycache__/` to `.gitignore`

**Key files:** `aiscripts/reviewbrowser/reviewbrowser_app.py` (new), `aiscripts/reviewbrowser/findings_tree.py` (new), `aiscripts/reviewbrowser/review_run_manager.py` (new), `aiscripts/aitask_reviewbrowser.sh` (new), `ait` (add command), `aiscripts/codebrowser/codebrowser_app.py` (pattern ref), `aiscripts/codebrowser/explain_manager.py` (pattern ref)

### t259_6: Review Findings TUI — Findings Viewer
**Depends on: t259_1, t259_5**

- Create `aiscripts/reviewbrowser/findings_viewer.py` — right-panel widget
- File view: findings grouped by guide, sorted by severity, Rich styled tables
- Directory view: aggregate summary (severity counts, guide counts, file list sorted by severity)
- Root view: full run summary from manifest
- Severity/guide filtering via toggle keybindings
- Source code preview: read relevant lines from `source_root` when finding is highlighted
- Keybindings: `f` filter severity, `g` filter guide, `r` refresh from disk

**Key files:** `aiscripts/reviewbrowser/findings_viewer.py` (new), `aiscripts/codebrowser/code_viewer.py` (pattern ref for Rich tables)

### t259_7: Task Creation from TUI
**Depends on: t259_5, t259_6**

- Create `aiscripts/reviewbrowser/task_creator.py`
- Single finding → task (`t` key): invoke `aitask_create.sh --batch --commit`
- Multi-finding → tasks (`T` key): grouping options (by guide, by file, all-in-one)
- Parent+children pattern for grouped findings (same as aitask-review Step 4)
- Update `task_created` field in findings YAML after creation
- Keybindings integrated into main app

**Key files:** `aiscripts/reviewbrowser/task_creator.py` (new), `aiscripts/aitask_create.sh` (invoked)

### t259_8: Batch Review Skill and Integration
**Depends on: t259_2, t259_3**

- Create `.claude/skills/aitask-review-batched/SKILL.md` — new Claude Code skill
- Skill workflow: target selection → guide selection → parameter config → launch batch driver → inform user to run `ait reviewbrowser`
- Profile integration: add `review_batch_max_parallel`, `review_batch_timeout`, `review_batch_model` keys
- Update `ait` help text with all new commands (review-batch-run, reviewbrowser, review-runs, review-cleanup)
- Add `aireviews/` to `.gitignore`
- Update `seed/` templates if needed

**Key files:** `.claude/skills/aitask-review-batched/SKILL.md` (new), `ait` (update help text), `.gitignore` (add aireviews/)

## Dependency Graph

```
t259_1 (Data Model) ───┬──→ t259_5 (TUI Shell+Manager) ──→ t259_6 (Viewer) ──→ t259_7 (Tasks)
                        │         ↑                               │
t259_4 (Run Mgmt) ─────┘         │                               └──→ t259_10 (TUI Model Settings) ←── t265
                                  │
t259_2 (Batch Core) ──→ t259_3 (Session Orch.) ──→ t259_8 (Skill)
                              │                         │
                              └──→ t259_9 (Driver Model Config) ←── t265
                                                        └──→ t259_11 (Skill Model Config) ←── t265
```

- **Parallel track 1**: t259_1 + t259_4 (no deps) → t259_5 → t259_6 → t259_7
- **Parallel track 2**: t259_2 (no deps) → t259_3 → t259_8
- Tasks 1, 2, 4 can all start in parallel
- Task 5 needs 1 + 4 (data model + management scripts inform the manager class)
- Task 8 integrates everything into the skill
- **t265-dependent tasks** (t259_9, t259_10, t259_11): blocked on both their t259 predecessors and t265

## New `ait` Commands Summary

| Command | Script | Purpose |
|---------|--------|---------|
| `review-batch-run` | `aitask_review_batch_run.sh` | Run batch review (interactive or `--batch`) |
| `reviewbrowser` | `aitask_reviewbrowser.sh` | Launch findings TUI |
| `review-runs` | `aitask_review_runs.sh` | List/delete/info review runs |
| `review-cleanup` | `aitask_review_cleanup.sh` | Cleanup stale review runs |

### t259_9: Integrate batch driver with model configuration from t265
**Depends on: t259_3, t265**

**Note:** Task details are not fully defined yet — implementation will depend on the model configuration infrastructure created in t265 and related tasks.

- Replace hardcoded `--model sonnet` default with reading from `aitasks/metadata/models_claude.txt`
- Use `claude/<model>` naming convention (e.g., `claude/sonnet4.6`) consistent with t265
- Batch driver's `--model` flag should accept the `claude/<model>` format
- Record the model used in `manifest.yaml` per session

### t259_10: Add model settings to reviewbrowser TUI
**Depends on: t259_5, t265**

**Note:** Task details are not fully defined yet — implementation will depend on the settings screen patterns established in t265 and related tasks.

- Add settings screen to reviewbrowser TUI (same pattern as codebrowser settings from t265)
- Model selector for batch review invocations from TUI
- Read available models from `aitasks/metadata/models_claude.txt`
- Store selected model preference in TUI settings

### t259_11: Integrate batch review skill with model configuration
**Depends on: t259_8, t265**

**Note:** Task details are not fully defined yet — implementation will depend on the model configuration infrastructure created in t265 and related tasks.

- Update `.claude/skills/aitask-review-batched/SKILL.md` to read model from project/profile config
- Add `review_batch_model` profile key that uses `claude/<model>` format
- Fall back to project default model if not specified

**Note for t259_1 through t259_8:** Use a simple `--model` CLI flag defaulting to `sonnet` as a temporary solution. Tasks t259_9–t259_11 will integrate with the proper model configuration infrastructure from t265.

## Verification

- Run `bash tests/test_*.sh` to ensure no regressions
- `shellcheck aiscripts/aitask_review_batch_run.sh aiscripts/aitask_review_runs.sh aiscripts/aitask_review_cleanup.sh`
- Test batch driver with a small directory (2-3 files, 1 guide)
- Test run management: list, cleanup, delete
- Test TUI with sample findings YAML (fixture data from t259_1)
- Test task creation from TUI findings
- Test with external directory (outside project repo)
- Test cleanup logic: create multiple runs for same dir_key, verify only newest survives
