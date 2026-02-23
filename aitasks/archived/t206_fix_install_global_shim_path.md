---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [install_scripts]
created_at: 2026-02-22 16:44
updated_at: 2026-02-22 16:44
---

Fix `ait` command not found after curl-pipe installation on macOS. The installer now installs the global shim and adds `~/.local/bin` to the user's shell profile during `install.sh`, eliminating the chicken-and-egg problem where `ait setup` was needed to install the shim but `ait` wasn't in PATH yet.
