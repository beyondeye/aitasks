---
Task: t2134_push_retry_classifier_treats_every_rejection_as_a_race.md
Base branch: main
Output branch: main
---

# t2134 — Push-retry classifier treats every rejection as a race

## Context

`is_retryable_push_error` (`.aitask-scripts/lib/verified_update_lib.sh:122-125`)
matches `non-fast-forward|fetch first|rejected|failed to push some refs`. git
prints `error: failed to push some refs` for **every** rejected push, and the
bare `rejected` also matches `[remote rejected]` (hook refusals). So a hook
refusal, an ambiguous destination, a protected branch … is retried
`MAX_REMOTE_RETRIES` (5) times and reported as
`Failed to update metadata after 5 retries due to concurrent pushes` — git's
real reason never reaches the user. Both `aitask_verified_update.sh` and
`aitask_usage_update.sh` share this lib (`commit_metadata_update`).

## Probe evidence (git 2.56.0, real bare remote, `push --quiet` as the lib runs it)

| family | output (relevant lines) | must |
|---|---|---|
| client race, unseen tip | ` ! [rejected]        HEAD -> main (fetch first)` | retry |
| client race, known tip | ` ! [rejected]        HEAD -> main (non-fast-forward)` | retry |
| server-side race (competing push lands between advertisement and ref lock) | `remote: error: cannot lock ref … is at X but expected Y` / ` ! [remote rejected] HEAD -> main (incorrect old value provided)` | retry |
| pre-receive refusal | `remote: <hook text>` / ` ! [remote rejected] HEAD -> main (pre-receive hook declined)` | die fast |
| update-hook refusal | ` ! [remote rejected] HEAD -> main (hook declined)` | die fast |
| ambiguous destination | `error: dst refspec main matches more than one` | die fast |
| bad remote | `fatal: … does not appear to be a git repository` (rc 128) | die fast |

Key findings:
- A hook's own text arrives as `remote: …` lines and **can contain** the words
  `non-fast-forward` / `fetch first` / `rejected` (probed: a hook printing
  exactly that). So even the narrowed word list from the task's suggestion is
  spoofable; the classifier must anchor on git's **ref-status line**, which
  always starts ` ! [` and which hook output (always `remote: `-prefixed) can
  never produce.
- The `[rejected]` / `[remote rejected]` tags and the parenthesised reasons are
  not translated by git (the `error:`/`hint:` lines are), so the anchored form
  is also locale-independent — the old `failed to push some refs` alternative was not.
- The server-side race was reproduced deterministically (no sleep): origin's
  `pre-receive` runs one competing push (environment `GIT_*` unset, guarded by a
  flag file) before the outer push takes its ref lock.
- Older servers report the server-side race as `(failed to update ref)`, which
  also covers non-race failures (disk, permissions). It is deliberately **not**
  retryable: the list is non-exhaustive, so it fails closed — die with git's text.

## Implementation

1. **`.aitask-scripts/lib/verified_update_lib.sh` — `is_retryable_push_error`**
   Replace the body with a line-anchored ERE over git's ref-status lines only:
   ```bash
   # Only git's own ref-status lines are race evidence. "failed to push some
   # refs" ends EVERY rejected push (hook refusal, ambiguous dst, …) and a
   # hook's text arrives as "remote: …" lines that may contain any word, so
   # match the " ! [...]" status line, which a hook can never print (t2134).
   # Retryable: the client-side race (fetch first / non-fast-forward) and the
   # server-side one (a competing push moved the ref before our lock:
   # "incorrect old value provided"). Anything else dies with git's text.
   is_retryable_push_error() {
       local output="$1"
       printf '%s\n' "$output" | grep -Eq \
           '^ ! \[rejected\] .* \((fetch first|non-fast-forward)\)[[:space:]]*$|^ ! \[remote rejected\] .* \(incorrect old value provided\)[[:space:]]*$'
   }
   ```
   The non-retryable branch already exists: `die "Failed to push metadata update: $push_output"`
   — git's output verbatim, immediately (no retry).

2. **Same file — keep git's last reason on retry exhaustion.** In
   `commit_and_push_from_remote_clone`, before `return 10`, store the output in a
   new global `AIT_LAST_PUSH_OUTPUT` (declared next to the other out-params with
   a one-line comment; reset to `""` at the top of `commit_metadata_update`).
   The final `die` in `commit_metadata_update` becomes
   `"Failed to update metadata after ${MAX_REMOTE_RETRIES} retries due to concurrent pushes. Last push error: ${AIT_LAST_PUSH_OUTPUT}"`,
   so even the genuine-race exhaustion shows git's text.

3. **`tests/lib/metadata_update_fixture.sh` — shared origin-side hooks** (both
   entry-point test files need them; follow the existing `mdfix_write_*_hook` style):
   - `mdfix_install_refusing_pre_receive <origin_dir>` — pre-receive that echoes
     `policy: refused (non-fast-forward fetch first rejected)` (the spoof) and exits 1.
   - `mdfix_install_server_race_pre_receive <origin_dir> <flag_file>` — the
     probed deterministic server-side race (first invocation only: unset `GIT_*`,
     clone origin, commit `--allow-empty`, push; exit 0).
   - `mdfix_write_attempt_counter_hook <hook_path> <count_file>` — a
     `AITASK_VERIFIED_UPDATE_BEFORE_PUSH_HOOK` script that appends
     `$AITASK_VERIFIED_UPDATE_ATTEMPT` to `<count_file>`, so a test can assert
     how many push attempts ran without parsing logs.
   - `mdfix_server_race_reason` — runs the server-race probe once in a scratch
     bare origin and echoes the parenthesised reason from the
     ` ! [remote rejected]` line that the **installed** git emits
     (`incorrect old value provided` on current git; `failed to update ref` on
     older receive-packs such as 2.39.2). The fixtures use the local file
     transport, so client and server are the same installed binary, and the
     probe's answer describes the server the end-to-end tests run against.
     Empty output means the probe produced no rejected status line at all.

   **Server-race expectations follow the probed reason.** Every real-server
   race assertion below (4a's real-output row, 4c, 5) branches on
   `mdfix_server_race_reason`:
   - `incorrect old value provided` → retryable; end-to-end: exit 0,
     `UPDATED:…`, two attempts, origin carries the racer commit and the update.
   - `failed to update ref` → **not** retryable (the planned immediate-stop
     policy for an ambiguous status); end-to-end: non-zero exit, exactly one
     attempt, output contains `failed to update ref`, no `concurrent pushes`,
     origin carries only the racer commit.
   - anything else (including empty) → explicit FAIL naming the reason, so an
     unknown wording is reported, never silently given either expectation.
   Each branch prints which one ran, so a log shows which server shape was
   covered.

4. **`tests/test_verified_update.sh` — new section "Test t2134"** (after Test 9t):
   - **t2134a classifier vs real git output (unit).** In a scratch bare origin
     + clones, produce each family's real `git push --quiet` output (fetch
     first, non-ff, server-side race, pre-receive refusal incl. the spoof text,
     update-hook refusal, ambiguous dst via an unqualified `HEAD:main` beside a
     same-named tag, bad remote) and feed each to `is_retryable_push_error`
     (lib sourced in a subshell, rc captured outside it). Assert retry for the
     two client-race families, no-retry for the four non-race families, and the
     server-race row per the probed reason (above). Also a mutant control:
     the old regex returns retryable on the refusal and ambiguous-dst outputs
     (proves the fixtures exercise the bug).
   - **t2134a' classifier vs both server-race statuses (independent of the
     installed git).** Literal status-line fixtures, copied verbatim from the
     probes: ` ! [remote rejected] HEAD -> main (incorrect old value provided)`
     → retryable; ` ! [remote rejected] HEAD -> main (failed to update ref)` →
     not retryable. Each with a preceding `remote: error: cannot lock ref …`
     line, as git prints it. This pins both behaviours on every machine,
     whichever one the end-to-end tests can reach.
   - **t2134b hook refusal fails fast end-to-end.** `setup_remote_metadata_repo
     aitask_verified_update.sh` + refusing pre-receive + attempt counter. Assert:
     non-zero exit; output contains `pre-receive hook declined` and `policy: refused`;
     output does not contain `concurrent pushes` or `retrying`; counter file has
     exactly one attempt; origin tip unchanged.
   - **t2134c server-side race end-to-end.** Same fixture + server-race
     pre-receive + attempt counter. Expectations per the probed reason (above):
     retried and `UPDATED:` on current git; immediate stop showing
     `failed to update ref` on an older receive-pack.
   - **t2134d exhaustion shows git's reason.** Before-push hook that lands a
     competing commit on **every** attempt → assert non-zero exit, output
     contains `after 5 retries due to concurrent pushes` and `fetch first`.

5. **`tests/test_usage_update.sh` — mirror t2134b and t2134c** through
   `aitask_usage_update.sh` (the second entry point), using the fixture helpers;
   its t2134c mirror branches on `mdfix_server_race_reason` the same way.

## Verification

```bash
bash tests/test_verified_update.sh
bash tests/test_usage_update.sh
bash tests/test_verified_update_flags.sh
shellcheck .aitask-scripts/lib/verified_update_lib.sh tests/lib/metadata_update_fixture.sh
```
Red proof: temporarily run t2134b/t2134a against the pre-fix regex (scratch copy
of the lib, never `git stash`/`restore` in the shared tree) and confirm they fail.

Step 9 (Post-Implementation): commit code (`bug: … (t2134)`), plan via
`aitask_task_commit.sh`, archive per the workflow.

## Risk

### Code-health risk: low
- Narrowing the classifier changes behaviour only on push failure: a race variant git words differently from the three enumerated families (e.g. an older server's `(failed to update ref)`) now dies immediately instead of retrying, losing one usage/score bump with git's own message shown · severity: low · → mitigation: none (deliberate fail-closed direction; the message tells the user to rerun)

### Goal-achievement risk: low
- The end-to-end server-race tests depend on the installed git's receive-pack wording, so a fixed expectation would fail on older installs (2.39.2 says `failed to update ref`) even though production behaves as designed · severity: low (residual: handled in the plan) · → mitigation: none (the plan already does this: expectations branch on the probed reason, unknown wordings fail explicitly, and t2134a' pins both statuses on every machine)

## Post-Review Changes

### Change Request 1 (2026-10-25 06:05)
- **Requested by user:** the t2134a ambiguous-destination fixture assertion and its old-classifier control read git's localized `error:` lines, so `LANGUAGE=de LC_ALL=en_US.utf8 bash tests/test_verified_update.sh` failed 2 assertions (229/231) although production classification was correct.
- **Changes made:** t2134a's fixture pushes (`t2134_push`, the missing-remote push) now run under `LC_ALL=C LANGUAGE=''`. Added a conditional locale-independence check: the non-fast-forward and ambiguous-destination pushes are repeated under `LANGUAGE=de LC_ALL=en_US.UTF-8`; where git really translates (output differs from the C one) the classifier must still retry the first and not the second, otherwise a "not exercised" line is printed. Result: 233/233 in both the default and the German locale; usage suite 100/100 under German; red copy still fails the same 7 t2134 assertions.
- **Files affected:** tests/test_verified_update.sh

## Final Implementation Notes
- **Actual work done:** All five plan steps as written. `is_retryable_push_error` now matches only git's ` ! [rejected] … (fetch first|non-fast-forward)` and ` ! [remote rejected] … (incorrect old value provided)` status lines; every other failure reaches the existing `die "Failed to push metadata update: $push_output"` on the first attempt. Retry exhaustion now appends `Last push error: <git output>` via the new `AIT_LAST_PUSH_OUTPUT` global (reset per `commit_metadata_update` call). Fixture helpers in `tests/lib/metadata_update_fixture.sh`: `mdfix_install_refusing_pre_receive`, `mdfix_install_server_race_pre_receive`, `mdfix_write_attempt_counter_hook`, `mdfix_server_race_reason`, plus the shared end-to-end checks `mdfix_check_push_refusal` / `mdfix_check_server_race` (used by both entry-point test files; documented as needing asserts.sh). Tests: `test_verified_update.sh` t2134a/a'/b/c/d, `test_usage_update.sh` t2134b-usage/c-usage.
- **Deviations from plan:** The end-to-end refusal/race assertions were placed in the shared fixture as `mdfix_check_*` functions rather than duplicated per file. Post-review: fixture pushes pinned to `LC_ALL=C` and a conditional locale-independence check added (see Post-Review Changes).
- **Issues encountered:** A pre-receive hook cannot `git update-ref` (quarantine forbids it), so the server-side race is produced by a nested push from inside the hook with the outer receive-pack's `GIT_*` environment unset — deterministic, no sleeping. Plan-review concern: the server-race wording depends on the installed receive-pack (`failed to update ref` on e.g. 2.39.2), so every real-server race expectation branches on `mdfix_server_race_reason`, with unknown wordings failing explicitly; t2134a' pins both wordings independently of the installed git. On this machine (git 2.56.0) only the `incorrect old value provided` branch is exercised end to end.
- **Key decisions:** Anchor on the ref-status line rather than the narrowed word list the task suggested — a probed hook printing `non-fast-forward fetch first rejected` would have defeated a word match (hook text arrives as `remote: …` lines, which can never start with ` ! [`). The status-line tags/reasons are not localized, so the classifier is also locale-independent (pinned where a German catalog exists). The older `(failed to update ref)` status is deliberately not retried: it also covers non-race failures, and the non-exhaustive list fails closed.
- **Verification:** `test_verified_update.sh` 233/233 (default and `LANGUAGE=de LC_ALL=en_US.utf8`), `test_usage_update.sh` 100/100 (both locales), `test_verified_update_flags.sh` 19/19, `shellcheck -S warning` clean on all four files. Red proof in a scratch tree copy with the pre-fix regex: 7 t2134 failures in the verified suite, 3 in the usage suite.
- **Upstream defects identified:** None
