---
title: "Review Guide Format"
linkTitle: "Review Guide Format"
weight: 20
description: "File format, vocabulary files, and matching algorithms for review guides"
---

## File Structure

Review guides are markdown files with YAML frontmatter in `aireviewguides/`, organized by environment subdirectory. Each guide contains metadata that powers auto-detection and similarity matching, plus actionable review instructions that `/aitask-review` applies during code review.

```yaml
---
name: Python Best Practices
description: Check type hints, modern idioms, context managers, and pythonic patterns
reviewtype: conventions
reviewlabels: [type-hints, idioms, context-managers, pythonic]
environment: [python]
source_url: https://example.com/python-guide
similar_to: general/code_conventions.md
---

## Review Instructions

### Type Hints
- Flag public functions missing type annotations on parameters and return types
- Look for use of `Any` where a more specific type is known
```

### Frontmatter Fields

| Field | Required | Values | Description |
|-------|----------|--------|-------------|
| `name` | Yes | string | Guide display name shown during selection |
| `description` | Yes | string | Brief description of what the guide reviews |
| `reviewtype` | Yes | string | Classification type from `reviewtypes.txt` |
| `reviewlabels` | Yes | `[label1, label2]` | Topic labels from `reviewlabels.txt` (3-6 recommended) |
| `environment` | No | `[env1, env2]` | Target environments from `reviewenvironments.txt`. Absent = universal guide |
| `source_url` | No | URL | Reference to the original source material |
| `similar_to` | No | relative path | Most similar guide, set by `/aitask-reviewguide-classify` when similarity score >= 5 |

The body must start with `## Review Instructions`, followed by `###` section headings each containing bullet-point checks. This structure is what `/aitask-review` reads and applies during code review.

---

## Directory Organization

Guides are organized into subdirectories by environment. The subdirectory name serves as a strong hint for the `environment` field value.

```
aireviewguides/
├── reviewtypes.txt            # Vocabulary: classification types
├── reviewlabels.txt           # Vocabulary: topic labels
├── reviewenvironments.txt     # Vocabulary: supported environments
├── .reviewguidesignore        # Exclude guides from auto-detection
├── general/                   # Universal guides (no environment field)
│   ├── code_conventions.md
│   ├── code_duplication.md
│   ├── error_handling.md
│   ├── performance.md
│   ├── refactoring.md
│   └── security.md
├── python/                    # environment: [python]
│   ├── python_best_practices.md
│   └── python_style_guide.md
├── shell/                     # environment: [bash, shell]
│   └── shell_scripting.md
├── android/                   # environment: [android, kotlin]
│   └── android_best_practices.md
├── cpp/
├── c-sharp/
├── dart/
├── go/
├── html-css/
├── javascript/
└── typescript/
```

Files in `general/` should **not** have an `environment` field (they are universal and apply to all projects). Files in other directories should have an `environment` field matching the values from `reviewenvironments.txt`.

---

## Vocabulary Files

Three text files in `aireviewguides/` constrain the metadata values. Each contains one value per line, sorted alphabetically. The `/aitask-reviewguide-classify` skill can extend these files when no existing value fits.

### reviewtypes.txt

Classification types that define the primary purpose of a guide:

```
bugs
code-smell
conventions
deprecations
performance
security
style
```

### reviewlabels.txt

Topic labels describing the specific review areas a guide covers (3-6 per guide recommended):

```
algorithmic-complexity  authentication  caching  code-smells  comments
compose  complexity  context-managers  coroutines  coupling  cryptography
database  deduplication  dry  edge-cases  error-handling  errors
exceptions  extraction  formatting  idioms  injection  input-validation
lifecycle  memory  naming  organization  portability  pythonic  quoting
resource-cleanup  secrets  shellcheck  type-hints
```

### reviewenvironments.txt

Supported environments, mapped to subdirectory names and the environment detection scoring:

```
android  bash  cmake  cpp  c-sharp  dart  flutter  go  html-css
ios  java  javascript  kotlin  python  rust  shell  swift  typescript
```

### .reviewguidesignore

Gitignore-style file for excluding guides from auto-discovery. Matching is performed via `git check-ignore --no-index`:

```
general/performance.md    # Exclude a specific guide
android/                  # Exclude an entire environment
*.draft.md                # Exclude all draft guides
!general/security.md      # Re-include after a broader exclusion
```

---

## Environment Detection Algorithm

The script `aiscripts/aitask_review_detect_env.sh` auto-detects which review guides are relevant to a set of files. It is called by `/aitask-review` during guide selection (Step 1b).

**Input:** A list of file paths via `--files FILE...` or `--files-stdin`.

**Scoring:** Four independent test functions each contribute scores to an associative array mapping environment names to numeric scores. Scores accumulate additively across tests.

### Test 1: Project Root Marker Files (weight 3)

Checks for well-known build and configuration files in the current directory:

| Marker Files | Environments Scored |
|-------------|-------------------|
| `pyproject.toml`, `setup.py`, `requirements.txt` | python |
| `build.gradle`, `build.gradle.kts` | android, kotlin |
| `CMakeLists.txt` | cpp, cmake |
| `package.json` | javascript, typescript |
| `Cargo.toml` | rust |
| `go.mod` | go |
| `*.csproj`, `*.sln` | c-sharp |
| `pubspec.yaml` | dart (+flutter if yaml contains `flutter:`) |
| `*.xcodeproj`, `*.xcworkspace`, `Package.swift` | ios, swift |

### Test 2: File Extensions (weight 1 per file)

Each input file scores its extension's associated environment(s):

| Extension(s) | Environments |
|-------------|-------------|
| `.py` | python |
| `.sh` | bash, shell |
| `.kt`, `.kts` | kotlin, android |
| `.java` | android (if `build.gradle` present) or java |
| `.js`, `.jsx`, `.mjs` | javascript |
| `.ts`, `.tsx`, `.mts` | typescript |
| `.cpp`, `.cc`, `.cxx`, `.c`, `.h`, `.hpp` | cpp |
| `.cmake` | cmake |
| `.rs` | rust |
| `.go` | go |
| `.cs` | c-sharp |
| `.dart` | dart |
| `.swift` | swift (+ios if `.xcodeproj`/`.xcworkspace` present) |

### Test 3: Shebang Lines (weight 2)

Reads the first line of up to 20 existing files from the input list. If it starts with `#!`:

- Contains `bash` or `/sh` → scores bash, shell
- Contains `python` → scores python

### Test 4: Directory Patterns (weight 2, fires once per pattern)

Checks file paths for known directory structures. Each pattern triggers scoring only once (deduplicated via boolean flags):

| Pattern | Environments |
|---------|-------------|
| `aiscripts/*` | bash, shell |
| `*.sh` at project root (no `/` in path) | bash, shell |
| `src/main/kotlin/*`, `src/main/java/*`, `app/src/*` | android, kotlin |
| `*.xcodeproj/*`, `ios/*`, `Pods/*` | ios, swift |
| `lib/*.dart`, `lib/**/*.dart` | flutter, dart |
| `Properties/*`, `obj/*` | c-sharp |

### Adding New Tests

To extend the detection system, add a new function `test_<name>()` to the script and register it in the `ALL_TESTS` array. Use `add_score "env_name" <weight>` to contribute scores.

---

## Guide Ranking

After scoring, guides are ranked for presentation to the user in `/aitask-review`:

1. **Environment-specific guides** — sorted by their maximum environment score (descending). For guides with multiple environments (e.g., `environment: [bash, shell]`), the highest-scoring environment determines the guide's rank
2. **Universal guides** — listed after all environment-specific guides, sorted alphabetically by name
3. **Non-matching guides** — environment-specific guides with a score of 0 appear at the bottom

**Output format** (pipe-delimited, two sections separated by `---`):

```
ENV_SCORES
python|6
bash|5
shell|5
---
REVIEW_GUIDES
python/python_best_practices.md|Python Best Practices|Check type hints...|6
shell/shell_scripting.md|Shell Scripting|Check variable quoting...|5
general/security.md|Security|Check for injection...|universal
```

---

## Similarity Scoring Algorithm

The script `aiscripts/aitask_reviewguide_scan.sh` analyzes guide metadata to find similar guides for consolidation. The `--compare FILE` mode is used by `/aitask-reviewguide-classify` (Step 5) and the `--find-similar` mode by `/aitask-reviewguide-merge`.

### Scoring Formula

```
score = (shared_labels_count × 2) + (type_match ? 3 : 0) + (env_overlap ? 2 : 0)
```

- **shared_labels_count** — number of `reviewlabels` values present in both guides
- **type_match** — 1 if both guides have the same `reviewtype` (and neither is missing), 0 otherwise
- **env_overlap** — 1 if environments overlap per the rules below, 0 otherwise

### Environment Overlap Rules

| Guide A | Guide B | Overlap? |
|---------|---------|----------|
| universal | universal | Yes |
| universal | specific | No (different scope) |
| specific | specific | Yes, if they share at least one environment value |

### Threshold

When the top similarity score is >= 5, the `/aitask-reviewguide-classify` skill sets the `similar_to` frontmatter field to the most similar guide's relative path.

### Scan Modes

| Mode | Purpose |
|------|---------|
| `--compare FILE` | Score all other guides against one target, sorted descending. Only scores > 0 |
| `--find-similar` | For each guide, find its single most similar peer by label overlap count |
| `--missing-meta` | Find guides missing `reviewtype`, `reviewlabels`, or `environment` (non-general) |
| `--environment ENV` | Filter output to guides matching a specific environment (or `"general"` for universal) |

---

## See Also

- [Code Review Workflow](../workflows/code-review/) — high-level review cycle and guide management
- [`/aitask-review`](../skills/aitask-review/) — run code reviews using guides
- [`/aitask-reviewguide-classify`](../skills/aitask-reviewguide-classify/) — assign metadata to guides
- [`/aitask-reviewguide-merge`](../skills/aitask-reviewguide-merge/) — consolidate overlapping guides
- [`/aitask-reviewguide-import`](../skills/aitask-reviewguide-import/) — import external content as guides
