# Real-repository disagreement: thinking_app

baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Input: `thinking_app@33b7fcd4923d`, the walked checkout at that commit.

Read-only walk of the repository's git-visible files (`git ls-files --cached --others --exclude-standard`) in the 8 research languages; nothing was executed or written there, and this report holds counts and paths only, never contents. Each candidate is compared with the baseline (the landed M2.2 lexers) as the reference; a disagreement is evidence to inspect, not a verdict on either side. Files over 2097152 bytes skipped: 0.

## Files per language

| lang | files | baseline uncertain |
|---|---|---|
| bash | 246 | 0 |
| python | 278 | 0 |
| go | 0 | 0 |
| kotlin | 784 | 0 |
| typescript | 0 | unsupported |
| tsx | 0 | unsupported |
| javascript | 1 | unsupported |
| java | 0 | unsupported |
| rust | 0 | unsupported |
| swift | 0 | unsupported |

## Candidate vs baseline

| subject | lang | files | unsupported | provider errors | comment-class differs (files / lines) | records differ (files) | uncertain: baseline only | uncertain: subject only |
|---|---|---|---|---|---|---|---|---|
| antlr | kotlin | 784 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| chroma | bash | 246 | 0 | 0 | 4 / 158 | 0 | 0 | 0 |
| chroma | python | 278 | 0 | 0 | 36 / 59 | 0 | 0 | 0 |
| chroma | kotlin | 784 | 0 | 0 | 0 / 0 | 0 | 0 | 80 |
| chroma | javascript | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| gotreesitter | bash | 246 | 0 | 0 | 0 / 0 | 0 | 0 | 19 |
| gotreesitter | python | 278 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| gotreesitter | kotlin | 784 | 0 | 0 | 0 / 0 | 0 | 0 | 236 |
| gotreesitter | javascript | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| ktpsi | kotlin | 784 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pygments | bash | 246 | 0 | 0 | 4 / 158 | 0 | 0 | 0 |
| pygments | python | 278 | 0 | 0 | 36 / 59 | 0 | 0 | 0 |
| pygments | kotlin | 784 | 0 | 0 | 0 / 0 | 0 | 0 | 40 |
| pygments | javascript | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pytokenize | python | 278 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| shfmt | bash | 246 | 0 | 0 | 0 / 0 | 0 | 0 | 2 |
| textmate | bash | 246 | 0 | 0 | 3 / 17 | 0 | 0 | 0 |
| textmate | python | 278 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | kotlin | 784 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | javascript | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | bash | 246 | 0 | 0 | 0 / 0 | 0 | 0 | 17 |
| tscgo | python | 278 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | kotlin | 784 | 0 | 0 | 0 / 0 | 0 | 0 | 29 |
| tscgo | javascript | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tsnative | javascript | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | bash | 246 | 0 | 0 | 0 / 0 | 0 | 0 | 17 |
| tswasm | python | 278 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | kotlin | 784 | 0 | 0 | 0 / 0 | 0 | 0 | 29 |
| tswasm | javascript | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |

## Paths per disagreement kind

- chroma / bash / comment-class-differs:
  - `tools/verification/emulator-allot-test.sh`
  - `tools/verification/screenshot-diff-viewer-test.sh`
  - `tools/verification/screenshot-review-test.sh`
  - `tools/verification/worker-peak-test.sh`
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
  - `tools/design/figma_font_sizes.py`
  - `tools/design/measure_candidate_pairing.py`
  - `tools/localization/check_copy_review_ledger.py`
  - `tools/localization/dev/test_strings_json.py`
  - `tools/localization/strings_json.py`
  - `tools/verification/depin-sites-check.py`
  - `tools/verification/lib/dex_java_time.py`
  - `tools/verification/suite-outcome-check.py`
- chroma / kotlin / uncertain-chroma-only:
  - `app/src/debug/java/com/softman/thinking/utils/BillingInterceptionProbeActivity.kt`
  - `app/src/main/java/com/softman/thinking/ForegroundAppService.kt`
  - `app/src/main/java/com/softman/thinking/MainCoordinator.kt`
  - `app/src/main/java/com/softman/thinking/enforcement/ForegroundAppDetector.kt`
  - `app/src/main/java/com/softman/thinking/enforcement/InputMethodResolver.kt`
  - `app/src/main/java/com/softman/thinking/network/NetworkConnectivityObserver.kt`
  - `app/src/main/java/com/softman/thinking/network/dto/KidByIdProgressDeserializer.kt`
  - `app/src/main/java/com/softman/thinking/repositories/KidsRepository.kt`
  - `app/src/main/java/com/softman/thinking/repositories/QuestionsRepository.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/BaseActivity.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/Buttons.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/PopUp.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/auth/login/LoginViewModel.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/auth/signin/SignInViewModel.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/blockingList/BlockingList.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/blockingList/BlockingListViewModel.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/dashboardKids/DashboardKidsScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/questions/QuestionViewModel.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/questions/QuestionsScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/setUpAccess/AccessibilityAccessScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/setUpAccess/DrawOverlaysAccessScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/setUpAccess/NotificationListenerAccessScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/setUpAccess/NotificationsAccessScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/setUpAccess/RunInBackgroundAccessScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/setUpAccess/SetUpScreenTimeScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/setUpAccess/UninstallRestrictionScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/setUpAccess/UsageAccessScreen.kt`
  - `app/src/main/java/com/softman/thinking/utils/BillingViewModel.kt`
  - `app/src/main/java/com/softman/thinking/utils/InstallReferrerFetcher.kt`
  - `app/src/test/java/com/softman/thinking/analytics/AnalyticsInstallerTest.kt`
  - `app/src/test/java/com/softman/thinking/analytics/AppEventCoverageMatrixTest.kt`
  - `app/src/test/java/com/softman/thinking/analytics/AuthEventsTest.kt`
  - `app/src/test/java/com/softman/thinking/analytics/OnboardingFunnelWalkTest.kt`
  - `app/src/test/java/com/softman/thinking/analytics/SubscriptionEventsTest.kt`
  - `app/src/test/java/com/softman/thinking/analytics/UserPropertySyncTest.kt`
  - `app/src/test/java/com/softman/thinking/enforcement/InputMethodResolverTest.kt`
  - `app/src/test/java/com/softman/thinking/localization/AppLocaleMigrationTest.kt`
  - `app/src/test/java/com/softman/thinking/localization/ArabicCatalogCompletenessFenceTest.kt`
  - `app/src/test/java/com/softman/thinking/localization/CatalogManifest.kt`
  - `app/src/test/java/com/softman/thinking/localization/ForcedLocaleSeamTest.kt`
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
  - `gradlew`
  - `tools/verification/aab-language-delivery-check-test.sh`
  - `tools/verification/heavy-run-lock-test.sh`
  - `tools/verification/lib/mem-facts.sh`
  - `tools/verification/screenshot-review-test.sh`
  - `tools/verification/worker-peak-test.sh`
- gotreesitter / kotlin / uncertain-gotreesitter-only:
  - `app/src/androidTest/java/com/softman/thinking/SmokeComposeTest.kt`
  - `app/src/main/java/com/softman/thinking/Screen.kt`
  - `app/src/main/java/com/softman/thinking/analytics/AnalyticsEvent.kt`
  - `app/src/main/java/com/softman/thinking/analytics/AnalyticsParam.kt`
  - `app/src/main/java/com/softman/thinking/analytics/AnalyticsUserProperty.kt`
  - `app/src/main/java/com/softman/thinking/data/Gender.kt`
  - `app/src/main/java/com/softman/thinking/enforcement/ForegroundAppMonitor.kt`
  - `app/src/main/java/com/softman/thinking/enforcement/ProtectionTier.kt`
  - `app/src/main/java/com/softman/thinking/navigation/TabDestination.kt`
  - `app/src/main/java/com/softman/thinking/network/ApiResult.kt`
  - `app/src/main/java/com/softman/thinking/onboarding/PermissionStep.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/AppRoot.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/Backgrounds.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/Buttons.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/ElasticTopGapScrollColumn.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/FitOrAdapt.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/HeroBand.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/KidListLoadError.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/PopUp.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/QrCode.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/SettingsRow.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/SteadyFont.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/Text.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/auth/login/LoginSubmitError.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/dashboardKids/DashboardKidsScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/deviceOwner/video/TutorialVideoScaffold.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/gradeRepair/GradeRepairViewModel.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/learningSettings/AddChildError.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/learningSettings/LearningSettingsClassNameScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/learningSettings/LearningSettingsClassScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/learningSettings/LearningSettingsSchoolScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/learningSettings/LearningSettingsStudySubjectsScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/learningSettings/LearningSettingsStudySubjectsViewModel.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/main/KidLoadError.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/main/MainScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/pinCode/ConfirmPinCodeScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/pinCode/CurrentPinCodeScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/questions/QuestionLoadError.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/questions/RewardTail.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/setUpAccess/PrimerTextColumn.kt`
- pygments / bash / comment-class-differs:
  - `tools/verification/emulator-allot-test.sh`
  - `tools/verification/screenshot-diff-viewer-test.sh`
  - `tools/verification/screenshot-review-test.sh`
  - `tools/verification/worker-peak-test.sh`
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
  - `tools/design/figma_font_sizes.py`
  - `tools/design/measure_candidate_pairing.py`
  - `tools/localization/check_copy_review_ledger.py`
  - `tools/localization/dev/test_strings_json.py`
  - `tools/localization/strings_json.py`
  - `tools/verification/depin-sites-check.py`
  - `tools/verification/lib/dex_java_time.py`
  - `tools/verification/suite-outcome-check.py`
- pygments / kotlin / uncertain-pygments-only:
  - `app/src/main/java/com/softman/thinking/data/rules/PasswordPolicy.kt`
  - `app/src/test/java/com/softman/thinking/BuildConfigBuildInfoTest.kt`
  - `app/src/test/java/com/softman/thinking/analytics/AnalyticsEventCatalogueTest.kt`
  - `app/src/test/java/com/softman/thinking/analytics/AnalyticsNameConstraintTest.kt`
  - `app/src/test/java/com/softman/thinking/analytics/AnalyticsSeamFenceTest.kt`
  - `app/src/test/java/com/softman/thinking/enforcement/DeviceManagementStatusTest.kt`
  - `app/src/test/java/com/softman/thinking/localization/ArabicAdvertisingGateRejectionProbeTest.kt`
  - `app/src/test/java/com/softman/thinking/localization/BundleLocaleDeliveryTest.kt`
  - `app/src/test/java/com/softman/thinking/localization/CatalogAdvertisingRules.kt`
  - `app/src/test/java/com/softman/thinking/localization/CatalogFormatSignatureTest.kt`
  - `app/src/test/java/com/softman/thinking/localization/CatalogManifest.kt`
  - `app/src/test/java/com/softman/thinking/localization/EnglishTypeScaleSpecificationTest.kt`
  - `app/src/test/java/com/softman/thinking/localization/ForcedLocaleSeamFenceTest.kt`
  - `app/src/test/java/com/softman/thinking/localization/LanguageSelectionOptionsDeriveFromTheConstantFenceTest.kt`
  - `app/src/test/java/com/softman/thinking/localization/NumericRenderingSeamFenceTest.kt`
  - `app/src/test/java/com/softman/thinking/localization/RussianCopyReviewSignOffTest.kt`
  - `app/src/test/java/com/softman/thinking/localization/RussianFigmaCrosswalkTest.kt`
  - `app/src/test/java/com/softman/thinking/localization/RussianGoldenMapTest.kt`
  - `app/src/test/java/com/softman/thinking/navigation/ScreenRouteRegistrationFenceTest.kt`
  - `app/src/test/java/com/softman/thinking/navigation/SetPasswordDeepLinkOwnershipFenceTest.kt`
  - `app/src/test/java/com/softman/thinking/network/SafeApiCallErrorKindTest.kt`
  - `app/src/test/java/com/softman/thinking/repositories/KidsRepositoryEmptyRosterTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/ArabicFixtureDataFenceTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/ArabicMatrixAudit.kt`
  - `app/src/test/java/com/softman/thinking/testing/FontFamilyDeclarationFenceTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/FontProvenanceTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/HeroHeadingFitTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/ImageSizingFence.kt`
  - `app/src/test/java/com/softman/thinking/testing/KidActionPillCallSiteCensusTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/LtrMatrixEnglishOnlyContract.kt`
  - `app/src/test/java/com/softman/thinking/testing/MatrixAuditRegistry.kt`
  - `app/src/test/java/com/softman/thinking/testing/OutlinedFieldParityTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/QualifierPolicyTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/RussianFixtureDataFenceTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/RussianMatrixAudit.kt`
  - `app/src/test/java/com/softman/thinking/testing/ScreenshotTestHarness.kt`
  - `app/src/test/java/com/softman/thinking/testing/SourceFence.kt`
  - `app/src/test/java/com/softman/thinking/testing/SourceFenceTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/T53Reconciliation.kt`
  - `app/src/test/java/com/softman/thinking/testing/WorktreeSymlinkIgnorePolicyTest.kt`
- shfmt / bash / uncertain-shfmt-only:
  - `.aitask-scripts/aitask_fold_mark.sh`
  - `.aitask-scripts/aitask_prune_retired_skills.sh`
- textmate / bash / comment-class-differs:
  - `.aitask-scripts/aitask_pick_own.sh`
  - `.aitask-scripts/aitask_setup.sh`
  - `tools/verification/worker-peak-test.sh`
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
  - `gradlew`
  - `tools/verification/aab-language-delivery-check-test.sh`
  - `tools/verification/heavy-run-lock-test.sh`
  - `tools/verification/lib/mem-facts.sh`
  - `tools/verification/screenshot-review-test.sh`
  - `tools/verification/worker-peak-test.sh`
- tscgo / kotlin / uncertain-tscgo-only:
  - `app/src/androidTest/java/com/softman/thinking/SmokeComposeTest.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/AppRoot.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/ElasticTopGapScrollColumn.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/FitOrAdapt.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/HeroBand.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/PopUp.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/QrCode.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/SettingsRow.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/SteadyFont.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/Text.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/dashboardKids/DashboardKidsScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/deviceOwner/video/TutorialVideoScaffold.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/questions/RewardTail.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/settings/ManageChildrenSettingsScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/settings/PurchaseSubscriptionScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/theme/Theme.kt`
  - `app/src/test/java/com/softman/thinking/analytics/ScreenViewTrackerTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/ArabicBodyLeadingTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/DepinDirectionCoverageTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/DirectionalRenderingTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/LabelAlignmentTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/LtrMatrixEnglishOnlyContract.kt`
  - `app/src/test/java/com/softman/thinking/testing/MediaPlayerLifecycleTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/OutlinedFieldErrorSemanticsTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/PinRowDirectionTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/QuestionsTextDirectionTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/ScreenFixtures.kt`
  - `app/src/test/java/com/softman/thinking/testing/ScreenshotTestHarness.kt`
  - `app/src/test/java/com/softman/thinking/testing/SettingsRowGeometryTest.kt`
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
  - `gradlew`
  - `tools/verification/aab-language-delivery-check-test.sh`
  - `tools/verification/heavy-run-lock-test.sh`
  - `tools/verification/lib/mem-facts.sh`
  - `tools/verification/screenshot-review-test.sh`
  - `tools/verification/worker-peak-test.sh`
- tswasm / kotlin / uncertain-tswasm-only:
  - `app/src/androidTest/java/com/softman/thinking/SmokeComposeTest.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/AppRoot.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/ElasticTopGapScrollColumn.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/FitOrAdapt.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/HeroBand.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/PopUp.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/QrCode.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/SettingsRow.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/SteadyFont.kt`
  - `app/src/main/java/com/softman/thinking/ui/components/Text.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/dashboardKids/DashboardKidsScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/deviceOwner/video/TutorialVideoScaffold.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/questions/RewardTail.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/settings/ManageChildrenSettingsScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/mvvm/settings/PurchaseSubscriptionScreen.kt`
  - `app/src/main/java/com/softman/thinking/ui/theme/Theme.kt`
  - `app/src/test/java/com/softman/thinking/analytics/ScreenViewTrackerTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/ArabicBodyLeadingTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/DepinDirectionCoverageTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/DirectionalRenderingTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/LabelAlignmentTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/LtrMatrixEnglishOnlyContract.kt`
  - `app/src/test/java/com/softman/thinking/testing/MediaPlayerLifecycleTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/OutlinedFieldErrorSemanticsTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/PinRowDirectionTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/QuestionsTextDirectionTest.kt`
  - `app/src/test/java/com/softman/thinking/testing/ScreenFixtures.kt`
  - `app/src/test/java/com/softman/thinking/testing/ScreenshotTestHarness.kt`
  - `app/src/test/java/com/softman/thinking/testing/SettingsRowGeometryTest.kt`
