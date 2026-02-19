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

## Final Implementation Notes
- **Actual work done:** Added detection for c-sharp, dart, flutter, ios, and swift across 3 of 4 test functions (root files, extensions, directory patterns). Shebang test was not modified as these languages don't use shebangs. Created a comprehensive test suite with 90 tests covering all 17 environments.
- **Deviations from plan:** Added `tests/test_detect_env.sh` test suite (not in original plan, requested by user during review).
- **Issues encountered:** None significant. The `compgen -G` pattern works well for glob matching in root file detection.
- **Key decisions:** Used `compgen -G` for glob matching (consistent with no existing pattern in the script but necessary for .csproj/.sln/.xcodeproj detection). Flutter detection uses `grep` on `pubspec.yaml` for `flutter:` and `flutter_` patterns. Swift/iOS distinction: Package.swift alone = server-side Swift only, Xcode project = iOS + Swift.
