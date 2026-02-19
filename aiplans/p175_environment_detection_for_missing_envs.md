---
Task: t175_environment_detection_for_missing_envs.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

The `aireviewguides/reviewenvironments.txt` file lists 17 environments, but `aiscripts/aitask_review_detect_env.sh` only detects 12 of them. Five environments have no detection logic: **c-sharp**, **dart**, **flutter**, **ios**, and **swift**.

## Plan

Modify `aiscripts/aitask_review_detect_env.sh` to add detection for all 5 missing environments across the 4 existing test functions.

### Changes to `test_project_root_files()` (weight: 3)

- **C#**: Check for `*.csproj`, `*.sln` files in root
- **Dart / Flutter**: Check for `pubspec.yaml`. If present, score `dart`. If flutter dependency present, also score `flutter`.
- **iOS / Swift**: Check for `*.xcodeproj` or `*.xcworkspace` directories, `Package.swift`.

### Changes to `test_file_extensions()` (weight: 1)

- `cs` → score `c-sharp`
- `dart` → score `dart`
- `swift` → score `swift`; if Xcode project exists, also score `ios`

### Changes to `test_shebang_lines()`

No changes needed.

### Changes to `test_directory_patterns()` (weight: 2)

- **iOS**: `*.xcodeproj/*`, `ios/*`, `Pods/*`
- **Flutter**: `lib/*.dart` pattern, `android/` + `ios/` coexistence
- **C#**: `Properties/*`, `obj/*` patterns

### Verification

Run the script with test inputs for each new environment.
