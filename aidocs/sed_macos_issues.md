# sed macOS Compatibility Guide

## Problem

macOS ships with BSD sed, not GNU sed. Several sed features commonly used on Linux do not work on macOS without modification. This was identified and fixed in task t209.

## Incompatible Features

| Feature | GNU sed | BSD sed (macOS) | Portable Alternative |
|---------|---------|-----------------|---------------------|
| In-place edit | `sed -i "expr" file` | `sed -i '' "expr" file` | `sed_inplace "expr" file` (from `terminal_compat.sh`) |
| Append after match | `sed '/pattern/a text'` | Requires `a\` + literal newline | Use `awk '/pattern/{print; print "text"; next}1'` |
| Uppercase | `sed 's/^./\U&/'` | Not supported | Bash 4.0+: `${var^}` |
| Lowercase | `sed 's/./\L&/g'` | Not supported | Bash 4.0+: `${var,,}` |
| Grouped multi-line commands | `sed -e :a -e '/pat/{ $d; N; ba; }'` | `{` `}` grouping fails across `-e` args | Use `awk` for multi-line processing |

## Safe Features (work on both)

These sed features are POSIX-compatible and work on both GNU and BSD sed:

- Basic substitution: `sed 's/pattern/replacement/'`
- Global substitution: `sed 's/pattern/replacement/g'`
- Delete lines: `sed '/pattern/d'`
- Character classes: `[[:space:]]`, `[[:alpha:]]`, etc.
- Extended regex flag: `sed -E 's/pattern/replacement/'`
- Backreferences: `\(group\)` and `\1`
- Multiple expressions: `sed 's/a/b/;s/c/d/'`
- Address ranges: `sed '2,5s/foo/bar/'`

## The `sed_inplace()` Helper

Located in `aiscripts/lib/terminal_compat.sh`. Detects macOS and uses the correct `sed -i` syntax:

```bash
sed_inplace() {
    if [[ "$(uname -s)" == "Darwin" ]]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}
```

**Usage:** Drop-in replacement for `sed -i`:
```bash
# Instead of: sed -i "s/foo/bar/" "$file"
sed_inplace "s/foo/bar/" "$file"
```

## Portable Append-After-Line Pattern

When you need to insert a line after a matching line, use `awk` instead of sed's `a` command:

```bash
# Instead of: sed -i '/^pattern:/a new_line_text' "$file"
awk -v line="new_line_text" '/^pattern:/{print; print line; next}1' "$file" > "$file.tmp" && mv "$file.tmp" "$file"

# For piped content (no in-place needed):
content=$(echo "$content" | awk -v line="new_line_text" '/^pattern:/{print; print line; next}1')
```

## Files Fixed in t209

| File | Lines | Issue | Fix Applied |
|------|-------|-------|-------------|
| `aiscripts/aitask_archive.sh` | 114-115 | `sed -i` | `sed_inplace` |
| `aiscripts/aitask_archive.sh` | 118 | `sed -i` + GNU `a` | `awk` with temp file |
| `aiscripts/aitask_create.sh` | 275 | GNU `a` in pipe | `awk` in pipe |
| `aiscripts/aitask_stats.sh` | 61, 680 | `\U` uppercase | `${var^}` |
| `aiscripts/lib/task_utils.sh` | 274 | Grouped `{ $d; N; ba; }` across `-e` | `awk` for trailing blank line trim |
