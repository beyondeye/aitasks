# Real-repository disagreement: thinking_backend

baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Input: `thinking_backend@e9a371524f4b`, the walked checkout at that commit.

Read-only walk of the repository's git-visible files (`git ls-files --cached --others --exclude-standard`) in the 8 research languages; nothing was executed or written there, and this report holds counts and paths only, never contents. Each candidate is compared with the baseline (the landed M2.2 lexers) as the reference; a disagreement is evidence to inspect, not a verdict on either side. Files over 2097152 bytes skipped: 0.

## Files per language

| lang | files | baseline uncertain |
|---|---|---|
| bash | 269 | 0 |
| python | 322 | 0 |
| go | 0 | 0 |
| kotlin | 0 | 0 |
| typescript | 0 | unsupported |
| tsx | 0 | unsupported |
| javascript | 0 | unsupported |
| java | 0 | unsupported |
| rust | 0 | unsupported |
| swift | 0 | unsupported |

## Candidate vs baseline

| subject | lang | files | unsupported | provider errors | comment-class differs (files / lines) | records differ (files) | uncertain: baseline only | uncertain: subject only |
|---|---|---|---|---|---|---|---|---|
| chroma | bash | 269 | 0 | 0 | 2 / 33 | 0 | 0 | 1 |
| chroma | python | 322 | 0 | 0 | 41 / 74 | 0 | 0 | 0 |
| gotreesitter | bash | 269 | 0 | 0 | 0 / 0 | 0 | 0 | 20 |
| gotreesitter | python | 322 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pygments | bash | 269 | 0 | 0 | 2 / 33 | 0 | 0 | 1 |
| pygments | python | 322 | 0 | 0 | 41 / 74 | 0 | 0 | 0 |
| pytokenize | python | 322 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| shfmt | bash | 269 | 0 | 0 | 1 / 1 | 0 | 0 | 2 |
| textmate | bash | 269 | 0 | 0 | 3 / 15 | 0 | 0 | 0 |
| textmate | python | 322 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | bash | 269 | 0 | 0 | 0 / 0 | 0 | 0 | 16 |
| tscgo | python | 322 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | bash | 269 | 0 | 0 | 0 / 0 | 0 | 0 | 16 |
| tswasm | python | 322 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |

## Paths per disagreement kind

- chroma / bash / comment-class-differs:
  - `scripts/tests/test_check_origin_certificate.sh`
  - `scripts/tests/test_deploy.sh`
- chroma / bash / uncertain-chroma-only:
  - `scripts/tests/test_issue_certificates.sh`
- chroma / python / comment-class-differs:
  - `.aitask-scripts/aitask_model_supersession.py`
  - `.aitask-scripts/applink/headless.py`
  - `.aitask-scripts/applink/pairing.py`
  - `.aitask-scripts/board/board_task_manager.py`
  - `.aitask-scripts/board/board_trail_screen.py`
  - `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `.aitask-scripts/brainstorm/brainstorm_session.py`
  - `.aitask-scripts/chatlink/config.py`
  - `.aitask-scripts/chatlink/relay.py`
  - `.aitask-scripts/chatlink/sessions_store.py`
  - `.aitask-scripts/lib/agent_freeze.py`
  - `.aitask-scripts/lib/agent_launch_utils.py`
  - `.aitask-scripts/lib/agent_marks.py`
  - `.aitask-scripts/lib/agent_restore.py`
  - `.aitask-scripts/lib/agent_sessions.py`
  - `.aitask-scripts/lib/board_columns.py`
  - `.aitask-scripts/lib/config_utils.py`
  - `.aitask-scripts/lib/cross_repo_settings.py`
  - `.aitask-scripts/lib/gate_ledger.py`
  - `.aitask-scripts/lib/gate_registry_sync.py`
  - `.aitask-scripts/lib/ledger_block.py`
  - `.aitask-scripts/lib/shortcut_labels.py`
  - `.aitask-scripts/lib/trail_gather.py`
  - `.aitask-scripts/lib/work_report_gather.py`
  - `.aitask-scripts/monitor/minimonitor_app.py`
  - `.aitask-scripts/monitor/monitor_app.py`
  - `.aitask-scripts/monitor/monitor_core.py`
  - `.aitask-scripts/syncer/syncer_app.py`
  - `app/api/resources.py`
  - `db_target.py`
  - `env_contract.py`
  - `scripts/prod/compare_tiers.py`
  - `scripts/prod/http_probe.py`
  - `scripts/prod/test_mirror_mapping.py`
  - `scripts/prod/validate_prod.py`
  - `scripts/prod/verify_indirection.py`
  - `scripts/prod/verify_restore.py`
  - `scripts/server/lib/firewall_rules.py`
  - `scripts/tests/test_app_env_normalization.py`
  - `scripts/tests/test_db_target.py`
- gotreesitter / bash / uncertain-gotreesitter-only:
  - `.aitask-scripts/aitask_attach.sh`
  - `.aitask-scripts/aitask_contribution_review.sh`
  - `.aitask-scripts/aitask_create.sh`
  - `.aitask-scripts/aitask_prune_retired_skills.sh`
  - `.aitask-scripts/aitask_revert_analyze.sh`
  - `.aitask-scripts/aitask_review_commits.sh`
  - `.aitask-scripts/aitask_shadow_rejected.sh`
  - `.aitask-scripts/aitask_stats_legacy.sh`
  - `.aitask-scripts/lib/atomic_write.sh`
  - `.aitask-scripts/lib/github_release.sh`
  - `.aitask-scripts/lib/ledger_block.sh`
  - `.aitask-scripts/lib/task_utils.sh`
  - `.aitask-scripts/lib/yaml_utils.sh`
  - `scripts/prod/migrate_legacy_db.sh`
  - `scripts/prod/mirror_legacy_media.sh`
  - `scripts/prod/place_media_mirror.sh`
  - `scripts/server/provision_hetzner.sh`
  - `scripts/server/setup_backup_remote.sh`
  - `scripts/tests/test_caddy_indirection.sh`
  - `scripts/tests/test_restore_rehearsal.sh`
- pygments / bash / comment-class-differs:
  - `scripts/tests/test_check_origin_certificate.sh`
  - `scripts/tests/test_deploy.sh`
- pygments / bash / uncertain-pygments-only:
  - `scripts/tests/test_issue_certificates.sh`
- pygments / python / comment-class-differs:
  - `.aitask-scripts/aitask_model_supersession.py`
  - `.aitask-scripts/applink/headless.py`
  - `.aitask-scripts/applink/pairing.py`
  - `.aitask-scripts/board/board_task_manager.py`
  - `.aitask-scripts/board/board_trail_screen.py`
  - `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `.aitask-scripts/brainstorm/brainstorm_session.py`
  - `.aitask-scripts/chatlink/config.py`
  - `.aitask-scripts/chatlink/relay.py`
  - `.aitask-scripts/chatlink/sessions_store.py`
  - `.aitask-scripts/lib/agent_freeze.py`
  - `.aitask-scripts/lib/agent_launch_utils.py`
  - `.aitask-scripts/lib/agent_marks.py`
  - `.aitask-scripts/lib/agent_restore.py`
  - `.aitask-scripts/lib/agent_sessions.py`
  - `.aitask-scripts/lib/board_columns.py`
  - `.aitask-scripts/lib/config_utils.py`
  - `.aitask-scripts/lib/cross_repo_settings.py`
  - `.aitask-scripts/lib/gate_ledger.py`
  - `.aitask-scripts/lib/gate_registry_sync.py`
  - `.aitask-scripts/lib/ledger_block.py`
  - `.aitask-scripts/lib/shortcut_labels.py`
  - `.aitask-scripts/lib/trail_gather.py`
  - `.aitask-scripts/lib/work_report_gather.py`
  - `.aitask-scripts/monitor/minimonitor_app.py`
  - `.aitask-scripts/monitor/monitor_app.py`
  - `.aitask-scripts/monitor/monitor_core.py`
  - `.aitask-scripts/syncer/syncer_app.py`
  - `app/api/resources.py`
  - `db_target.py`
  - `env_contract.py`
  - `scripts/prod/compare_tiers.py`
  - `scripts/prod/http_probe.py`
  - `scripts/prod/test_mirror_mapping.py`
  - `scripts/prod/validate_prod.py`
  - `scripts/prod/verify_indirection.py`
  - `scripts/prod/verify_restore.py`
  - `scripts/server/lib/firewall_rules.py`
  - `scripts/tests/test_app_env_normalization.py`
  - `scripts/tests/test_db_target.py`
- shfmt / bash / comment-class-differs:
  - `scripts/tests/test_deploy.sh`
- shfmt / bash / uncertain-shfmt-only:
  - `.aitask-scripts/aitask_fold_mark.sh`
  - `.aitask-scripts/aitask_prune_retired_skills.sh`
- textmate / bash / comment-class-differs:
  - `.aitask-scripts/aitask_pick_own.sh`
  - `.aitask-scripts/aitask_setup.sh`
  - `scripts/tests/test_deploy.sh`
- tscgo / bash / uncertain-tscgo-only:
  - `.aitask-scripts/aitask_add_model.sh`
  - `.aitask-scripts/aitask_create.sh`
  - `.aitask-scripts/aitask_fold_mark.sh`
  - `.aitask-scripts/aitask_prune_retired_skills.sh`
  - `.aitask-scripts/aitask_setup.sh`
  - `.aitask-scripts/aitask_shadow_rejected.sh`
  - `.aitask-scripts/lib/atomic_write.sh`
  - `.aitask-scripts/lib/github_release.sh`
  - `.aitask-scripts/lib/ledger_block.sh`
  - `.aitask-scripts/lib/task_utils.sh`
  - `.aitask-scripts/lib/yaml_utils.sh`
  - `scripts/prod/migrate_legacy_db.sh`
  - `scripts/prod/mirror_legacy_media.sh`
  - `scripts/server/check_origin_certificate.sh`
  - `scripts/tests/test_caddy_indirection.sh`
  - `scripts/tests/test_restore_rehearsal.sh`
- tswasm / bash / uncertain-tswasm-only:
  - `.aitask-scripts/aitask_add_model.sh`
  - `.aitask-scripts/aitask_create.sh`
  - `.aitask-scripts/aitask_fold_mark.sh`
  - `.aitask-scripts/aitask_prune_retired_skills.sh`
  - `.aitask-scripts/aitask_setup.sh`
  - `.aitask-scripts/aitask_shadow_rejected.sh`
  - `.aitask-scripts/lib/atomic_write.sh`
  - `.aitask-scripts/lib/github_release.sh`
  - `.aitask-scripts/lib/ledger_block.sh`
  - `.aitask-scripts/lib/task_utils.sh`
  - `.aitask-scripts/lib/yaml_utils.sh`
  - `scripts/prod/migrate_legacy_db.sh`
  - `scripts/prod/mirror_legacy_media.sh`
  - `scripts/server/check_origin_certificate.sh`
  - `scripts/tests/test_caddy_indirection.sh`
  - `scripts/tests/test_restore_rehearsal.sh`
