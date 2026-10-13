# Real-repository disagreement: timexchange

baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Read-only walk of the repository's git-visible files (`git ls-files --cached --others --exclude-standard`) in the 8 research languages; nothing was executed or written there, and this report holds counts and paths only, never contents. Each candidate is compared with the baseline (the landed M2.2 lexers) as the reference; a disagreement is evidence to inspect, not a verdict on either side. Files over 2097152 bytes skipped: 0.

## Files per language

| lang | files | baseline uncertain |
|---|---|---|
| bash | 151 | 0 |
| python | 197 | 0 |
| go | 0 | 0 |
| kotlin | 970 | 0 |
| typescript | 0 | unsupported |
| tsx | 0 | unsupported |
| javascript | 0 | unsupported |
| java | 15 | unsupported |
| rust | 0 | unsupported |
| swift | 0 | unsupported |

## Candidate vs baseline

| subject | lang | files | unsupported | provider errors | comment-class differs (files / lines) | records differ (files) | uncertain: baseline only | uncertain: subject only |
|---|---|---|---|---|---|---|---|---|
| antlr | kotlin | 970 | 0 | 0 | 0 / 0 | 0 | 0 | 1 |
| antlr | java | 15 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| chroma | bash | 151 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| chroma | python | 197 | 0 | 0 | 20 / 24 | 0 | 0 | 0 |
| chroma | kotlin | 970 | 0 | 0 | 3 / 58 | 0 | 0 | 63 |
| chroma | java | 15 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| ktpsi | kotlin | 970 | 0 | 0 | 0 / 0 | 0 | 0 | 13 |
| pygments | bash | 151 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pygments | python | 197 | 0 | 0 | 20 / 24 | 0 | 0 | 0 |
| pygments | kotlin | 970 | 0 | 0 | 5 / 66 | 0 | 0 | 18 |
| pygments | java | 15 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | bash | 151 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | python | 197 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | kotlin | 970 | 0 | 0 | 5 / 66 | 0 | 0 | 0 |
| textmate | java | 15 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |

## Paths per disagreement kind

- antlr / kotlin / uncertain-antlr-only:
  - `txlibs/src/main/java/com/beyondeye/txlibs/timepicker/common/domain/Extensions.kt`
- chroma / python / comment-class-differs:
  - `.aitask-scripts/applink/headless.py`
  - `.aitask-scripts/applink/pairing.py`
  - `.aitask-scripts/board/aitask_board.py`
  - `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `.aitask-scripts/brainstorm/brainstorm_session.py`
  - `.aitask-scripts/chatlink/config.py`
  - `.aitask-scripts/chatlink/relay.py`
  - `.aitask-scripts/chatlink/sessions_store.py`
  - `.aitask-scripts/lib/agent_marks.py`
  - `.aitask-scripts/lib/config_utils.py`
  - `.aitask-scripts/lib/cross_repo_settings.py`
  - `.aitask-scripts/lib/gate_ledger.py`
  - `.aitask-scripts/lib/gate_registry_sync.py`
  - `.aitask-scripts/lib/shortcut_labels.py`
  - `.aitask-scripts/lib/trail_gather.py`
  - `.aitask-scripts/lib/work_report_gather.py`
  - `.aitask-scripts/monitor/minimonitor_app.py`
  - `.aitask-scripts/monitor/monitor_app.py`
  - `.aitask-scripts/monitor/monitor_core.py`
  - `.aitask-scripts/syncer/syncer_app.py`
- chroma / kotlin / comment-class-differs:
  - `txcore/src/main/java/com/beyondeye/txcore/apicalls/ApiCallsRemoteStorage.kt`
  - `txdatamodels/src/main/kotlin/com/beyondeye/timexchange/datamodels/datapaths/DBPath.kt`
  - `txdatamodels/src/main/kotlin/com/beyondeye/timexchange/datamodels/datapaths/FSPath.kt`
- chroma / kotlin / uncertain-chroma-only:
  - `app/src/main/java/com/beyondeye/calendar/ExpandableCalendar.kt`
  - `app/src/main/java/com/beyondeye/timexchange/MainActivity.kt`
  - `app/src/main/java/com/beyondeye/timexchange/jobs/BackupActivityRecordsJobService.kt`
  - `app/src/main/java/com/beyondeye/timexchange/monitoring/TimerActivationMonitoringBackgroundAndroidService.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/activities/ActivitiesScreen.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/activities/components/KonfettiLayer.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/activities/handlers/AppUsageRecordsHandler.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/editrecord/AddEditRecordScreenComponents.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/goals/GoalsScreen.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/goals/goalcalendar/ContinuousSelectionHelper.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/goals/goalcalendar/backgroundHighlight.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/paywall/PaywallScreen.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/running/RunningActivityComponents.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/settings/subscreens/scancode/ScanCodeScreen.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/userchoice/UserChoiceScreen.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/userchoice/UserChoiceScreenModel.kt`
  - `app/src/main/java/com/beyondeye/timexchange/uicomponents/pininput/CheckPinDialog.kt`
  - `app/src/main/java/com/beyondeye/timexchange/uicomponents/plots/LineGraph4.kt`
  - `app/src/main/java/com/beyondeye/timexchange/wizard/rive/WizardAnimations.kt`
  - `buildSrc/build.gradle.kts`
  - `txaboutlibscanner/src/main/java/com/mikepenz/aboutlibraries/Libs.kt`
  - `txaboutlibscanner/src/main/java/com/mikepenz/aboutlibraries/entity/License.kt`
  - `txaboutlibscanner/src/test/java/com/beyondeye/aboutlibscanner/testUtils.kt`
  - `txcore/src/androidTest/java/com/beyondeye/txdomain/interactor/ActivityStreaksMediatorTest.kt`
  - `txcore/src/main/java/com/beyondeye/txcore/remote_impl/RemoteDatabaseFirebase.kt`
  - `txcore/src/main/java/com/beyondeye/txcore/remote_impl/RemoteStorageFirebase.kt`
  - `txcore/src/main/java/com/beyondeye/txcore/zippedcache/ZippedDataCache.kt`
  - `txdbaccess/src/main/java/com/beyondeye/txdbaccess/database/AppDatabase.kt`
  - `txdbaccess/src/main/java/com/beyondeye/txdbaccess/repo/AchievementRepoImpl.kt`
  - `txdbaccess/src/main/java/com/beyondeye/txdbaccess/utils/PrefsUtils.kt`
  - `txdomain/src/main/java/com/beyondeye/txdomain/interactor/AchievementsRewarder.kt`
  - `txdomain/src/main/java/com/beyondeye/txdomain/interactor/RemoveRunningRecordMediator.kt`
  - `txdomain/src/main/java/com/beyondeye/txdomain/mapper/UserPairingMapper.kt`
  - `txdomain/src/main/java/com/beyondeye/txdomain/model/AchievementCode.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/calendar_kiziton/CalendarDefaults.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/cascade/Cascade.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/cascade/internal/AnimateEntryExit.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/emojipicker/ComposeEmojiPickerBottomSheetUI.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/konfetti/core/emitter/EmitterConfig.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/madrapps_plot/line/Components.kt`
- ktpsi / kotlin / uncertain-ktpsi-only:
  - `app/build.gradle.kts`
  - `build.gradle.kts`
  - `buildSrc/build.gradle.kts`
  - `buildSrc/settings.gradle.kts`
  - `settings.gradle.kts`
  - `txaboutlibscanner/build.gradle.kts`
  - `txcore/build.gradle.kts`
  - `txdatamodels/build.gradle.kts`
  - `txdbaccess/build.gradle.kts`
  - `txdomain/build.gradle.kts`
  - `txlibs/build.gradle.kts`
  - `txsyncexecutor/build.gradle.kts`
  - `txvoyager/build.gradle.kts`
- pygments / python / comment-class-differs:
  - `.aitask-scripts/applink/headless.py`
  - `.aitask-scripts/applink/pairing.py`
  - `.aitask-scripts/board/aitask_board.py`
  - `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `.aitask-scripts/brainstorm/brainstorm_session.py`
  - `.aitask-scripts/chatlink/config.py`
  - `.aitask-scripts/chatlink/relay.py`
  - `.aitask-scripts/chatlink/sessions_store.py`
  - `.aitask-scripts/lib/agent_marks.py`
  - `.aitask-scripts/lib/config_utils.py`
  - `.aitask-scripts/lib/cross_repo_settings.py`
  - `.aitask-scripts/lib/gate_ledger.py`
  - `.aitask-scripts/lib/gate_registry_sync.py`
  - `.aitask-scripts/lib/shortcut_labels.py`
  - `.aitask-scripts/lib/trail_gather.py`
  - `.aitask-scripts/lib/work_report_gather.py`
  - `.aitask-scripts/monitor/minimonitor_app.py`
  - `.aitask-scripts/monitor/monitor_app.py`
  - `.aitask-scripts/monitor/monitor_core.py`
  - `.aitask-scripts/syncer/syncer_app.py`
- pygments / kotlin / comment-class-differs:
  - `txcore/src/main/java/com/beyondeye/txcore/apicalls/ApiCallsRemoteStorage.kt`
  - `txdatamodels/src/main/kotlin/com/beyondeye/timexchange/datamodels/datapaths/DBPath.kt`
  - `txdatamodels/src/main/kotlin/com/beyondeye/timexchange/datamodels/datapaths/FSPath.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/compose/navigator/AndroidRootNavigator.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/compose/navigator/init_generic_store_owners.kt`
- pygments / kotlin / uncertain-pygments-only:
  - `txaboutlibscanner/src/main/java/com/mikepenz/aboutlibraries/entity/License.kt`
  - `txdatamodels/src/main/kotlin/com/beyondeye/timexchange/datamodels/item/Hashids.kt`
  - `txdbaccess/src/main/java/com/beyondeye/txdbaccess/database/AppDatabase.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/qrcodecomposelib/common/QRCodeComposeXFormat.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/timepicker/common/domain/Extensions.kt`
  - `txvoyager/src/main/java/cafe/adriel/voyager/navigator/Navigator.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/compose/BlocBuilder.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/compose/BlocConsumer.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/compose/BlocListener.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/compose/BlocProvider.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/compose/BlocSelector.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/compose/MultiBlocProvider.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/compose/internal/BlocBindings.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/compose/internal/BlocStore.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/compose/internal/LocalBlocStoreOwner.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/core/Change.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/core/Transition.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/utils/nanoid.kt`
- textmate / kotlin / comment-class-differs:
  - `txcore/src/main/java/com/beyondeye/txcore/apicalls/ApiCallsRemoteStorage.kt`
  - `txdatamodels/src/main/kotlin/com/beyondeye/timexchange/datamodels/datapaths/DBPath.kt`
  - `txdatamodels/src/main/kotlin/com/beyondeye/timexchange/datamodels/datapaths/FSPath.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/compose/navigator/AndroidRootNavigator.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/compose/navigator/init_generic_store_owners.kt`
