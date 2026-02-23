---
priority: high
effort: medium
depends: []
issue_type: bug
status: Done
labels: [macos, bash_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-22 22:32
updated_at: 2026-02-22 22:51
completed_at: 2026-02-22 22:51
---

`aitask_stats.sh` has multiple macOS incompatibilities beyond the sed issues fixed in t209:

## Issue 1: `#!/bin/bash` shebang uses macOS system bash 3.2

The script uses `#!/bin/bash` which on macOS resolves to `/usr/bin/bash` (version 3.2). The script requires bash 4.0+ features (`declare -A` for associative arrays, `${var^}` for case modification). Brew-installed bash 5.x is at `/opt/homebrew/bin/bash` (Apple Silicon) or `/usr/local/bin/bash` (Intel).

**Fix:** Change shebang to `#!/usr/bin/env bash` so it picks up the brew-installed bash from PATH. Also audit all other scripts in `aiscripts/` for the same issue — any script using `#!/bin/bash` instead of `#!/usr/bin/env bash` will have the same problem on macOS.

**Key files:**
- `aiscripts/aitask_stats.sh` — line 1: `#!/bin/bash`
- All scripts in `aiscripts/` should be checked

## Issue 2: `date -d` is GNU coreutils, not available on macOS

The script uses `date -d` (GNU date) in ~15 places for date arithmetic. macOS BSD `date` does not support `-d`. The `ait setup` script already installs `coreutils` via brew (which provides `gdate`), but `aitask_stats.sh` calls `date` not `gdate`.

**Fix options:**
1. Create a portable `date_compat()` wrapper in `terminal_compat.sh` that uses `gdate` on macOS and `date` on Linux
2. Or replace all `date -d` calls with a portable alternative

**Affected lines in `aitask_stats.sh`:** ~15 instances of `date -d`, used in:
- `get_week_start()` — line 162
- `get_week_offset()` — lines 174-175, 182
- `print_daily_breakdown()` — line 467-468
- `print_dow_stats()` — lines 491-492, 506
- `print_label_dow_stats()` — lines 579-580

**Reference:** See `aidocs/sed_macos_issues.md` for the pattern used to document and fix the sed incompatibilities in t209. A similar `aidocs/date_macos_issues.md` could be created.
