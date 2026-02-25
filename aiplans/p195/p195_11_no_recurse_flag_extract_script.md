---
Task: t195_11_no_recurse_flag_extract_script.md
Parent Task: aitasks/t195_python_codebrowser.md
Sibling Tasks: aitasks/t195/t195_4_*.md
Archived Sibling Plans: aiplans/archived/p195/p195_*_*.md
Branch: main
Base branch: main
---

# Plan: t195_11 — Add `--no-recurse` Flag to Extract Script

## Steps

### 1. Add flag to argument parser
```bash
NO_RECURSE=false
# In case statement:
--no-recurse) NO_RECURSE=true; shift ;;
```

### 2. Modify `expand_path()`
When `$NO_RECURSE` is true and path is a directory:
```bash
git ls-files "$path" | while IFS= read -r f; do
    local rel="${f#"$path"/}"
    [[ "$rel" == */* ]] && continue  # skip subdirectory files
    if file -b --mime-encoding "$f" 2>/dev/null | grep -qv 'binary'; then
        echo "$f"
    fi
done
```

### 3. Handle edge cases
- Root directory: filter files with no `/` in path
- Directory with no direct files: empty result, existing "no files" handling applies

### 4. Update `explain_manager.py`
- Change from passing individual files to: `["--no-recurse", "--gather", str(directory)]`
- Remove Python-side depth filtering

### 5. Add to help text
Document `--no-recurse` in the script's usage section.

## Verification
- `--no-recurse` on `aiscripts/` → only direct .sh files, not `aiscripts/board/` or `aiscripts/lib/` files
- Without flag → recursive (unchanged)
- Root directory with `--no-recurse` → top-level files only
- Codebrowser uses `--no-recurse` correctly
