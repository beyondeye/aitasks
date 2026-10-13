# Real-repository disagreement: thinking_app

baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Read-only walk of the repository's git-visible files (`git ls-files --cached --others --exclude-standard`) in the 8 research languages; nothing was executed or written there, and this report holds counts and paths only, never contents. Each candidate is compared with the baseline (the landed M2.2 lexers) as the reference; a disagreement is evidence to inspect, not a verdict on either side. Files over 2097152 bytes skipped: 0.

## Files per language

| lang | files | baseline uncertain |
|---|---|---|
| bash | 244 | 0 |
| python | 277 | 0 |
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
| chroma | bash | 244 | 0 | 0 | 4 / 158 | 0 | 0 | 0 |
| chroma | python | 277 | 0 | 0 | 35 / 58 | 0 | 0 | 0 |
| chroma | kotlin | 784 | 0 | 0 | 0 / 0 | 0 | 0 | 80 |
| chroma | javascript | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| ktpsi | kotlin | 784 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pygments | bash | 244 | 0 | 0 | 4 / 158 | 0 | 0 | 0 |
| pygments | python | 277 | 0 | 0 | 35 / 58 | 0 | 0 | 0 |
| pygments | kotlin | 784 | 0 | 0 | 0 / 0 | 0 | 0 | 40 |
| pygments | javascript | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | bash | 244 | 0 | 0 | 3 / 17 | 0 | 0 | 0 |
| textmate | python | 277 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | kotlin | 784 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | javascript | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tsnative | javascript | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |

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
- textmate / bash / comment-class-differs:
  - `.aitask-scripts/aitask_pick_own.sh`
  - `.aitask-scripts/aitask_setup.sh`
  - `tools/verification/worker-peak-test.sh`
