# Real-repository disagreement: aitasks_mobile

baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Read-only walk of the repository's git-visible files (`git ls-files --cached --others --exclude-standard`) in the 8 research languages; nothing was executed or written there, and this report holds counts and paths only, never contents. Each candidate is compared with the baseline (the landed M2.2 lexers) as the reference; a disagreement is evidence to inspect, not a verdict on either side. Files over 2097152 bytes skipped: 0.

## Files per language

| lang | files | baseline uncertain |
|---|---|---|
| bash | 141 | 0 |
| python | 148 | 0 |
| go | 0 | 0 |
| kotlin | 260 | 0 |
| typescript | 0 | unsupported |
| tsx | 0 | unsupported |
| javascript | 0 | unsupported |
| java | 0 | unsupported |
| rust | 0 | unsupported |
| swift | 2 | unsupported |

## Candidate vs baseline

| subject | lang | files | unsupported | provider errors | comment-class differs (files / lines) | records differ (files) | uncertain: baseline only | uncertain: subject only |
|---|---|---|---|---|---|---|---|---|
| gotreesitter | bash | 141 | 0 | 0 | 0 / 0 | 0 | 0 | 7 |
| gotreesitter | python | 148 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| gotreesitter | kotlin | 260 | 0 | 0 | 0 / 0 | 0 | 0 | 73 |
| gotreesitter | swift | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | bash | 141 | 0 | 0 | 0 / 0 | 0 | 0 | 3 |
| tscgo | python | 148 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | kotlin | 260 | 0 | 0 | 0 / 0 | 0 | 0 | 25 |
| tscgo | swift | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | bash | 141 | 0 | 0 | 0 / 0 | 0 | 0 | 3 |
| tswasm | python | 148 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | kotlin | 260 | 0 | 0 | 0 / 0 | 0 | 0 | 25 |
| tswasm | swift | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |

## Paths per disagreement kind

- gotreesitter / bash / uncertain-gotreesitter-only:
  - `.aitask-scripts/aitask_attach.sh`
  - `.aitask-scripts/aitask_contribution_review.sh`
  - `.aitask-scripts/aitask_revert_analyze.sh`
  - `.aitask-scripts/aitask_review_commits.sh`
  - `.aitask-scripts/aitask_stats_legacy.sh`
  - `.aitask-scripts/lib/task_utils.sh`
  - `gradlew`
- gotreesitter / kotlin / uncertain-gotreesitter-only:
  - `dbaccess/src/androidMain/kotlin/com/beyondeye/aitmobile/dbaccess/Database.android.kt`
  - `dbaccess/src/commonMain/kotlin/com/beyondeye/aitmobile/dbaccess/AitDatabase.kt`
  - `dbaccess/src/iosMain/kotlin/com/beyondeye/aitmobile/dbaccess/Database.ios.kt`
  - `domain/src/commonMain/kotlin/com/beyondeye/aitmobile/applink/QrUrl.kt`
  - `domain/src/commonMain/kotlin/com/beyondeye/aitmobile/applink/monitor/KtorMonitorStreamClient.kt`
  - `domain/src/commonMain/kotlin/com/beyondeye/aitmobile/applink/monitor/MonitorSessionMediator.kt`
  - `domain/src/commonMain/kotlin/com/beyondeye/aitmobile/applink/monitor/PaneRenderStateMediator.kt`
  - `domain/src/commonMain/kotlin/com/beyondeye/aitmobile/applink/wire/ControlFrames.kt`
  - `domain/src/commonMain/kotlin/com/beyondeye/aitmobile/applink/wire/MsgReader.kt`
  - `domain/src/commonMain/kotlin/com/beyondeye/aitmobile/domain/connectivity/ConnectivityMonitor.kt`
  - `domain/src/commonTest/kotlin/com/beyondeye/aitmobile/applink/monitor/EndpointRacerTest.kt`
  - `domain/src/commonTest/kotlin/com/beyondeye/aitmobile/applink/monitor/MonitorSessionMediatorTest.kt`
  - `domain/src/commonTest/kotlin/com/beyondeye/aitmobile/domain/connections/Fakes.kt`
  - `domain/src/commonTest/kotlin/com/beyondeye/aitmobile/domain/panes/Fakes.kt`
  - `domain/src/iosMain/kotlin/com/beyondeye/aitmobile/applink/HttpClientFactory.ios.kt`
  - `libs/src/androidMain/kotlin/org/ncgroup/kscan/BarcodeAnalyzer.kt`
  - `libs/src/androidMain/kotlin/org/ncgroup/kscan/ScannerView.android.kt`
  - `libs/src/commonMain/kotlin/org/ncgroup/kscan/BarcodeFormat.kt`
  - `libs/src/commonMain/kotlin/org/ncgroup/kscan/ImageScanner.kt`
  - `libs/src/commonMain/kotlin/org/ncgroup/kscan/ScannerBarcodeFrame.kt`
  - `libs/src/commonMain/kotlin/org/ncgroup/kscan/ScannerHeader.kt`
  - `libs/src/commonMain/kotlin/org/ncgroup/kscan/ScannerView.kt`
  - `libs/src/commonMain/kotlin/org/ncgroup/kscan/ScannerViewContent.kt`
  - `libs/src/commonMain/kotlin/org/ncgroup/kscan/ScannerZoomAdjuster.kt`
  - `libs/src/iosMain/kotlin/org/ncgroup/kscan/ImageScanner.ios.kt`
  - `libs/src/iosMain/kotlin/org/ncgroup/kscan/ScannerView.ios.kt`
  - `shared/src/androidMain/kotlin/com/beyondeye/aitmobile/connections/CameraPermissionGate.android.kt`
  - `shared/src/androidMain/kotlin/com/beyondeye/aitmobile/di/DataPlatform.android.kt`
  - `shared/src/commonMain/kotlin/com/beyondeye/aitmobile/connections/CameraPermissionGate.kt`
  - `shared/src/commonMain/kotlin/com/beyondeye/aitmobile/connections/ConnectionRow.kt`
  - `shared/src/commonMain/kotlin/com/beyondeye/aitmobile/monitor/MonitorScreenModel.kt`
  - `shared/src/commonMain/kotlin/com/beyondeye/aitmobile/monitor/PaneContentViewer.kt`
  - `shared/src/commonMain/kotlin/com/beyondeye/aitmobile/monitor/PaneListPanel.kt`
  - `shared/src/commonMain/kotlin/com/beyondeye/aitmobile/monitor/TaskDetailSheet.kt`
  - `shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/MonitorScreenModelReplayTest.kt`
  - `shared/src/iosMain/kotlin/com/beyondeye/aitmobile/connections/CameraPermissionGate.ios.kt`
  - `shared/src/iosMain/kotlin/com/beyondeye/aitmobile/di/DataPlatform.ios.kt`
  - `voyager/src/androidMain/kotlin/cafe/adriel/voyager/androidx/AndroidScreenLifecycleOwner.kt`
  - `voyager/src/androidMain/kotlin/cafe/adriel/voyager/core/lifecycle/ConfigurationChecker.kt`
  - `voyager/src/androidMain/kotlin/com/beyondeye/kbloc/compose/navigator/AndroidRootNavigator.kt`
- tscgo / bash / uncertain-tscgo-only:
  - `.aitask-scripts/aitask_add_model.sh`
  - `.aitask-scripts/lib/task_utils.sh`
  - `gradlew`
- tscgo / kotlin / uncertain-tscgo-only:
  - `libs/src/commonMain/kotlin/org/ncgroup/kscan/ScannerViewContent.kt`
  - `shared/src/androidMain/kotlin/com/beyondeye/aitmobile/connections/CameraPermissionGate.android.kt`
  - `shared/src/commonMain/kotlin/com/beyondeye/aitmobile/connections/CameraPermissionGate.kt`
  - `shared/src/iosMain/kotlin/com/beyondeye/aitmobile/connections/CameraPermissionGate.ios.kt`
  - `voyager/src/androidMain/kotlin/cafe/adriel/voyager/androidx/AndroidScreenLifecycleOwner.kt`
  - `voyager/src/androidMain/kotlin/com/beyondeye/kbloc/compose/navigator/AndroidRootNavigator.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/core/lifecycle/ScreenLifecycleOwner.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/core/lifecycle/multipleScreenLifecycleOwnerUtil.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/core/model/NavigatorScreenModel.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/core/model/ScreenModel.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/core/model/ScreenModelStore.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/navigator/Navigator.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/navigator/bottomSheet3/BottomSheetNavigator.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/navigator/tab/TabNavigator.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/transitions/CrossfadeTransition.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocBuilder.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocConsumer.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocListener.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocProvider.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocSelector.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/MultiBlocProvider.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/internal/BlocBindings.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/internal/BlocStore.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/navigator/init_generic_store_owners.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/core/bloc_base.kt`
- tswasm / bash / uncertain-tswasm-only:
  - `.aitask-scripts/aitask_add_model.sh`
  - `.aitask-scripts/lib/task_utils.sh`
  - `gradlew`
- tswasm / kotlin / uncertain-tswasm-only:
  - `libs/src/commonMain/kotlin/org/ncgroup/kscan/ScannerViewContent.kt`
  - `shared/src/androidMain/kotlin/com/beyondeye/aitmobile/connections/CameraPermissionGate.android.kt`
  - `shared/src/commonMain/kotlin/com/beyondeye/aitmobile/connections/CameraPermissionGate.kt`
  - `shared/src/iosMain/kotlin/com/beyondeye/aitmobile/connections/CameraPermissionGate.ios.kt`
  - `voyager/src/androidMain/kotlin/cafe/adriel/voyager/androidx/AndroidScreenLifecycleOwner.kt`
  - `voyager/src/androidMain/kotlin/com/beyondeye/kbloc/compose/navigator/AndroidRootNavigator.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/core/lifecycle/ScreenLifecycleOwner.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/core/lifecycle/multipleScreenLifecycleOwnerUtil.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/core/model/NavigatorScreenModel.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/core/model/ScreenModel.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/core/model/ScreenModelStore.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/navigator/Navigator.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/navigator/bottomSheet3/BottomSheetNavigator.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/navigator/tab/TabNavigator.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/transitions/CrossfadeTransition.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocBuilder.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocConsumer.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocListener.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocProvider.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocSelector.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/MultiBlocProvider.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/internal/BlocBindings.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/internal/BlocStore.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/navigator/init_generic_store_owners.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/core/bloc_base.kt`
