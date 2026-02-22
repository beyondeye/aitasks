# macOS Shell Compatibility Guide

## Problem

macOS ships with BSD versions of `sed` and `grep`, not the GNU versions found on Linux. Several features commonly used on Linux do not work on macOS without modification.

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

## grep macOS Incompatibilities

macOS `grep` does not support PCRE (`-P` flag). This is a common pitfall when writing portable bash scripts.

| Feature | GNU grep | BSD grep (macOS) | Portable Alternative |
|---------|----------|-------------------|---------------------|
| PCRE mode | `grep -P 'pattern'` | Not supported | Use `grep -E` (extended regex) or `awk` |
| `\K` (reset match start) | `grep -oP '\*\*\K[^*]+'` | Not supported | `grep -o '\*\*[^*]*\*\*' \| sed 's/\*\*//g'` |
| Lookahead `(?=...)` | `grep -P 'foo(?=bar)'` | Not supported | `grep -o 'foobar' \| sed 's/bar$//'` |
| Lookbehind `(?<=...)` | `grep -P '(?<=foo)bar'` | Not supported | `grep -o 'foobar' \| sed 's/^foo//'` |
| Non-greedy `*?`, `+?` | `grep -oP 'a.*?b'` | Not supported | Use `awk` or `sed` for non-greedy matching |

**Rule of thumb:** Never use `grep -P` or `grep -oP` in portable scripts. Use `grep -E` (extended regex) for alternation and quantifiers, and pipe through `sed` when you need to trim match boundaries.

### Files Fixed in t186

| File | Issue | Fix Applied |
|------|-------|-------------|
| `website/new_release_post.sh` | `grep -oP '\*\*\K[^*]+(?=\*\*)'` | `grep -o '\*\*[^*]*\*\*' \| sed 's/\*\*//g'` |

## The `portable_date()` Helper

macOS BSD `date` does not support `date -d` (GNU coreutils). The `ait setup` script installs `coreutils` via brew (which provides `gdate`). Use the `portable_date()` wrapper from `terminal_compat.sh`:

```bash
portable_date() {
    if [[ "$(uname -s)" == "Darwin" ]]; then
        gdate "$@"
    else
        date "$@"
    fi
}
```

**Usage:** Drop-in replacement for `date` when using `-d`:
```bash
# Instead of: date -d "$date" +%s
portable_date -d "$date" +%s

# Instead of: date -d "$TODAY - 3 days" +%Y-%m-%d
portable_date -d "$TODAY - 3 days" +%Y-%m-%d
```

**Note:** Plain `date` calls without `-d` (e.g., `date '+%Y-%m-%d'`) work fine on macOS and don't need the wrapper.

## Shebang Convention

Always use `#!/usr/bin/env bash`, never `#!/bin/bash`. macOS system bash is 3.2 which lacks `declare -A`, `local -n`, `${var^}`. The `env bash` form picks up brew-installed bash 5.x from PATH.

## Files Fixed in t211

| File | Issue | Fix Applied |
|------|-------|-------------|
| 20 scripts (aiscripts/ + tests/) | `#!/bin/bash` shebang | Changed to `#!/usr/bin/env bash` |
| `aiscripts/aitask_stats.sh` | 15x `date -d` | `portable_date -d` |
| `aiscripts/aitask_issue_import.sh` | 1x `date -d` | `portable_date -d` |

## Files Fixed in t209

| File | Lines | Issue | Fix Applied |
|------|-------|-------|-------------|
| `aiscripts/aitask_archive.sh` | 114-115 | `sed -i` | `sed_inplace` |
| `aiscripts/aitask_archive.sh` | 118 | `sed -i` + GNU `a` | `awk` with temp file |
| `aiscripts/aitask_create.sh` | 275 | GNU `a` in pipe | `awk` in pipe |
| `aiscripts/aitask_stats.sh` | 61, 680 | `\U` uppercase | `${var^}` |
| `aiscripts/lib/task_utils.sh` | 274 | Grouped `{ $d; N; ba; }` across `-e` | `awk` for trailing blank line trim |
