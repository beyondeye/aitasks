---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [installation, install_scripts]
created_at: 2026-04-23 13:02
updated_at: 2026-04-23 13:02
---

Follow-up to t624: install.sh never installs seed/project_config.yaml into aitasks/metadata/. Every other seed file has an install_seed_* function but project_config.yaml does not, and install.sh deletes seed/ at the end, so ait setup's ensure_project_config_defaults bails silently (seed missing) and setup_git_tui / setup_tmux_default_session both report 'No project_config.yaml found'. Fix adds install_seed_project_config() to install.sh and hardens ensure_project_config_defaults to create target from scratch or warn loudly when both are missing.
