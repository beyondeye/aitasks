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
| gotreesitter | bash | 151 | 0 | 0 | 0 / 0 | 0 | 0 | 9 |
| gotreesitter | python | 197 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| gotreesitter | kotlin | 970 | 0 | 0 | 0 / 0 | 0 | 0 | 186 |
| gotreesitter | java | 15 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | bash | 151 | 0 | 0 | 0 / 0 | 0 | 0 | 5 |
| tscgo | python | 197 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tscgo | kotlin | 970 | 0 | 0 | 0 / 0 | 0 | 0 | 72 |
| tscgo | java | 15 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | bash | 151 | 0 | 0 | 0 / 0 | 0 | 0 | 5 |
| tswasm | python | 197 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |
| tswasm | kotlin | 970 | 0 | 0 | 0 / 0 | 0 | 0 | 72 |
| tswasm | java | 15 | 0 | 0 | 0 / 0 | 0 | 0 | 0 |

## Paths per disagreement kind

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
