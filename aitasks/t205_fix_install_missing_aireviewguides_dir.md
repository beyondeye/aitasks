---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [installer]
created_at: 2026-02-22 16:12
updated_at: 2026-02-22 16:12
---

Fix silent install failure caused by missing `aireviewguides/` directory creation in `install.sh`. The `create_data_dirs()` function didn't create the `aireviewguides/` directory, but `install_seed_reviewtypes()`, `install_seed_reviewlabels()`, and `install_seed_reviewenvironments()` tried to copy files into it before `install_seed_reviewguides()` had a chance to create it, causing a `cp` failure and silent exit under `set -e`.
