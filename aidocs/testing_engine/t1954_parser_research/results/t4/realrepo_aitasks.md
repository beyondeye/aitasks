# Real-repository disagreement: aitasks

baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Input: `aitasks@7f1d0614a333`, the walked checkout at that commit.

Read-only walk of the repository's git-visible files (`git ls-files --cached --others --exclude-standard`) in the 8 research languages; nothing was executed or written there, and this report holds counts and paths only, never contents. Each candidate is compared with the baseline (the landed M2.2 lexers) as the reference; a disagreement is evidence to inspect, not a verdict on either side. Files over 2097152 bytes skipped: 0.

## Files per language

| lang | files | baseline uncertain |
|---|---|---|
| bash | 661 | 0 |
| python | 652 | 0 |
| go | 198 | 0 |
| kotlin | 0 | 0 |
| typescript | 0 | unsupported |
| tsx | 0 | unsupported |
| javascript | 2 | unsupported |
| java | 1 | unsupported |
| rust | 0 | unsupported |
| swift | 0 | unsupported |

## Candidate vs baseline

| subject | lang | files | unsupported | provider errors | comment-class differs (files / lines) | records differ (files) | uncertain: baseline only | uncertain: subject only |
|---|---|---|---|---|---|---|---|---|
| antlr | java | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| chroma | bash | 661 | 0 | 0 | 11 / 225 | 0 | 0 | 1 |
| chroma | python | 652 | 0 | 0 | 91 / 146 | 0 | 0 | 0 |
| chroma | go | 198 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| chroma | javascript | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| chroma | java | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| goscanner | go | 198 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| gotreesitter | bash | 661 | 0 | 0 | 0 / 0 | 0 | 0 | 19 |
| gotreesitter | python | 652 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| gotreesitter | go | 198 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| gotreesitter | javascript | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| gotreesitter | java | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pygments | bash | 661 | 0 | 0 | 11 / 225 | 0 | 0 | 1 |
| pygments | python | 652 | 0 | 0 | 91 / 146 | 0 | 0 | 0 |
| pygments | go | 198 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pygments | javascript | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pygments | java | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pytokenize | python | 652 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| shfmt | bash | 661 | 0 | 0 | 0 / 0 | 0 | 0 | 3 |
| textmate | bash | 661 | 0 | 0 | 12 / 127 | 0 | 0 | 0 |
| textmate | python | 652 | 0 | 0 | 3 / 11 | 0 | 0 | 0 |
| textmate | go | 198 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | javascript | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | java | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | bash | 661 | 0 | 0 | 0 / 0 | 0 | 0 | 16 |
| tscgo | python | 652 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | go | 198 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | javascript | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | java | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tsnative | javascript | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | bash | 661 | 0 | 0 | 0 / 0 | 0 | 0 | 16 |
| tswasm | python | 652 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | go | 198 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | javascript | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | java | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |

## Paths per disagreement kind

- chroma / bash / comment-class-differs:
  - `tests/test_agent_sessions_stamp.sh`
  - `tests/test_create_email_lock.sh`
  - `tests/test_ide_frozen_offer.sh`
  - `tests/test_ide_session_override.sh`
  - `tests/test_pick_own_scoped_commit.sh`
  - `tests/test_session_hook.sh`
  - `tests/test_shadow_rejected.sh`
  - `tests/test_shadow_spawn_config.sh`
  - `tests/test_shadow_spawn_learner.sh`
  - `tests/test_syncer_upgrade_handoff.sh`
  - `tests/test_testmap_shim.sh`
- chroma / bash / uncertain-chroma-only:
  - `tests/test_python_runner_exit_status.sh`
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
  - `tests/lib/validate_session_hook_fixtures.py`
  - `tests/test_agent_freeze.py`
  - `tests/test_agent_frozen_ops.py`
  - `tests/test_agent_keys.py`
  - `tests/test_agent_model_picker_narrow.py`
  - `tests/test_agent_reopen.py`
  - `tests/test_agent_restore.py`
  - `tests/test_ansi_utils.py`
  - `tests/test_board_bytrail_view.py`
  - `tests/test_board_detail_collapsible.py`
  - `tests/test_board_filter_row_layout.py`
  - `tests/test_board_fixture_harness.py`
- gotreesitter / bash / uncertain-gotreesitter-only:
  - `.aitask-scripts/aitask_artifact.sh`
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
  - `install.sh`
  - `tests/test_atomic_task_file_writes.sh`
  - `tests/test_atomic_write_sh.sh`
  - `tests/test_no_unscoped_task_commit.sh`
  - `tests/test_xdeps_blocking.sh`
- pygments / bash / comment-class-differs:
  - `tests/test_agent_sessions_stamp.sh`
  - `tests/test_create_email_lock.sh`
  - `tests/test_ide_frozen_offer.sh`
  - `tests/test_ide_session_override.sh`
  - `tests/test_pick_own_scoped_commit.sh`
  - `tests/test_session_hook.sh`
  - `tests/test_shadow_rejected.sh`
  - `tests/test_shadow_spawn_config.sh`
  - `tests/test_shadow_spawn_learner.sh`
  - `tests/test_syncer_upgrade_handoff.sh`
  - `tests/test_testmap_shim.sh`
- pygments / bash / uncertain-pygments-only:
  - `tests/test_python_runner_exit_status.sh`
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
  - `tests/lib/validate_session_hook_fixtures.py`
  - `tests/test_agent_freeze.py`
  - `tests/test_agent_frozen_ops.py`
  - `tests/test_agent_keys.py`
  - `tests/test_agent_model_picker_narrow.py`
  - `tests/test_agent_reopen.py`
  - `tests/test_agent_restore.py`
  - `tests/test_ansi_utils.py`
  - `tests/test_board_bytrail_view.py`
  - `tests/test_board_detail_collapsible.py`
  - `tests/test_board_filter_row_layout.py`
  - `tests/test_board_fixture_harness.py`
- shfmt / bash / uncertain-shfmt-only:
  - `.aitask-scripts/aitask_fold_mark.sh`
  - `.aitask-scripts/aitask_prune_retired_skills.sh`
  - `tests/test_xdeps_blocking.sh`
- textmate / bash / comment-class-differs:
  - `.aitask-scripts/aitask_pick_own.sh`
  - `.aitask-scripts/aitask_setup.sh`
  - `tests/test_gate_verifiers.sh`
  - `tests/test_install_create_data_dirs.sh`
  - `tests/test_install_upgrade_dirty_baseline.sh`
  - `tests/test_multi_session_minimonitor.sh`
  - `tests/test_multi_session_monitor.sh`
  - `tests/test_multi_session_primitives.sh`
  - `tests/test_task_data_writer_guard.sh`
  - `tests/test_tui_switcher_brainstorm_session.sh`
  - `tests/test_tui_switcher_footer_fit.sh`
  - `tests/test_tui_switcher_multi_session.sh`
- textmate / python / comment-class-differs:
  - `tests/test_collection_parity.py`
  - `tests/test_minimonitor_concern_smoke.py`
  - `tests/test_no_zero_collection.py`
- tscgo / bash / uncertain-tscgo-only:
  - `.aitask-scripts/aitask_add_model.sh`
  - `.aitask-scripts/aitask_artifact.sh`
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
  - `install.sh`
  - `tests/test_atomic_task_file_writes.sh`
  - `tests/test_atomic_write_sh.sh`
  - `tests/test_xdeps_blocking.sh`
- tswasm / bash / uncertain-tswasm-only:
  - `.aitask-scripts/aitask_add_model.sh`
  - `.aitask-scripts/aitask_artifact.sh`
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
  - `install.sh`
  - `tests/test_atomic_task_file_writes.sh`
  - `tests/test_atomic_write_sh.sh`
  - `tests/test_xdeps_blocking.sh`
