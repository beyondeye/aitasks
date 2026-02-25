---
title: "Build Verification"
linkTitle: "Build Verification"
weight: 10
description: "Configure build verification for post-implementation checks"
---

After implementation, the skill can optionally run a build verification command to catch regressions introduced by the task's changes. This is configured via `aitasks/metadata/project_config.yaml` and applies to all three implementation skills: `/aitask-pick`, `/aitask-pickrem`, and `/aitask-pickweb`.

## Configuration

```yaml
# Single command
verify_build: "cargo build"

# Multiple commands (run sequentially, stop on first failure)
verify_build:
  - "npm install"
  - "npm run build"
  - "npm test"
```

If `verify_build` is not set (or the file doesn't exist), the step is skipped entirely.

## How It Works

The `project_config.yaml` file is:
- **Git-tracked** — shared across the team (unlike `userconfig.yaml` which is per-user)
- **Project-specific** — not tied to execution profiles (the same build command applies regardless of which profile you use)
- **Installed from seed** — a template is copied during `ait setup`; edit it to match your project

### Failure Handling

If the build fails, the agent analyzes whether the failure is caused by the task's own changes:
- **Task-related failure:** The agent automatically goes back to fix the errors and re-runs the build. This repeats until the build passes.
- **Pre-existing failure:** The agent logs the build failure details in the plan file's "Final Implementation Notes" and proceeds without attempting to fix unrelated issues.

## Common Examples

| Project Type | `verify_build` |
|-------------|----------------|
| Android (Gradle) | `"JAVA_HOME=/opt/android-studio/jbr ./gradlew assembleDebug"` |
| Rust | `"cargo build"` |
| Node.js | `"npm run build"` |
| Go | `"go build ./..."` |
| Python | `"python -m py_compile main.py"` |
| Shell/scripts | *(leave empty — no build step)* |
