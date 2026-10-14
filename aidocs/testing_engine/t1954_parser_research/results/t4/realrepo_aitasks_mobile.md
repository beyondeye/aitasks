# Real-repository disagreement: aitasks_mobile

baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Input: `aitasks_mobile@75f4543fb70e`, the walked checkout at that commit.

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
| antlr | kotlin | 260 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| chroma | bash | 141 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| chroma | python | 148 | 0 | 0 | 9 / 9 | 0 | 0 | 0 |
| chroma | kotlin | 260 | 0 | 0 | 0 / 0 | 0 | 0 | 25 |
| chroma | swift | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| gotreesitter | bash | 141 | 0 | 0 | 0 / 0 | 0 | 0 | 7 |
| gotreesitter | python | 148 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| gotreesitter | kotlin | 260 | 0 | 0 | 0 / 0 | 0 | 0 | 73 |
| gotreesitter | swift | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| ktpsi | kotlin | 260 | 0 | 0 | 0 / 0 | 0 | 0 | 8 |
| pygments | bash | 141 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pygments | python | 148 | 0 | 0 | 9 / 9 | 0 | 0 | 0 |
| pygments | kotlin | 260 | 0 | 0 | 2 / 8 | 0 | 0 | 17 |
| pygments | swift | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pytokenize | python | 148 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| shfmt | bash | 141 | 0 | 0 | 0 / 0 | 0 | 0 | 1 |
| textmate | bash | 141 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | python | 148 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | kotlin | 260 | 0 | 0 | 2 / 8 | 0 | 0 | 0 |
| textmate | swift | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | bash | 141 | 0 | 0 | 0 / 0 | 0 | 0 | 3 |
| tscgo | python | 148 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | kotlin | 260 | 0 | 0 | 0 / 0 | 0 | 0 | 25 |
| tscgo | swift | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | bash | 141 | 0 | 0 | 0 / 0 | 0 | 0 | 3 |
| tswasm | python | 148 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | kotlin | 260 | 0 | 0 | 0 / 0 | 0 | 0 | 25 |
| tswasm | swift | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |

## Paths per disagreement kind

- chroma / python / comment-class-differs:
  - `.aitask-scripts/applink/headless.py`
  - `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `.aitask-scripts/brainstorm/brainstorm_session.py`
  - `.aitask-scripts/lib/config_utils.py`
  - `.aitask-scripts/lib/gate_ledger.py`
  - `.aitask-scripts/lib/shortcut_labels.py`
  - `.aitask-scripts/monitor/minimonitor_app.py`
  - `.aitask-scripts/monitor/monitor_app.py`
  - `.aitask-scripts/monitor/monitor_core.py`
- chroma / kotlin / uncertain-chroma-only:
  - `domain/src/androidMain/kotlin/com/beyondeye/aitmobile/applink/HttpClientFactory.android.kt`
  - `domain/src/androidMain/kotlin/com/beyondeye/aitmobile/domain/connectivity/ConnectivityMonitorAndroid.kt`
  - `domain/src/commonMain/kotlin/com/beyondeye/aitmobile/applink/QrUrl.kt`
  - `domain/src/commonMain/kotlin/com/beyondeye/aitmobile/applink/monitor/EndpointRacer.kt`
  - `domain/src/commonTest/kotlin/com/beyondeye/aitmobile/applink/monitor/EndpointRacerTest.kt`
  - `domain/src/commonTest/kotlin/com/beyondeye/aitmobile/applink/monitor/MonitorSessionMediatorTest.kt`
  - `domain/src/commonTest/kotlin/com/beyondeye/aitmobile/applink/monitor/MonitorSessionReconnectTest.kt`
  - `domain/src/commonTest/kotlin/com/beyondeye/aitmobile/domain/connections/ConnectionMediatorTest.kt`
  - `domain/src/commonTest/kotlin/com/beyondeye/aitmobile/domain/connections/EndpointRepoTest.kt`
  - `libs/src/commonMain/kotlin/org/ncgroup/kscan/Barcode.kt`
  - `libs/src/commonMain/kotlin/org/ncgroup/kscan/BarcodeFormat.kt`
  - `libs/src/commonMain/kotlin/org/ncgroup/kscan/ImageScanner.kt`
  - `shared/src/commonMain/kotlin/com/beyondeye/aitmobile/monitor/MonitorScreen.kt`
  - `voyager/src/androidMain/kotlin/cafe/adriel/voyager/androidx/AndroidScreenLifecycleOwner.kt`
  - `voyager/src/androidMain/kotlin/com/beyondeye/kbloc/compose/navigator/AndroidRootNavigator.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/navigator/Navigator.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/transitions/ScaleTransition.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/transitions/SlideTransition.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocProvider.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/MultiBlocProvider.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/internal/LocalBlocStoreOwner.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/navigator/init_generic_store_owners.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/reselect/reselect.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/core/Change.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/core/Transition.kt`
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
- ktpsi / kotlin / uncertain-ktpsi-only:
  - `androidApp/build.gradle.kts`
  - `build.gradle.kts`
  - `dbaccess/build.gradle.kts`
  - `domain/build.gradle.kts`
  - `libs/build.gradle.kts`
  - `settings.gradle.kts`
  - `shared/build.gradle.kts`
  - `voyager/build.gradle.kts`
- pygments / python / comment-class-differs:
  - `.aitask-scripts/applink/headless.py`
  - `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `.aitask-scripts/brainstorm/brainstorm_session.py`
  - `.aitask-scripts/lib/config_utils.py`
  - `.aitask-scripts/lib/gate_ledger.py`
  - `.aitask-scripts/lib/shortcut_labels.py`
  - `.aitask-scripts/monitor/minimonitor_app.py`
  - `.aitask-scripts/monitor/monitor_app.py`
  - `.aitask-scripts/monitor/monitor_core.py`
- pygments / kotlin / comment-class-differs:
  - `voyager/src/androidMain/kotlin/com/beyondeye/kbloc/compose/navigator/AndroidRootNavigator.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/navigator/init_generic_store_owners.kt`
- pygments / kotlin / uncertain-pygments-only:
  - `libs/src/commonMain/kotlin/org/ncgroup/kscan/Barcode.kt`
  - `libs/src/commonMain/kotlin/org/ncgroup/kscan/BarcodeFormat.kt`
  - `libs/src/commonMain/kotlin/org/ncgroup/kscan/ImageScanner.kt`
  - `libs/src/iosMain/kotlin/org/ncgroup/kscan/CameraViewController.kt`
  - `voyager/src/commonMain/kotlin/cafe/adriel/voyager/navigator/Navigator.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocBuilder.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocConsumer.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocListener.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocProvider.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/BlocSelector.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/MultiBlocProvider.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/internal/BlocBindings.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/internal/BlocStore.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/internal/LocalBlocStoreOwner.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/core/Change.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/core/Transition.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/utils/nanoid.kt`
- shfmt / bash / uncertain-shfmt-only:
  - `.aitask-scripts/aitask_fold_mark.sh`
- textmate / kotlin / comment-class-differs:
  - `voyager/src/androidMain/kotlin/com/beyondeye/kbloc/compose/navigator/AndroidRootNavigator.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/navigator/init_generic_store_owners.kt`
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
