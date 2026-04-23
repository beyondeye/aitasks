---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [installation, install_scripts]
created_at: 2026-04-23 13:08
updated_at: 2026-04-23 13:08
---

Follow-up to t624/t628: commit_framework_files() uses printf | head -20 | sed to list untracked files. When check_paths yields >20 files (now common — user reported 326), head closes the pipe after 20 lines, printf gets SIGPIPE, set -o pipefail + set -e kill the script mid-list. User reports ait setup terminates silently after printing exactly 20 files — no [Y/n] prompt, no commit. Fix: replace the three 'printf | head -N | sed' patterns in commit_framework_files() with bash index-bounded for loops (and awk for string-input cases) — neither creates a pipe that can send SIGPIPE.
