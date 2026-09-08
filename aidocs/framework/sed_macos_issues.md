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
| BRE quantifiers `\?` `\+` `\|` | `sed 's/ab\?c/x/'` | Treated as literal `?`/`+`/`\|` — the match silently fails | Use `sed -E` with bare `?` `+` `\|` (e.g. `sed -E 's/ab?c/x/'`) |
| Bracket **ranges** (`[x-y]`) | Collation-ordered; `[0-?]` accepted through 4.9, **rejected from 4.10** | Collation-ordered — rejected (`REG_ERANGE`) | `LC_ALL=C sed ...`, or enumerate: `[0-9:;<=>?]` |
| Hex escapes `\xNN` | `sed 's/\x1b//'` matches the ESC byte | Not an escape — matches a literal `x`, `1`, `b` | Let **bash** produce the byte: `sed $'s/\033//'` |

**`\xNN` fails the same silent way as `\?`.** The most common instance is
stripping ANSI color from captured output before asserting on it —
`sed 's/\x1b\[[0-9;]*m//g'`. On BSD sed the escape is never recognized, the
substitution does not match, and the wrapper survives; an exact assertion then
fails against a perfectly correct implementation, which reads as a bug in the
code under test rather than in the test. Write the ESC byte with bash's `$'...'`
quoting instead — `sed $'s/\033\[[0-9;]*m//g'` — so bash expands the escape
before `sed` ever sees it and both implementations receive the same literal
byte. (Octal `\033` inside `$'...'` is a *bash* escape, not a sed one; that is
exactly why it is portable.)

**`\?` / `\+` / `\|` are the most common silent footgun.** In Basic Regular
Expressions these are GNU extensions; BSD sed treats the backslashed form as a
literal character, so the `s/.../.../ ` simply does not match and the input
passes through unchanged. There is **no error** — the caller just receives the
raw, un-substituted string, which then surfaces as bad data far downstream (a
mis-parsed version number, an un-stripped filename prefix, garbled output).
Always reach for `sed -E` (ERE) and write the quantifier bare: `?`, `+`, `|`.

### Bracket ranges are ordered by the locale, not by ASCII

A bracket *range* `[x-y]` is valid only when its endpoints are in non-descending
order under the **locale's collating sequence**. That sequence is not ASCII, so
a range that looks obviously well-formed can be rejected outright:

```
$ printf 'x\n' | sed 's/[0-?]//g'
sed: -e expression #1, char 10: Invalid range end      # rc=1
$ printf 'x\n' | LC_ALL=C sed 's/[0-?]//g'
x                                                      # rc=0
```

BSD sed has always enforced this. **GNU sed accepted such ranges through 4.9 and
rejects them from 4.10** — which is how a pattern that had worked on Linux for
years became a hard failure on an ordinary package upgrade (t1637: it killed
every shadow-agent pane capture at once, because the helper is `set -euo
pipefail` and the strip sits on its whole stdout path).

Measured on GNU sed 4.10 / glibc 2.44 under `en_US.UTF-8`, the range-collation
order is:

    space + punctuation (in ASCII order)  <  digits  <  lowercase  <  uppercase

Do not extrapolate that from ASCII intuition — it produces surprises in both
directions:

| Range | Verdict | Why |
|-------|---------|-----|
| `[0-9]` `[a-z]` `[A-Z]` | OK | endpoints inside one block |
| `[0-A]` `[9-a]` `[!-~]` `[@-~]` `[:-@]` | **OK** | ascending in this order, though they cross blocks |
| `[0-?]` | **rejected** | `?` is punctuation, so it sorts *before* the digits |
| `[A-z]` `[A-b]` `[M-a]` | **rejected** | lowercase sorts *before* uppercase as a block — so `z < A` |

Note `[A-z]`: uppercase-to-lowercase is a common way to spell "all letters and
the punctuation between them", and it is exactly backwards here. Note too that
the ordering is **blocked**, not interleaved — `[a-B]` is accepted while
`[A-b]` is not.

**Two portable fixes.** Pin `LC_ALL=C` on the command, which restores byte-value
semantics for the whole expression (this is the repo idiom — see
`shadow_strip_ansi` in `.aitask-scripts/aitask_shadow_capture.sh`, plus
`lib/task_utils.sh`, `lib/pid_anchor.sh`); or enumerate the members explicitly,
which is locale-proof without changing the process locale. `LC_ALL=C` is safe on
UTF-8 text for a pattern built from 7-bit bytes: multi-byte sequences contain no
7-bit bytes and pass through untouched.

This row is the one entry in this guide that is **not macOS-specific** — a UTF-8
locale is the default nearly everywhere, so treat a suspect range as broken on
every platform, Linux included.

## Safe Features (work on both)

These sed features are POSIX-compatible and work on both GNU and BSD sed:

- Basic substitution: `sed 's/pattern/replacement/'`
- Global substitution: `sed 's/pattern/replacement/g'`
- Delete lines: `sed '/pattern/d'`
- Character *classes*: `[[:space:]]`, `[[:alpha:]]`, etc. — locale-independent,
  unlike bracket *ranges* (see above)
- Extended regex flag: `sed -E 's/pattern/replacement/'`
- Backreferences: `\(group\)` and `\1`
- Multiple expressions: `sed 's/a/b/;s/c/d/'`
- Address ranges: `sed '2,5s/foo/bar/'`

> **Note:** backreference *grouping* `\(…\)` is portable, but the `?`/`+`/`|`
> *quantifiers* are **not** portable in their backslashed BRE form — see the
> incompatibility row above. Prefer `sed -E` whenever a pattern needs `?`, `+`,
> `|`, or grouping.

> **Note:** a bracket *expression* is portable, but a *range* inside one is only
> portable when its endpoints ascend in the locale's collating sequence. `[0-9]`,
> `[a-z]`, `[A-Z]` are always safe; `[0-?]` and `[A-z]` are rejected under
> `en_US.UTF-8`. Pin `LC_ALL=C` or enumerate — see the section above.

## The `sed_inplace()` Helper

Located in `.aitask-scripts/lib/terminal_compat.sh`. Detects macOS and uses the correct `sed -i` syntax:

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

## awk macOS Incompatibilities

This guide repeatedly recommends `awk` as the portable replacement for sed's
GNU-only features — but `awk` has its own GNU/BSD split. macOS ships BSD/`nawk`,
not GNU `gawk`, so `gawk`-only extensions are **hard syntax errors** under BSD
awk (the script fails to parse and exits non-zero), not silent no-ops.

| Feature | gawk (GNU) | BSD awk (macOS) | Portable Alternative |
|---------|------------|------------------|---------------------|
| Capture array in `match()` | `match(str, re, arr); v = arr[1]` | Syntax error — 3-arg `match()` is gawk-only | 2-arg `match(str, re)` + `substr($0, RSTART, RLENGTH)`, or `sub()` to strip the prefix, or `split()` |
| `gensub()` | `gensub(/re/, "x", "g", s)` | Not supported | `gsub()`/`sub()` (in-place on the field/var) |
| `\<` `\>` word boundaries | supported | Not supported | `[[:<:]]`/`[[:>:]]` (BSD) are non-portable too — match surrounding chars explicitly |
| `length(arr)` | supported | supported on modern nawk | safe in practice; avoid on very old awk |

**The 2-arg `match()` form is portable and fine:** `match($0, /^[ \t]*/)` then
reading `RSTART` / `RLENGTH` works on both. Only the **3-argument** capture-array
form (`match(str, re, arr)`) is the gawk extension that breaks.

**Rule of thumb:** keep awk scripts to POSIX features — `~`, `sub()`, `gsub()`,
`split()`, `substr()`, `match()` (2-arg) with `RSTART`/`RLENGTH`. Do not use the
3-arg `match()`, `gensub()`, or `\<`/`\>`.

## After fixing one portability bug, sweep for the whole class

These footguns travel in families. A single `\?` or 3-arg `match()` almost
always has siblings elsewhere in the tree. After fixing one instance, grep
`.aitask-scripts/*.sh` (and `tests/`) for the entire class before considering
the bug closed:

```bash
# GNU-only sed BRE quantifiers not in -E/-r mode:
grep -rnE "sed '[^']*\\\\[?+|]" .aitask-scripts --include='*.sh' | grep -vE 'sed -E|sed -r'

# gawk-only 3-arg match() (str, re, arr) — note 2-arg match() is fine:
grep -rnE "match\([^,]+,[^,]+,[^)]+\)" .aitask-scripts --include='*.sh'
```

**The `\xNN` class is enforced, not swept.** That family recurred twice despite
this instruction (t1641, t1646 — each caught only because someone remembered to
sweep), so it now has a guard test instead of a grep you have to run:

```bash
bash tests/test_no_sed_hex_escape.sh
```

It scans every tracked `*.sh` for a `sed`/`awk`/`tr` expression carrying a `\xNN`
escape, suppressing pure comments and — segment-scoped, not line-scoped — any
`\xNN` inside bash `$'…'` quoting, where bash expands it and it is correct. Add
new sites to nothing: just use the `$'…'` form. The remaining classes above are
still manual sweeps.

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

## `wc -l` Output Whitespace

macOS BSD `wc -l` pads output with leading spaces, while GNU `wc -l` does not:

```bash
# macOS:  echo "hello" | wc -l  →  "       1"
# Linux:  echo "hello" | wc -l  →  "1"
```

**When it's safe (no fix needed):** Bash strips leading whitespace in arithmetic contexts. All of these work correctly on both platforms:

```bash
count=$(echo "$files" | wc -l)
if [[ "$count" -gt 1 ]]; then ...    # ✓ -gt is arithmetic
if [[ $count -gt 0 ]]; then ...      # ✓ -gt is arithmetic
total=$((count + 1))                  # ✓ $(()) is arithmetic
echo "Found $count files"            # ✓ cosmetic only (extra spaces harmless)
```

**When it breaks:** Exact string comparisons fail:

```bash
count=$(echo "$files" | wc -l)
if [[ "$count" == "1" ]]; then ...    # ✗ "       1" != "1"
assert_eq "1" "$count"                # ✗ same problem
```

**Portable fix:** Strip whitespace when the value will be used in string comparisons:

```bash
count=$(echo "$files" | wc -l | tr -d ' ')     # explicit trim
count=$(echo "$files" | wc -l | xargs)          # xargs trims whitespace
```

Or handle it in the comparison helper (as done in test `assert_eq` functions):

```bash
assert_eq() {
    local expected="$(echo "$2" | xargs)"   # trim whitespace
    local actual="$(echo "$3" | xargs)"
    [[ "$expected" == "$actual" ]]
}
```

## `mktemp` Portability

macOS BSD `mktemp` does not support the `--suffix` option (GNU coreutils extension), **and it only substitutes the `XXXXXX` placeholder when the placeholder ends the template.**

```bash
# GNU only (fails on macOS):
tmpfile=$(mktemp --suffix=.md)

# ALSO BROKEN on macOS -- and it does not fail, which is why it survived:
tmpfile=$(mktemp "${TMPDIR:-/tmp}/prefix_XXXXXX.ext")

# Portable, no suffix needed:
tmpfile=$(mktemp "${TMPDIR:-/tmp}/prefix_XXXXXX")

# Portable, suffix preserved (source lib/terminal_compat.sh):
tmpfile=$(mktemp_suffixed "${TMPDIR:-/tmp}/prefix_XXXXXX.ext")
```

**The middle form is a trap, and this document used to recommend it (t1729).** With anything after the `XXXXXX`, BSD `mktemp` does not substitute — it creates a file named *literally* `prefix_XXXXXX.ext` and **exits 0**. The caller looks fine, and on Linux it genuinely is fine, because GNU `mktemp` substitutes. On macOS the second call and every one after it fails with `mkstemp failed: File exists`, permanently, because that fixed name persists in `$TMPDIR`. Two further consequences: the path is predictable rather than unguessable, and two concurrent runs share one file.

Symptom to recognise: a script that worked once and now reports a temp-file infrastructure error on a machine where nothing changed. Check `ls "$TMPDIR"/*XXXXXX*`.

`mktemp_suffixed` (in `.aitask-scripts/lib/terminal_compat.sh`) takes the **same single argument**, so migrating a call site is just `mktemp` → `mktemp_suffixed`. It splits the template at the last `XXXXXX`, lets `mktemp` pick a genuinely unique name, then renames it to carry the suffix. Use it whenever the extension matters (an editor's syntax mode, a parser that sniffs it); otherwise just put `XXXXXX` last.

For a skill procedure or any other instruction an agent executes without sourcing the framework libs, use the no-suffix form — the helper will not be in scope there.

**Note:** `TMPDIR` is set on macOS (typically `/var/folders/...`), so using `"${TMPDIR:-/tmp}"` respects the platform's temp directory. The `XXXXXX` template is required on both platforms. Plain `mktemp` (no arguments) and `mktemp -d` work identically on both.

## `base64` Portability

macOS and Linux use different flags for base64 decoding:

| Platform | Decode flag | Long form |
|----------|-------------|-----------|
| Linux (GNU coreutils) | `base64 -d` | `base64 --decode` |
| macOS (BSD) | `base64 -D` | Not supported |

Modern macOS (10.15+) accepts both `-d` and `-D`, but older versions only accept `-D`. The long form `--decode` is not available on macOS BSD `base64`.

**In scripts:** Use a conditional or avoid `base64` if possible:
```bash
if [[ "$(uname -s)" == "Darwin" ]]; then
    decoded=$(echo "$encoded" | base64 -D)
else
    decoded=$(echo "$encoded" | base64 -d)
fi
```

**In skill files / AI instructions:** Document both flags side by side: `base64 -d` (Linux) or `base64 -D` (macOS).

## `stat` Portability

There is no portable `stat` format flag. GNU uses `-c`, BSD uses `-f`, and the
format strings themselves differ:

| Platform | Octal mode | Size |
|----------|------------|------|
| Linux (GNU coreutils) | `stat -c '%a'` | `stat -c '%s'` |
| macOS (BSD) | `stat -f '%Lp'` | `stat -f '%z'` |

`%Lp` (not `%p`) is what yields the bare permission bits on BSD — `%p` includes
the file type in the high bits.

The repo idiom is a fallback chain, not a `uname` branch (`lib/atomic_write.sh`,
`aitask_gate.sh`, `aitask_create.sh`):

```bash
ait_file_mode() {
    stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null || true
}
```

The chain is safe in both directions: on macOS `stat -c` exits 1 and the BSD form
answers; on GNU the first form answers and the second is never reached. `stat -f`
means "print filesystem status" on GNU, but it is only ever reached there when the
file is absent, where it fails too.

## `readlink` Portability

BSD `readlink` had **no `-f`** before macOS 12.3. Code that must run on older
macOS walks the symlink chain by hand rather than calling `readlink -f`:

```bash
# GNU / macOS >= 12.3 only:
resolved=$(readlink -f "$path")

# Portable: walk the chain with bare `readlink`, bounded, resolving
# relative targets against the link's own directory (lib/atomic_write.sh:
# ait_atomic_resolve, bounded at 40 hops).
```

A hand-walked chain needs three things a naive loop omits: a **hop bound** with an
explicit failure (otherwise a symlink cycle spins forever), resolution of
**relative** targets against the *link's* directory rather than `$PWD`, and
`cd -P` on the final directory so the returned path is fully physical.

Note that BSD `readlink` also prints nothing (exit 1) for a non-symlink, whereas
GNU `readlink -f` prints the path itself — so the two are not drop-in equivalents
even where `-f` exists.

## `mkdir -p` Through a Dangling Symlink

`mkdir -p` fails when a leading path component is a **dangling** symlink — the
`-p` "already exists, that's fine" clause does not cover it, because the
component does not exist as far as `mkdir` is concerned. Both platforms fail and
both exit non-zero, but **the errno and the message differ**:

| Platform | errno | Message |
|----------|-------|---------|
| Linux (GNU coreutils) | `EEXIST` | `File exists` |
| macOS (BSD) | `ENOENT` | `No such file or directory` |

```bash
d=$(mktemp -d); ln -s "$d/gone" "$d/aitasks"
mkdir -p "$d/aitasks/metadata"; echo "rc=$?"
# Linux: mkdir: cannot create directory '…/aitasks': File exists            rc=1
# macOS: mkdir: …/aitasks: No such file or directory                        rc=1
```

**Assert on the exit status, never on the message.** A test that greps for
`File exists` — the natural thing to write from a Linux console session — is a
macOS-only failure that never fires in CI. This is the whole class the entry
exists for: the *behaviour* is portable, the *diagnostic* is not.

This bites the install path specifically. `install.sh` runs under
`set -euo pipefail`, so an unguarded `mkdir -p` on a repo whose gitignored
`aitasks -> .aitask-data/aitasks` symlinks were captured in a tarball aborts the
entire install with an opaque diagnostic — the regression `ensure_data_root`
(t1193) exists to repair. Anything that writes through a path a user may have
symlinked needs the same guard, not a `2>/dev/null ||` that swallows the errno.

## Shebang Convention

Always use `#!/usr/bin/env bash`, never `#!/bin/bash`. macOS system bash is 3.2 which lacks `declare -A`, `local -n`, `${var^}`. The `env bash` form picks up brew-installed bash 5.x from PATH.

## Files Fixed in t211

| File | Issue | Fix Applied |
|------|-------|-------------|
| 20 scripts (.aitask-scripts/ + tests/) | `#!/bin/bash` shebang | Changed to `#!/usr/bin/env bash` |
| `.aitask-scripts/aitask_stats.sh` | 15x `date -d` | `portable_date -d` |
| `.aitask-scripts/aitask_issue_import.sh` | 1x `date -d` | `portable_date -d` |

## Files Fixed in t209

| File | Lines | Issue | Fix Applied |
|------|-------|-------|-------------|
| `.aitask-scripts/aitask_archive.sh` | 114-115 | `sed -i` | `sed_inplace` |
| `.aitask-scripts/aitask_archive.sh` | 118 | `sed -i` + GNU `a` | `awk` with temp file |
| `.aitask-scripts/aitask_create.sh` | 275 | GNU `a` in pipe | `awk` in pipe |
| `.aitask-scripts/aitask_stats.sh` | 61, 680 | `\U` uppercase | `${var^}` |
| `.aitask-scripts/lib/task_utils.sh` | 274 | Grouped `{ $d; N; ba; }` across `-e` | `awk` for trailing blank line trim |

## Files Fixed in t213

| File | Line | Issue | Fix Applied |
|------|------|-------|-------------|
| `.aitask-scripts/aitask_pick_own.sh` | 159 | `grep -oP` with `\K` (PCRE) | `grep -o` + `sed` pipe |
| `.aitask-scripts/aitask_update.sh` | 926 | `mktemp --suffix=.md` (GNU-only) | Template pattern `mktemp "${TMPDIR:-/tmp}/aitask_XXXXXX.md"` — **this replacement was itself broken on BSD; superseded by t1729, see the `mktemp` Portability section. Do not copy this row.** |

## Files Fixed in t658

Full repo-wide audit run on macOS arm64 (Darwin 24.6, bash 5.3 from brew). 76 production scripts in `.aitask-scripts/`, 7 lib scripts, and 98 bash tests scanned against every footgun documented above. The static sweep was largely clean — the previous tasks (t186/t209/t211/t213) had absorbed most of the platform-specific patterns. Two real bugs remained in the test suite, both surfaced by running the full suite on macOS:

| File | Line | Issue | Fix Applied |
|------|------|-------|-------------|
| `tests/test_archive_no_overbroad_add.sh` | 148, 257, 364 | Bare `sed -i 's/.../.../' file` — BSD sed parses the expression as the backup suffix and the file path as the expression, then errors with `command a expects \ followed by text` | Sourced `lib/terminal_compat.sh` and switched to `sed_inplace` |
| `tests/test_multi_session_primitives.sh` | 138 | `FAKE_PROJ` came straight from `mktemp -d "${TMPDIR:-/tmp}/..."`. macOS sets `TMPDIR` with a trailing `/` (so the path keeps a `//`), and tmux `pane_current_path` resolves `/var/folders/...` to `/private/var/folders/...` — both made the assertion strings diverge from the discovered session path | Canonicalize via `FAKE_PROJ=$(cd "$FAKE_PROJ" && pwd -P)` immediately after `mktemp` |

Test suite delta (98 bash tests, run on macOS):
- Baseline: 75 PASS, 23 FAIL.
- Post-fix: 77 PASS, 21 FAIL (no regressions; the two fixes above account for the entire delta).

The 21 remaining FAILs are unrelated to macOS portability: missing system-Python dependencies (`yaml`/`textual`/`rich` outside the `~/.aitask/venv/`), missing `codex` CLI, stale hand-curated copy lists in a few test setups (`tests/test_crew_groups.sh`, `tests/test_crew_report.sh`, `tests/test_data_branch_migration.sh` no longer copy `lib/launch_modes_sh.sh` / `lib/archive_scan.sh`), stale skill-count expectations in `test_gemini_setup.sh` / `test_opencode_setup.sh`, and other preexisting issues. They reproduce on Linux too and are out of scope for this audit; track them as separate follow-up tasks if/when needed.

## Files Fixed in t1729

The `mktemp "…_XXXXXX.ext"` pattern this document itself recommended is broken on
BSD: the placeholder is only substituted when it ends the template, so macOS
created a file named literally `…_XXXXXX.ext`, returned 0, and then failed every
subsequent call with `mkstemp failed: File exists` — permanently, because the
fixed name persists in `$TMPDIR`. Invisible on Linux, where GNU `mktemp`
substitutes. Found via `tests/test_settings_project_config_value_types.py`, whose
`test_the_saved_hook_actually_runs` failed on every run after the first.

| File | Sites | Fix Applied |
|------|-------|-------------|
| `.aitask-scripts/lib/terminal_compat.sh` | new | Added `mktemp_suffixed`, a drop-in taking the same single template argument |
| 10 scripts under `.aitask-scripts/` | 15 | `mktemp` → `mktemp_suffixed` (all already source `terminal_compat.sh`) |
| 6 bash tests under `tests/` | 17 | Same substitution; four gained a `terminal_compat.sh` source line |
| `.claude/skills/task-workflow/manual-verification.md` | 1 | No-suffix form — a skill procedure runs without the framework libs in scope; rendered variants and procedure goldens regenerated |

Because the previous "portable" form failed *silently and only on the second
run*, a static sweep could not have found it: only running a suite twice on one
macOS machine exposes it.

## Files Fixed in t931

Surfaced while running `ait setup` on macOS — the run silently aborted right
after the Claude permission-merge step (a `set -euo pipefail` exit whose
warning was swallowed by a `"$(...)"` capture), and the permission list printed
garbled. The profile resolver also failed to parse under BSD awk.

| File | Issue | Fix Applied |
|------|-------|-------------|
| `.aitask-scripts/aitask_setup.sh` | Permission preview used `sed 's/",\?$//'` — BSD sed left the trailing `",` un-stripped | `sed -E 's/",?$//'` |
| `.aitask-scripts/aitask_skill_resolve_profile.sh` | gawk-only 3-arg `match(str, re, arr)` capture form — hard syntax error under BSD awk, broke every profile-aware skill | Rewrote with POSIX `~` / `sub()` / `substr()` |

## Files Fixed in t932

Sweep for the `sed \?` class after t931 found three more instances (four lines).

| File | Line | Issue | Fix Applied |
|------|------|-------|-------------|
| `.aitask-scripts/aitask_setup.sh` | 1474 | `sed 's/.*"tag_name": *"v\?\([^"]*\)".*/\1/'` release-tag parse failed under BSD sed → bogus "Update available" hint | `sed -E 's/.*"tag_name": *"v?([^"]*)".*/\1/'` |
| `.aitask-scripts/aitask_upgrade.sh` | 56 | Same release-tag parse | Same `sed -E` fix |
| `.aitask-scripts/aitask_update.sh` | 1472, 1773 | `sed 's/^t[0-9]*_\([0-9]*_\)\?//'` left the `t<N>_<child>_` prefix in humanized commit-message names | `sed -E 's/^t[0-9]*_([0-9]*_)?//'` |

## Files Audited in t926

Periodic full-repo audit (June 2026) on macOS arm64 (Darwin 24.6, bash 5.3 from
brew, BSD awk `20200816`, BSD sed). Inventory scanned: 111 `.sh` in
`.aitask-scripts/` (94 top-level), 113 `.py`, and 172 top-level bash tests in
`tests/`.

**Static sweep — clean (no fixes needed).** Every footgun class above was
re-swept across bash + Python; all results were either absent or already
guarded/portable:

- GNU-only `sed` BRE quantifiers (`\?`/`\+`/`\|`), gawk 3-arg `match()`,
  `grep -P`/`-oP`, `mktemp --suffix`, `sed \U`/`\L`: **none**.
- All `date -d` call sites in production scripts (`aitask_verified_update.sh`,
  `aitask_usage_update.sh`, `aitask_explain_context.sh`,
  `aitask_plan_verified.sh`, `lib/verified_update_lib.sh`) are **guarded** with a
  `date --version` / probe and a BSD `date -j`/`-v` fallback. Correct.
- `base64 -d` appears only in the Linux branch of `lib/repo_fetch.sh`'s
  `_rf_base64_decode` (Darwin branch uses `-D`). Correct.
- `#!/bin/bash` hits in `tests/test_find_files.sh` are heredoc **test fixtures**,
  not the test's own shebang. The new shared `tests/lib/asserts.sh` (from t923_5)
  is portability-aware — it explicitly trims BSD `wc -l` leading-space padding.
- Python: no GNU-only shell-outs (`readlink -f`, `stat -c`, `sed -i`, etc.).

**Test suite — 162 PASS / 10 FAIL, zero macOS-attributable.** All 10 failures
are environmental and reproduce on Linux too:

- 2 (`run_all_python_tests.sh`, `test_crew_report.sh`) shell out via bare
  `python3` instead of `resolve_python` (`lib/python_resolve.sh`), so they miss
  the `~/.aitask/venv/` `yaml`/`textual` deps → `ModuleNotFoundError`. The venv
  itself is present and complete. → follow-up **t935**.
- 8 tmux/multi-session tests (`test_kill_agent_pane_smart.sh`,
  `test_multi_session_monitor.sh`, `test_multi_session_primitives.sh`,
  `test_tmux_control.sh`, `test_tmux_control_resilience.sh`,
  `test_tmux_exact_session_targeting.sh`, `test_tmux_run_parity.sh`,
  `test_tui_switcher_multi_session.sh`) aborted (exit 2) on their intentional
  "refuses to run while other tmux sessions are alive" self-protection guard (a
  live `aitasks` session was present). Not bugs. → follow-up **t936**.

**Follow-up tasks created:** t935 (use `resolve_python` in test harnesses, not
bare `python3`), t936 (let tmux tests run alongside a live session via isolated
socket), t937 (low-priority cleanup: switch the two fragile bare-`sed -i` +
`sed -i.bak`-fallback test setups in `test_fold_mark.sh:204` /
`test_fold_file_refs_union.sh:162` to `sed_inplace`). No production-code
portability bug was found — the prior audits (t186/t209/t211/t213/t658/t931/t932)
have absorbed the platform-specific patterns.

## Files Audited in t1397

Targeted macOS re-run of t1379's atomic-write conversion, on macOS 15.7.3 arm64
(Darwin 24.6.0, bash 5.3.9, BSD `stat`/`mktemp`/`readlink`). t1379 introduced
`.aitask-scripts/lib/atomic_write.sh`, whose BSD branches Linux CI never reaches.

**No BSD-vs-GNU divergence found — nothing to fix.** Every BSD path behaved as
the GNU path does:

- `ait_file_mode` — `stat -c '%a'` exits 1 on this box, so the `stat -f '%Lp'`
  fallback is genuinely the branch under test (not merely present). An existing
  `0640` file keeps `640` across a rewrite; a new file lands `0666 & ~umask`
  (`644` at `umask 022`) and `600` under `umask 0077` — the assertion that
  separates a derived mode from a hardcoded `0644`.
- `ait_atomic_tmp` — the BSD-safe `mktemp …XXXXXX` template form (placeholder
  last, no suffix) substitutes correctly; no literal-`XXXXXX` residue.
- `ait_atomic_resolve` — the hand-walked chain resolves a relative symlink, a
  3-hop chain, and the `/var` → `/private/var` prefix link; a symlink cycle exits
  1 with `too many symlink levels` instead of looping; the 40-hop bound holds (30
  hops resolve, 44 fail). `readlink -f` *is* available on macOS 15, but the manual
  walk is retained deliberately for macOS < 12.3 — see `readlink` above.

**Suites run — all green.** `test_atomic_write_sh.sh` 30/30,
`test_atomic_task_file_writes.sh` 62/62, plus the converted scripts' own suites:
`test_plan_verified.sh` 49/49, `test_plan_externalize.sh`,
`test_issue_import_contributor.sh`, `test_update_risk.sh` 21/21,
`test_create_silent_stdout.sh`, `test_projects_cmd.sh` 42/42.

**Sourcing caveat (not a code bug).** `lib/atomic_write.sh` computes its
default mode with `$(( 0666 & ~0$(umask) ))`, which is bash arithmetic. Sourced
from **zsh** — where a leading `0` is not octal unless `setopt octalzeroes` —
that expression yields `1210` instead of `644`, and the file lands with the wrong
permissions. Every framework caller is `#!/usr/bin/env bash`, so this is
unreachable in practice; it is recorded because an agent verifying by hand in an
interactive zsh will reproduce it and mistake it for a defect. Verify shell libs
with `bash -c '...'`, never a bare interactive shell.

## Files Audited in t1206

macOS run of `tests/test_install_create_data_dirs.sh`, on macOS 15.7.3 arm64
(Darwin 24.6.0, BSD `mkdir`/`readlink`). t1193 added `ensure_data_root` to
`install.sh`'s `create_data_dirs()`; t1201 ran the suite green on Linux but had
no macOS host, leaving one assumption open — **Test 3**, the negative control,
asserts that an *unguarded* `mkdir -p` through a dangling symlink exits
non-zero. If BSD behaved otherwise, Test 3 would pass vacuously and stop
attributing Test 2's success to the guard.

**No BSD-vs-GNU divergence found — nothing to fix.**

- **40/40 assertions pass, exit 0**, under both PATH bash 5.3.9 and macOS system
  bash 3.2.57. The 3.2 run was not required by the checklist; it closes t1201's
  other substitute-evidence assumption (no bash-4-only constructs in the test,
  `tests/lib/asserts.sh`, or `ensure_data_root`) by execution rather than by
  inspection.
- **Test 3 is non-vacuous.** Probed standalone rather than trusted green: BSD
  `mkdir -p` through a dangling symlink exits `1`, so Test 2 remains attributable
  to `ensure_data_root`.

**One divergence in the diagnostic, not the behaviour.** t1201 predicted BSD
`mkdir(1)`'s `build()` would go `stat()` → `ENOENT` → `mkdir()` → `EEXIST` and
report `File exists`, matching GNU. It reports **`No such file or directory`
(`ENOENT`)** instead. `assert_exit_nonzero_rc` checks only the status, so the
test is correct as written — but tightening it to match GNU's message would be
a macOS-only failure. See `mkdir -p` Through a Dangling Symlink above.
