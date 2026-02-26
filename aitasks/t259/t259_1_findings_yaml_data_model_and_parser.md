---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_review]
created_at: 2026-02-26 18:42
updated_at: 2026-02-26 18:42
---

## Context

This is the foundational data model for the batch review system (t259). All other components — the batch driver, TUI, and task creation — depend on this data model to read/write review findings in a standardized YAML format.

The data organization mirrors the aiexplains/ architecture: run directories named <dir_key>__<YYYYMMDD_HHMMSS> containing a manifest.yaml and per-file findings under findings/.

## Key Files to Modify

- aiscripts/reviewbrowser/findings_data.py (new) — dataclasses and YAML parsing
- aiscripts/reviewbrowser/__init__.py (new) — package init
- tests/test_findings_data.py (new) — unit tests with sample YAML fixtures

## Reference Files for Patterns

- aiscripts/codebrowser/annotation_data.py — pattern for dataclasses (AnnotationRange, FileExplainData, ExplainRunInfo)
- aiscripts/codebrowser/explain_manager.py — pattern for YAML parsing and data loading

## Implementation Plan

### Step 1: Create dataclasses

Create aiscripts/reviewbrowser/findings_data.py with:

- Finding: id, guide, guide_path, severity, category, line, end_line, code_snippet, description, suggested_fix, task_created
- FileFindings: file (relative path), reviewed_at, session_id, findings list
- SessionInfo: session_id, status, files list, started_at, completed_at, error
- ReviewRunManifest: run_id, dir_key, started_at, completed_at, status, source_root, source_is_external, review_guides, sessions, summary

### Step 2: Implement YAML parsing

- load_manifest(run_dir) -> ReviewRunManifest
- load_file_findings(findings_yaml_path) -> FileFindings
- list_findings_files(run_dir) -> list of Path
- aggregate_directory(run_dir, dir_path) -> dict with severity/guide/category counts

### Step 3: Write unit tests

- Sample YAML fixtures (manifest.yaml, per-file findings)
- Test parsing of manifest and file findings
- Test directory aggregation
- Test edge cases: empty findings, missing optional fields, malformed YAML

## Verification Steps

- python3 -m pytest tests/test_findings_data.py or python3 tests/test_findings_data.py
- Verify all dataclasses can round-trip through YAML
