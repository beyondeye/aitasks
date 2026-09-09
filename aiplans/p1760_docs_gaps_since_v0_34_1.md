---
Task: t1760_docs_gaps_since_v0_34_1.md
Branch: main
Base branch: main
Output branch: main
---

# t1760 — Document the `ait upgrade` version-check timeout knob

## Context

`/aitask-docs-gap` found one documentation gap in the `v0.34.1..HEAD` window
(the two other gaps it found are owned by t1657_6 / t1705_9 / t1705_10 and are
explicitly out of scope for this task).

t1244 made the version check reach the network under a **hard time bound**: the
`git ls-remote` fallback used when the GitHub REST API is rate-limited now runs
as a watchdogged background job that kills its whole process tree on expiry,
instead of hanging forever on a remote that blackholes the connection. The bound
is 10 seconds and is overridable through `AIT_GIT_LSREMOTE_TIMEOUT`.

The website's `## ait upgrade` section
(`website/content/docs/commands/setup-install.md:58`) is currently silent about
the version check touching the network at all — no fallback, no bound, no knob.
That is an inconsistency with the sibling git escape-hatch knob
`AIT_GIT_SKIP_STATE_CHECK`, which is documented inline in prose at
`website/content/docs/commands/sync.md:252`. This task closes that
inconsistency; it introduces no new documentation pattern.

## Ground truth (read from the landed code, not from the task description)

- `.aitask-scripts/lib/github_release.sh:45` — `_AIT_GIT_LSREMOTE_TIMEOUT_DEFAULT=10`.
- `.aitask-scripts/lib/github_release.sh:161-166` — `AIT_GIT_LSREMOTE_TIMEOUT`
  is read, then **normalized**: any value that is not a positive integer (empty,
  `0`, negative, non-numeric) falls back to the 10s default. Unit: whole seconds.
- `.aitask-scripts/lib/github_release.sh:148-207` — on expiry the job's process
  tree is killed and the function prints **nothing** and returns 0, so the caller
  sees "no version found", never a hang.
- `install.sh:236-278` — `_install_ls_remote_tags()` is the installer's private
  mirror; same 10s default, same variable, same normalization.

Which paths actually honor the knob:

| path | uses the bounded `git ls-remote`? | what the user sees on expiry |
|---|---|---|
| `ait upgrade latest` (`aitask_upgrade.sh:51-79`) | yes — **only** on the rate-limited branch (rc 2); a plain network failure dies before reaching it | dies with the rate-limit message + its `GH_TOKEN` hint, rather than hanging |
| `ait setup` version check (`aitask_setup.sh:2466`) | yes, via `github_resolve_latest_version` (rc 2 or 4) | silent — no "update available" notice (documented silent-degrade contract) |
| `curl \| bash` installer with no `--version` (`install.sh:357`) | yes — git tags are tried *first*, no REST call | **not silent**: after `[ait] Resolving latest aitasks release...` (`install.sh:356`) it moves on to `[ait] Fetching latest release via the GitHub API...` (`install.sh:380`), and if that REST fallback also resolves nothing it exits 1 with `[ait] Error: Could not find release tarball.` + the releases link (`install.sh:385`) |
| `ait` dispatcher's once-a-day update check (`ait:172`) | **no** — a direct `curl --max-time 5`, no git fallback | unaffected by the knob |

Two things the prose must not get wrong:

- The dispatcher row. The page's existing "**Automatic update check:**"
  paragraph describes exactly that once-a-day check, so a reader could easily
  assume the new knob applies to it. It does not.
- The three honoring paths do **not** share one outcome. Only `ait setup` is
  silent. `ait upgrade` dies with the rate-limit message it was already
  recovering from, and the installer visibly announces its REST fallback and can
  end in a terminal error. "Degrades quietly" is true of exactly one of them, so
  the outcomes must be stated per path.

## Approach

Single file: `website/content/docs/commands/setup-install.md`. Three edits, all
current-state-only prose (`aidocs/framework/documentation_conventions.md`).

### 1. Extend "How it works" step 1 (`setup-install.md:70`)

Point the numbered step at the new prose instead of leaving "queries GitHub API"
as the whole story:

```markdown
1. Resolves the target version (queries the GitHub API for `latest`, with a
   rate-limit-free `git ls-remote` fallback — see **Bounded version lookup**
   below — or validates the provided version number)
```

### 2. Add a "Bounded version lookup" block after the "How it works" list

Inserted between the numbered list (ends `setup-install.md:75`) and
"**Automatic update check:**" (`setup-install.md:77`). Bold-lead paragraph, not
a `###` heading — that matches the local style inside `## ait upgrade`.

```markdown
**Bounded version lookup:**

Resolving `latest` reaches the network. The GitHub REST API is tried first; when
it answers with a rate-limit error, the version is resolved from `git ls-remote`
instead, which is exempt from the REST quota. That git lookup is hard-bounded —
**10 seconds** by default — because a remote that blackholes the connection
instead of refusing it would otherwise stall the command indefinitely. Override
the bound with `AIT_GIT_LSREMOTE_TIMEOUT`, in whole seconds:

```bash
AIT_GIT_LSREMOTE_TIMEOUT=30 ait upgrade latest
```

An empty, zero, negative, or non-numeric value falls back to the 10-second
default. When the bound trips, the lookup yields no version rather than hanging,
and `ait upgrade` stops with the rate-limit message it was recovering from,
including its `GH_TOKEN` hint.

Two other paths use the same bounded lookup and honor the same variable, and
they report an expiry differently:

- The version check at the end of [`ait setup`](#ait-setup) is silent — it
  simply prints no "update available" notice.
- The `curl | bash` installer resolves the latest release from git tags before
  it touches the REST API, so an expiry is visible: after
  `Resolving latest aitasks release...` it announces
  `Fetching latest release via the GitHub API...` and continues there. If that
  fallback cannot resolve a release either, the installer stops with
  `Error: Could not find release tarball.` and a link to the releases page.
```

### 3. Scope the "Automatic update check" paragraph (`setup-install.md:79`)

Add one parenthetical so the daily dispatcher check is not read as covered by
the knob:

```markdown
The `ait` dispatcher checks for new versions once per day (at most) — a direct
API call with its own short timeout, independent of the bounded git lookup
above. When a newer version is available, …
```

(The rest of that paragraph is unchanged.)

### Deliberately not done

- **No cross-reference from `website/content/docs/installation/known-issues.md`.**
  The task said "consider" it. That page is scoped to *per-code-agent* workflow
  caveats ("This page tracks current workflow issues by code agent", grouped
  under `## Claude Code` / `## Codex CLI` / `## OpenCode`); a network-timeout
  knob for `ait upgrade` has no home in that taxonomy and adding one would
  dilute it.
- **No new "environment variables" reference page.** The house treatment for
  these knobs is inline prose at the point of use (`AIT_GIT_SKIP_STATE_CHECK`
  in `sync.md`, `AIT_GATES_REFERENCE` in `gates.md`); a central table is a
  different, larger decision and is not this task's gap.
- **No code changes.** `AIT_GIT_LSREMOTE_TIMEOUT` and its normalization already
  ship; this task only documents them.

## Files

- `website/content/docs/commands/setup-install.md` — the only file modified.

## Verification

1. **Facts match the source** — re-grep the three claims the prose makes, so the
   numbers are not copied from the task description:
   ```bash
   grep -n '_AIT_GIT_LSREMOTE_TIMEOUT_DEFAULT=' .aitask-scripts/lib/github_release.sh
   grep -n 'AIT_GIT_LSREMOTE_TIMEOUT' install.sh
   grep -rn 'AIT_GIT_LSREMOTE_TIMEOUT\|max-time 5' ait
   ```
   Expect: default `10` in the library; the same default mirrored in
   `install.sh`; and **no** hit for the variable in the `ait` dispatcher (which
   is what makes the "independent of the bounded git lookup" claim true).
2. **The quoted installer messages exist verbatim** — the prose promises a
   specific on-screen sequence, and nothing else in this plan checks it:
   ```bash
   grep -n 'Resolving latest aitasks release\|Fetching latest release via the GitHub API\|Could not find release tarball' install.sh
   ```
   Expect three hits, in that order (currently `install.sh:356`, `:380`, `:385`),
   with the third reached via `die` (exit 1). Also re-read
   `install.sh:352-386` to confirm an empty `version` still falls *through* to
   the REST discovery rather than exiting early — that control flow is the whole
   claim of the installer bullet.
3. **Link check** (mandatory after any `website/content/` edit):
   ```bash
   cd website && python3 check_links.py --build
   ```
   Must exit 0. It is the only thing that validates the new `#ait-setup`
   in-page anchor — Hugo builds a dead fragment green.
4. **Render check** — build and read the section back:
   ```bash
   cd website && hugo build --gc --minify
   ```
   Confirm the fenced `bash` block inside the bold-lead paragraph renders as a
   code block and the surrounding prose is not swallowed by it.

## Risk

### Code-health risk: low
- None identified. Documentation-only change to a single page; no shell, Python,
  or skill surface is touched, and nothing depends on this page's content.

### Goal-achievement risk: medium
- The prose could overstate the knob's reach — in particular by implying it
  bounds the `ait` dispatcher's once-a-day update check, which is a plain
  `curl --max-time 5` with no git fallback. · severity: low · → mitigation:
  covered by plan edit 3 (the explicit "independent of the bounded git lookup"
  parenthetical) and by Verification step 1, which asserts the dispatcher
  contains no reference to the variable.
- The task's explicit requirement is to say *what a user sees* when the bound
  trips, and the three honoring paths do not share one outcome — flattening them
  into a single "degrades quietly" claim would be wrong for the installer, which
  announces its REST fallback and can exit 1. Neither the link check nor the
  Hugo build can catch a semantic mismatch like that. · severity: medium ·
  → mitigation: covered by plan edit 2, which states the outcome per path, and
  by Verification step 2, which pins the three quoted installer messages and the
  fall-through control flow to `install.sh`.

No mitigations are proposed as spawned tasks or extra plan phases. Both
identified risks are accuracy risks about this plan's own prose, and each is
already discharged by a specific edit plus a specific verification step above; a
spawned task or an extra phase would only restate work the plan already does.
The goal-achievement level is **medium** rather than low because the per-path
outcome error was real — it was present in the first draft of this plan and
caught in review, not hypothetical.

## Post-implementation

Follow **Step 9 (Post-Implementation)** of the task workflow for commit,
cleanup, and archival. Commit type: `documentation: … (t1760)`.
