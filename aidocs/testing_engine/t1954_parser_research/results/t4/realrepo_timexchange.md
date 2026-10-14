# Real-repository disagreement: timexchange

baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched

Input: `timexchange@c60e7e05a465`, the walked checkout at that commit.

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
| gotreesitter | bash | 151 | 0 | 0 | 0 / 0 | 0 | 0 | 9 |
| gotreesitter | python | 197 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| gotreesitter | kotlin | 970 | 0 | 0 | 0 / 0 | 0 | 0 | 186 |
| gotreesitter | java | 15 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| ktpsi | kotlin | 970 | 0 | 0 | 0 / 0 | 0 | 0 | 13 |
| pygments | bash | 151 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pygments | python | 197 | 0 | 0 | 20 / 24 | 0 | 0 | 0 |
| pygments | kotlin | 970 | 0 | 0 | 5 / 66 | 0 | 0 | 18 |
| pygments | java | 15 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| pytokenize | python | 197 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| shfmt | bash | 151 | 0 | 0 | 0 / 0 | 0 | 0 | 1 |
| textmate | bash | 151 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | python | 197 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| textmate | kotlin | 970 | 0 | 0 | 5 / 66 | 0 | 0 | 0 |
| textmate | java | 15 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | bash | 151 | 0 | 0 | 0 / 0 | 0 | 0 | 5 |
| tscgo | python | 197 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | kotlin | 970 | 0 | 0 | 0 / 0 | 0 | 0 | 72 |
| tscgo | java | 15 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | bash | 151 | 0 | 0 | 0 / 0 | 0 | 0 | 5 |
| tswasm | python | 197 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | kotlin | 970 | 0 | 0 | 0 / 0 | 0 | 0 | 72 |
| tswasm | java | 15 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |

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
- gotreesitter / bash / uncertain-gotreesitter-only:
  - `.aitask-scripts/aitask_attach.sh`
  - `.aitask-scripts/aitask_contribution_review.sh`
  - `.aitask-scripts/aitask_create.sh`
  - `.aitask-scripts/aitask_revert_analyze.sh`
  - `.aitask-scripts/aitask_review_commits.sh`
  - `.aitask-scripts/aitask_stats_legacy.sh`
  - `.aitask-scripts/lib/atomic_write.sh`
  - `.aitask-scripts/lib/task_utils.sh`
  - `gradlew`
- gotreesitter / kotlin / uncertain-gotreesitter-only:
  - `app/src/debug/java/com/beyondeye/timexchange/di/AppModuleBindsAnalytics.kt`
  - `app/src/main/java/com/beyondeye/calendar/CalendarViewModel.kt`
  - `app/src/main/java/com/beyondeye/calendar/ExpandableCalendar.kt`
  - `app/src/main/java/com/beyondeye/calendar/component/CalendarPager.kt`
  - `app/src/main/java/com/beyondeye/calendar/component/InlineCalendar.kt`
  - `app/src/main/java/com/beyondeye/calendar/component/MonthViewCalendar.kt`
  - `app/src/main/java/com/beyondeye/schedule/schedule/basicEvent.kt`
  - `app/src/main/java/com/beyondeye/schedule/schedule/schedule.kt`
  - `app/src/main/java/com/beyondeye/schedulewcal/weekScheduleWithCalendar.kt`
  - `app/src/main/java/com/beyondeye/timexchange/monitoring/utils/PlayStoreAppMetadataRetriever.kt`
  - `app/src/main/java/com/beyondeye/timexchange/payments/PaymentServiceRevenueCat.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/achievements/components/AchievementLogLine.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/achievements/components/AchievementsPrizeSummary.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/achievements/components/WizardLevelAndXp.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/activities/ActivitiesScreenCubit.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/activities/components/WizardMessageTooltip.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/activities/handlers/ShowInAppReviewsDialogEffect.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/activities/wizmsgs/messagesForAchievements.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/addeditactivity/AddActivityScreen.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/addeditactivity/AddEditActivityComponents.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/addeditactivity/components/LabeledRoundBox.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/addeditactivity/components/LinkedAppsDialog.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/addeditactivity/components/SelectedSoundDialog.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/addeditactivity/pagedefs/AddActivityBasePageDef.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/addeditactivity/pagedefs/activityAdvFreezesOptionsPagedef.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/addeditactivity/pagedefs/activityAdvTimeBonusesPagedef.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/apptoactlnks/AppToActivityLinksScreen.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/goals/goalcalendar/GoalCalendar.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/goals/goalcalendar/SimpleCalendarTitle.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/history/historyEvent.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/login/LoginCubit.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/login/loginok/CheckAndPromptEnablingAppLinks.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/login/loginok/EmailVerifiedScreen.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/main/mainScreenTopbarComposables.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/onboarding/OnBoardingPageDef.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/onboarding/WizardPageDef.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/onboarding/components/WizardPageTopPart.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/onboarding/pagedefs/enableAutomaticMonitoringPagedef.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/running/RunningActivityComponents.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/settings/SettingsScreen.kt`
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
- shfmt / bash / uncertain-shfmt-only:
  - `.aitask-scripts/aitask_fold_mark.sh`
- textmate / kotlin / comment-class-differs:
  - `txcore/src/main/java/com/beyondeye/txcore/apicalls/ApiCallsRemoteStorage.kt`
  - `txdatamodels/src/main/kotlin/com/beyondeye/timexchange/datamodels/datapaths/DBPath.kt`
  - `txdatamodels/src/main/kotlin/com/beyondeye/timexchange/datamodels/datapaths/FSPath.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/compose/navigator/AndroidRootNavigator.kt`
  - `txvoyager/src/main/java/com/beyondeye/kbloc/compose/navigator/init_generic_store_owners.kt`
- tscgo / bash / uncertain-tscgo-only:
  - `.aitask-scripts/aitask_add_model.sh`
  - `.aitask-scripts/aitask_create.sh`
  - `.aitask-scripts/lib/atomic_write.sh`
  - `.aitask-scripts/lib/task_utils.sh`
  - `gradlew`
- tscgo / kotlin / uncertain-tscgo-only:
  - `app/src/main/java/com/beyondeye/calendar/component/CalendarPager.kt`
  - `app/src/main/java/com/beyondeye/schedule/schedule/schedule.kt`
  - `app/src/main/java/com/beyondeye/schedulewcal/weekScheduleWithCalendar.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/achievements/components/AchievementsPrizeSummary.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/activities/ActivitiesScreenCubit.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/activities/wizmsgs/messagesForAchievements.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/addeditactivity/AddEditActivityComponents.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/addeditactivity/components/LabeledRoundBox.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/addeditactivity/pagedefs/AddActivityBasePageDef.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/onboarding/OnBoardingPageDef.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/onboarding/WizardPageDef.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/running/RunningActivityComponents.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/settings/subscreens/scancode/ScanQRCodeCameraContent.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/settings/subscreens/startendofday/StartEndOfDayScreen.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/settings/uicomponents/ActionWithPInProtection.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/settings/uicomponents/SettingsLine.kt`
  - `app/src/main/java/com/beyondeye/timexchange/ui/theme/Theme.kt`
  - `app/src/main/java/com/beyondeye/timexchange/uicomponents/AnimatedMultiChoiceButton.kt`
  - `app/src/main/java/com/beyondeye/timexchange/uicomponents/dialogs/ConfirmDialog.kt`
  - `app/src/main/java/com/beyondeye/timexchange/uicomponents/plots/LineGraph4.kt`
  - `txdomain/src/main/java/com/beyondeye/txdomain/model/FreezeBalance.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/calendar_kiziton/Calendar.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/calendar_kiziton/CalendarMonths.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/calendar_kiziton/heatmapcalendar/HeatMapCalendar.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/cascade/Cascade.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/cascade/internal/AnimateEntryExit.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/cascade/internal/PositionPopupContent.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/emojipicker/ComposeEmojiPickerBottomSheetUI.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/madrapps_plot/Axes.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/madrapps_plot/line/Components.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/OverlayInformation.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/bar/BarChart.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/bar/BarChartWithLegend.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/grid/ChartAxis.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/grid/GridDefaults.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/line/ChartLegend.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/line/LineChart.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/line/LineChartOverlayInformation.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/line/LineChartWithLegend.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/pie/PieChartLegend.kt`
- tswasm / bash / uncertain-tswasm-only:
  - `.aitask-scripts/aitask_add_model.sh`
  - `.aitask-scripts/aitask_create.sh`
  - `.aitask-scripts/lib/atomic_write.sh`
  - `.aitask-scripts/lib/task_utils.sh`
  - `gradlew`
- tswasm / kotlin / uncertain-tswasm-only:
  - `app/src/main/java/com/beyondeye/calendar/component/CalendarPager.kt`
  - `app/src/main/java/com/beyondeye/schedule/schedule/schedule.kt`
  - `app/src/main/java/com/beyondeye/schedulewcal/weekScheduleWithCalendar.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/achievements/components/AchievementsPrizeSummary.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/activities/ActivitiesScreenCubit.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/activities/wizmsgs/messagesForAchievements.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/addeditactivity/AddEditActivityComponents.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/addeditactivity/components/LabeledRoundBox.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/addeditactivity/pagedefs/AddActivityBasePageDef.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/onboarding/OnBoardingPageDef.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/onboarding/WizardPageDef.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/running/RunningActivityComponents.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/settings/subscreens/scancode/ScanQRCodeCameraContent.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/settings/subscreens/startendofday/StartEndOfDayScreen.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/settings/uicomponents/ActionWithPInProtection.kt`
  - `app/src/main/java/com/beyondeye/timexchange/screens/settings/uicomponents/SettingsLine.kt`
  - `app/src/main/java/com/beyondeye/timexchange/ui/theme/Theme.kt`
  - `app/src/main/java/com/beyondeye/timexchange/uicomponents/AnimatedMultiChoiceButton.kt`
  - `app/src/main/java/com/beyondeye/timexchange/uicomponents/dialogs/ConfirmDialog.kt`
  - `app/src/main/java/com/beyondeye/timexchange/uicomponents/plots/LineGraph4.kt`
  - `txdomain/src/main/java/com/beyondeye/txdomain/model/FreezeBalance.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/calendar_kiziton/Calendar.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/calendar_kiziton/CalendarMonths.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/calendar_kiziton/heatmapcalendar/HeatMapCalendar.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/cascade/Cascade.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/cascade/internal/AnimateEntryExit.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/cascade/internal/PositionPopupContent.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/emojipicker/ComposeEmojiPickerBottomSheetUI.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/madrapps_plot/Axes.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/madrapps_plot/line/Components.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/OverlayInformation.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/bar/BarChart.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/bar/BarChartWithLegend.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/grid/ChartAxis.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/grid/GridDefaults.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/line/ChartLegend.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/line/LineChart.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/line/LineChartOverlayInformation.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/line/LineChartWithLegend.kt`
  - `txlibs/src/main/java/com/beyondeye/txlibs/ncharts/pie/PieChartLegend.kt`
