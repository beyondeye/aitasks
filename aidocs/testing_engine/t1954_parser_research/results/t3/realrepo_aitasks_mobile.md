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
| antlr | kotlin | 260 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| chroma | bash | 141 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| chroma | python | 148 | 0 | 0 | 9 / 9 | 0 | 0 | 0 |
| chroma | kotlin | 260 | 0 | 0 | 0 / 0 | 0 | 0 | 25 |
| chroma | swift | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| ktpsi | kotlin | 260 | 0 | 0 | 0 / 0 | 0 | 0 | 8 |
| pygments | bash | 141 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pygments | python | 148 | 0 | 0 | 9 / 9 | 0 | 0 | 0 |
| pygments | kotlin | 260 | 0 | 0 | 2 / 8 | 0 | 0 | 17 |
| pygments | swift | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | bash | 141 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | python | 148 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | kotlin | 260 | 0 | 0 | 2 / 8 | 0 | 0 | 0 |
| textmate | swift | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |

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
- textmate / kotlin / comment-class-differs:
  - `voyager/src/androidMain/kotlin/com/beyondeye/kbloc/compose/navigator/AndroidRootNavigator.kt`
  - `voyager/src/commonMain/kotlin/com/beyondeye/kbloc/compose/navigator/init_generic_store_owners.kt`
