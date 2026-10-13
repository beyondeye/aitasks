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
| gotreesitter | bash | 244 | 0 | 0 | 0 / 0 | 0 | 0 | 19 |
| gotreesitter | python | 277 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| gotreesitter | kotlin | 784 | 0 | 0 | 0 / 0 | 0 | 0 | 236 |
| gotreesitter | javascript | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | bash | 244 | 0 | 0 | 0 / 0 | 0 | 0 | 17 |
| tscgo | python | 277 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | kotlin | 784 | 0 | 0 | 0 / 0 | 0 | 0 | 29 |
| tscgo | javascript | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | bash | 244 | 0 | 0 | 0 / 0 | 0 | 0 | 17 |
| tswasm | python | 277 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | kotlin | 784 | 0 | 0 | 0 / 0 | 0 | 0 | 29 |
| tswasm | javascript | 1 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |

## Paths per disagreement kind

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
