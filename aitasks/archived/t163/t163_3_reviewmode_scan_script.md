---
priority: medium
effort: medium
depends: [t163_2]
issue_type: feature
status: Done
labels: [aitask_review, bash_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-18 15:11
updated_at: 2026-02-18 16:04
completed_at: 2026-02-18 16:04
---

## Context

This is child task 3 of the review modes consolidation (t163). Create a bash helper script that scans reviewmode files for metadata completeness and finds similar files. This script is used by the classify skill (t163_4) and merge skill (t163_5) but is also useful standalone.

## Dependencies

- Depends on t163_2 (reviewmode files must have the new metadata fields)

## Key Files to Create

- `aiscripts/aitask_reviewmode_scan.sh` — **new file**

## Reference Files for Patterns

- `aiscripts/aitask_review_detect_env.sh` — Primary reference. Reuse its `.reviewmodesignore` filtering pattern (lines 297-325) and frontmatter parsing approach (lines 237-263). Also source `lib/terminal_compat.sh`.
- `aitasks/metadata/reviewmodes/.reviewmodesignore` — gitignore-style filter to honor
- `aitasks/metadata/reviewtypes.txt` — valid reviewtype values
- `aitasks/metadata/reviewlabels.txt` — valid reviewlabel values

## Implementation Plan

### Script: `aiscripts/aitask_reviewmode_scan.sh`

**Usage:**
```bash
./aiscripts/aitask_reviewmode_scan.sh [--missing-meta] [--environment ENV] [--reviewmodes-dir DIR] [--find-similar] [--compare FILE]
```

**Options:**
- `--missing-meta` — Only show files missing `reviewlabels` or `reviewtype` (default: show all)
- `--environment ENV` — Filter to files matching this environment (or `general` for universal modes)
- `--reviewmodes-dir DIR` — Path to reviewmodes directory (default: `aitasks/metadata/reviewmodes`)
- `--find-similar` — For each file, find the most similar other file by reviewlabel overlap
- `--compare FILE` — Compare one specific file against all others, output similarity scores

**Default output format** (pipe-delimited, one per line):
```
<relative_path>|<name>|<reviewtype_or_MISSING>|<reviewlabels_csv_or_MISSING>|<environment_csv_or_universal>
```

**`--find-similar` output** (appends a 6th field):
```
<relative_path>|<name>|<reviewtype>|<reviewlabels_csv>|<env>|<most_similar_path>:<overlap_count>
```

**`--compare FILE` output:**
```
<relative_path>|<name>|<similarity_score>|<shared_labels_csv>|<type_match:yes/no>|<env_overlap:yes/no>
```
Score = (shared_labels_count * 2) + (type_match ? 3 : 0) + (env_overlap ? 2 : 0). Sorted descending by score. Only files with score > 0.

### Implementation details:

1. **Argument parsing** — Follow the pattern from `aitask_review_detect_env.sh` (lines 35-60)

2. **Source terminal_compat.sh** — Same as other aiscripts:
   ```bash
   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
   source "$SCRIPT_DIR/lib/terminal_compat.sh"
   ```

3. **Discover files** — Use `find "$REVIEWMODES_DIR" -name "*.md" -type f -print0`

4. **Apply .reviewmodesignore filter** — Reuse the exact pattern from `aitask_review_detect_env.sh` lines 297-325:
   ```bash
   if [[ -f "$REVIEWMODES_DIR/.reviewmodesignore" ]]; then
       # Build relative paths, use git check-ignore --no-index
       # Build ignored_set associative array for O(1) lookup
       # Filter out ignored files
   fi
   ```

5. **Parse frontmatter** — Extended version of `parse_reviewmode()` that also extracts `reviewtype` and `reviewlabels`:
   ```bash
   parse_reviewmode() {
       local file="$1"
       local in_yaml=false
       local name="" description="" environment="" reviewtype="" reviewlabels=""
       
       while IFS= read -r line; do
           if [[ "$line" == "---" ]]; then
               if [[ "$in_yaml" == true ]]; then break; fi
               in_yaml=true; continue
           fi
           if [[ "$in_yaml" == true ]]; then
               if [[ "$line" =~ ^name:[[:space:]]*(.*) ]]; then
                   name="${BASH_REMATCH[1]}"
               elif [[ "$line" =~ ^description:[[:space:]]*(.*) ]]; then
                   description="${BASH_REMATCH[1]}"
               elif [[ "$line" =~ ^environment:[[:space:]]*\[(.*)\] ]]; then
                   environment="${BASH_REMATCH[1]// /}"
               elif [[ "$line" =~ ^reviewtype:[[:space:]]*(.*) ]]; then
                   reviewtype="${BASH_REMATCH[1]}"
               elif [[ "$line" =~ ^reviewlabels:[[:space:]]*\[(.*)\] ]]; then
                   reviewlabels="${BASH_REMATCH[1]// /}"
               fi
           fi
       done < "$file"
       
       local rel_path="${file#$REVIEWMODES_DIR/}"
       echo "${rel_path}|${name}|${reviewtype:-MISSING}|${reviewlabels:-MISSING}|${environment:-universal}"
   }
   ```

6. **`--missing-meta` filter** — After parsing all files, only output lines where field 3 or field 4 contains "MISSING"

7. **`--environment` filter** — After parsing, only output lines where field 5 contains the specified environment (or "universal" if `--environment general`)

8. **`--find-similar` mode** — For each file pair, compute Jaccard-style overlap on reviewlabels:
   - Split comma-separated labels into arrays
   - Count shared labels between each pair
   - For each file, output the best-matching other file and its overlap count
   - Skip pairs where both have MISSING labels

9. **`--compare FILE` mode** — Given one file, compare against all others:
   - Parse the target file's reviewtype, reviewlabels, environment
   - For each other file, compute: shared_labels_count, type_match (yes/no), env_overlap (yes/no)
   - Score = (shared_labels_count * 2) + (type_match ? 3 : 0) + (env_overlap ? 2 : 0)
   - Output sorted descending by score, only score > 0

### Script structure:
```
#!/usr/bin/env bash
# Header comment with usage
set -euo pipefail
# Source lib
# Defaults
# Argument parsing
# File discovery + .reviewmodesignore filter
# Parse all files
# Apply mode-specific output (default / --missing-meta / --find-similar / --compare)
```

## Verification Steps

1. Run without arguments — should list all 9 reviewmode files with metadata:
   ```bash
   ./aiscripts/aitask_reviewmode_scan.sh
   ```
2. Run with `--missing-meta` — should return empty (all files already have metadata from t163_2):
   ```bash
   ./aiscripts/aitask_reviewmode_scan.sh --missing-meta
   ```
3. Run with `--environment bash` — should show only `shell/shell_scripting.md`:
   ```bash
   ./aiscripts/aitask_reviewmode_scan.sh --environment bash
   ```
4. Run with `--find-similar` — should show similarity pairs:
   ```bash
   ./aiscripts/aitask_reviewmode_scan.sh --find-similar
   ```
5. Run with `--compare` on a specific file:
   ```bash
   ./aiscripts/aitask_reviewmode_scan.sh --compare general/security.md
   ```
6. Run shellcheck: `shellcheck aiscripts/aitask_reviewmode_scan.sh`
