---
Task: t1223_2_framework_version_and_upgrade_command_model.md
Parent Task: aitasks/t1223_expand_syncer_scope_version_and_settings_sync.md
Sibling Tasks: aitasks/t1223/t1223_3_version_tab_upgrade_action_and_handoff.md, aitasks/t1223/t1223_4_cross_repo_settings_seam.md, aitasks/t1223/t1223_5_settings_tab_and_push_action.md, aitasks/t1223/t1223_6_syncer_scope_documentation.md, aitasks/t1223/t1223_7_manual_verification_expand_syncer_scope_version_and_settings.md
Archived Sibling Plans: aiplans/archived/p1223/p1223_1_tabbed_syncer_shell.md
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-25 23:32
---

# p1223_2 — Framework version + upgrade-command model (headless) — verified 2026-07-25

> Execution view for `aitasks/t1223/t1223_2_framework_version_and_upgrade_command_model.md`.
> The task file carries the full API signatures and binding contracts (A, B, C, F
> of `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`
> §Safety contracts). This plan revises the pre-existing p1223_2 after
> verification against live source.

## Context

Create `.aitask-scripts/lib/framework_version.py` — pure functions over paths
and strings, no Textual and no tmux calls — so the risky logic
(shell-command construction, self-target detection, active-target detection,
handoff request) is fully unit-tested before any UI consumes it (t1223_3).

## Verification findings (this plan revises the pre-existing p1223_2)

Re-read against live source at `1596a078a`. Findings:

1. **`tui_switcher.KNOWN_TUIS` holds `(name, label, command)` tuples, not bare
   names** (`tui_switcher.py:155` → `tui_registry.switcher_tuis()`). A literal
   "name in KNOWN_TUIS" membership check would never match — the name component
   must be extracted.
2. **Contract C's set is the switcher subset, missing real framework TUIs.**
   The authoritative `tui_registry.TUI_NAMES` (`tui_registry.py:38`)
   additionally classifies `brainstorm`, `minimonitor`, `git`, and
   `BRAINSTORM_PREFIX = "brainstorm-"` windows (`:32`) as framework TUIs. Under
   the literal contract a running brainstorm TUI would not block upgrading its
   repo — the exact mixed-version hazard Contract C exists to prevent.
   **Decision (user-confirmed): widen the busy set** to
   `tui_registry.TUI_NAMES` + `BRAINSTORM_PREFIX` + `agent-`/`create-`
   prefixes. `tui_registry` is a pure-data leaf module, so the defensive-import
   requirement gets *easier*. **AC deviation (explicit):** update the task
   file's Contract C wording in the same commit.
3. **Force-override requested (user).** The upgrade action must offer a FORCE
   option to proceed even when the target is busy ("most times it is still
   safe"). This contradicts parent-plan Contract C's "There is no override
   flag — re-check after closing them." Ownership: the override is **UI
   behavior in t1223_3** — this module's `detect_target_activity` stays a pure
   idle/busy reporter, unchanged. In-scope here (same commit, doc edits):
   - amend parent plan `aiplans/p1223_…md` Contract C: busy set widened per
     finding 2, and "no override flag" → busy refusal is the default but the
     confirm dialog MAY offer an explicit "Force upgrade anyway" acknowledging
     the named live windows;
   - update `aitasks/t1223/t1223_3_version_tab_upgrade_action_and_handoff.md`
     to require the force option in its refusal dialog (so a fresh context
     implementing t1223_3 does not lose the decision).
4. **All other anchors resolve as written:** version regex
   `^[0-9]+\.[0-9]+(\.[0-9]+)?$` + leading-`v` strip with `latest` handled
   separately (`aitask_upgrade.sh:87-89`); `github_release.sh:36-123` functions
   incl. `github_resolve_latest_version <repo>`; `AitasksSession.key` =
   `os.path.realpath` with `str()` fallback (`agent_launch_utils.py:126-141`);
   `resolve_agent_string` subprocess shape (`:232-251`); `get_tmux_windows`
   returns `(index, name)` tuples (`:267`); companion prefixes
   `["agent-", "create-"]` (`:1393` — config-overridable defaults there; this
   module pins the literal defaults per contract); `atomic_write` temp +
   `os.replace` pattern (`attachment_meta.py:65-78`); `tests/test_syncer_rows.py`
   style (unittest, `sys.path.insert`, fixture-only).
5. **`resolve_latest_version` needs a repo + helper seam.**
   `github_resolve_latest_version` takes a `<repo>` argument; `REPO`
   is `"beyondeye/aitasks"` (`aitask_upgrade.sh:9`). Additive keyword-only
   test-seam params beyond the pinned signature:
   `resolve_latest_version(timeout=10.0, *, helper=None, repo=REPO)` —
   `helper` defaults to the module-adjacent `github_release.sh`
   (`Path(__file__).resolve().parent / "github_release.sh"`). Explicit-defaults
   seam, house style; t1223_3 calls it with defaults.

6. **Review findings (user-raised, all verified valid):**
   - *Quoting test split defect:* the task file's "assert via `shlex.split` on
     each `&&` side" is unimplementable for a root containing a literal ` && `
     — splitting the command *string* on the operator cuts through the quoted
     path. Verified fix: `shlex.split` the **whole** command (a quoted path
     containing ` && ` stays one token; the operator is a standalone `&&`
     token), split the **token list** on the `&&` token, assert both argvs
     structurally. Plus execution-based proof: run the stub-`ait` failure-chain
     test from roots that themselves contain the special characters. Task-file
     AC updated accordingly.
   - *Fail-open activity guard:* degrading a `tui_registry` import failure to
     prefix-only matching returns `idle` for a live `board`/`syncer`/
     `brainstorm` window — the safety control silently vanishes. Verified fix:
     three-state return; classifier failure is surfaced, never masked (see
     Step 1 below). Task-file AC (and t1223_3 consumer spec) updated: only
     literal `idle` permits an un-forced upgrade.
   - *Orphaned resolver child:* `github_release.sh:94` `git ls-remote` has no
     time bound (only the curl paths do), and `subprocess.run(timeout=…)` kills
     only the direct `bash` child — a hung git grandchild survives the
     timeout. Verified fix: `start_new_session=True` + process-group kill on
     timeout, with a grandchild-cleanup test.
   - *Force-override underspecified* and *atomic-cleanup untested*: addressed
     in Step 3 and test group 10 below.

## Steps

1. **New `.aitask-scripts/lib/framework_version.py`.** Module docstring states
   the Contract C declared bound (tmux-session-scoped only: an `ait` process in
   an unrelated terminal, a detached process, or another machine sharing the
   checkout is undetectable) and that busy is a refuse-by-default signal whose
   override lives in the UI layer. Constants: `VERSION_RE =
   r"^(latest|[0-9]+\.[0-9]+(\.[0-9]+)?)$"` (compiled), `REPO =
   "beyondeye/aitasks"`, `COMPANION_PREFIXES = ("agent-", "create-")`.

   - `read_installed_version(root)` — read `<root>/.aitask-scripts/VERSION`;
     strip whitespace and one leading `v`; `None` on
     missing/unreadable/blank; never raises.
   - `resolve_latest_version(timeout=10.0, *, helper=None, repo=REPO)` —
     `subprocess.Popen(["bash", "-c", 'source "$1" && github_resolve_latest_version "$2"',
     "bash", str(helper_path), repo], stdout=PIPE, stderr=PIPE, text=True,
     start_new_session=True)`, then `communicate(timeout=timeout)`. On
     `TimeoutExpired`: `os.killpg(os.getpgid(p.pid), SIGKILL)` (fall back to
     `p.kill()` on `ProcessLookupError`/`PermissionError`), drain with a second
     `communicate()`, return `(None, "timeout after …s")` — the process-group
     kill covers the unbounded `git ls-remote` grandchild
     (`github_release.sh:94`), which a plain child kill would orphan. Exit 0 →
     last non-empty stdout line, `v`-stripped, validated against the numeric
     arm of `VERSION_RE` (reject junk with `(None, "unparseable version: …")`).
     Non-zero → `(None, <stderr token or generic reason>)`;
     `FileNotFoundError` / `OSError` → `(None, reason)`. Never raises, never
     leaves a live descendant past `timeout`.
   - `version_status(installed, latest)` — either side `None` → `"unknown"`;
     split on `.`, int() each component (any failure → `"unknown"`), zero-pad
     to equal length (`1.2` == `1.2.0`); compare tuples → `"up_to_date"` /
     `"behind"` (installed < latest) / `"ahead"`.
   - `is_self_target(root, cwd)` — `os.path.realpath` both sides, compare;
     on `OSError` fall back to comparing `str()` of both.
   - `detect_target_activity(session, windows)` — pure; `windows` is
     `list[tuple[str, str]]` of `(index, name)`. **Three-state, fail-closed**
     (AC amendment — review finding): returns `"idle"`,
     `"busy:" + ",".join(offending names in window order)`, or
     `"unknown:tui-registry-unavailable"`. Lazy/defensive import: `try: from
     tui_registry import TUI_NAMES, BRAINSTORM_PREFIX` → busy-names =
     `TUI_NAMES`, prefixes = `COMPANION_PREFIXES + (BRAINSTORM_PREFIX,)`.
     On import failure, prefix matching (`agent-`/`create-`/`brainstorm-`)
     still runs and a hit still returns `busy:<names>`; but with **no** prefix
     hit the function returns `unknown:…`, never `idle` — a classifier failure
     can widen refusal, never narrow it. Consumer contract (t1223_3 spec):
     only literal `idle` permits an un-forced upgrade; `busy` and `unknown`
     both refuse (force-override applies to both, showing the reason).
   - `build_upgrade_command(root, version)` — validate `version` against
     `VERSION_RE` **before any interpolation**, else `ValueError`;
     `q_ait = shlex.quote(str(Path(root) / "ait"))`; return
     `(f"{q_ait} upgrade {version} && {q_ait} setup", [q_ait, version])`.
     The `&&` is load-bearing.
   - `build_handoff_request(root, version)` — validate version (ValueError);
     return exactly `{"root": os.path.abspath(str(root)), "version": version}`.
   - `write_handoff_request(path, request)` — `tempfile.mkstemp(dir=<same
     dir>, prefix=".handoff.")`, write `json.dumps(request)`, `os.replace`;
     unlink the temp on failure (mirror `attachment_meta.atomic_write`).

2. **New `tests/test_framework_version.py`** in `test_syncer_rows.py` style
   (`sys.path.insert` of `.aitask-scripts/lib`, `unittest`, `tempfile.mkdtemp`
   fixture roots — never cwd). The task file's 10 required test groups,
   verbatim:
   1. `read_installed_version`: valid / missing file / missing
      `.aitask-scripts/` dir / blank / whitespace+`v` stripped / chmod-000
      unreadable → `None`, no raise (skip chmod case when running as root).
   2. `version_status` truth table incl. `None` sides and non-numeric
      component; plus `1.2` vs `1.2.0` equal.
   3. `resolve_latest_version` via stub helper files defining
      `github_resolve_latest_version`: success echo → version; exit 1 →
      `(None, reason)`; sleeping stub + small timeout → `(None, reason)`.
      **Grandchild-cleanup (review finding):** stub whose function writes a
      spawned `sleep 60` child's PID to a file then waits on it; after the
      timeout return, assert the PID is dead (`os.kill(pid, 0)` raises,
      polled briefly) — pins the process-group kill.
   4. `is_self_target`: same path; symlink resolving to same realpath → True;
      different path → False; trailing slash → True.
   5. `detect_target_activity` truth table: no windows / plain shells → idle;
      `board` (registry name) → busy naming it; `agent-syncfix-pull` → busy;
      `create-…` → busy; **widened set:** `brainstorm`, `minimonitor`, `git`,
      `brainstorm-42` → busy; mixed → busy listing only offenders in order.
      **Fail-closed classifier (review finding):** with the registry import
      forced to fail (`mock.patch.dict(sys.modules, {"tui_registry": None})`
      or equivalent): `agent-x` window → still `busy`; plain-shell/`board`
      windows → `unknown:…`, **never** `idle` (negative control: this test
      must fail if the fallback returns idle).
   6. `build_upgrade_command` quoting (shell-aware — review finding): roots
      with space, `$`, `;`, ` && `, single quote, double quote, backtick —
      `shlex.split` the **whole** command, split the token list on the
      standalone `&&` token, assert exactly
      `[<root>/ait, "upgrade", version]` and `[<root>/ait, "setup"]` (also
      asserts exactly one operator token). Never splits the raw string.
   7. Rejection: `""`, `"; rm -rf /"`, `"1.2.3; ls"`, `"$(id)"`, `"v1.2.3"`
      → `ValueError`; accepts `latest`, `1.2`, `0.28.0`.
   8. **Failure-chain (load-bearing):** temp dir with stub `ait` executable
      appending `$1` to a log, exit 1 → run built command via
      `subprocess.run(cmd, shell=True)` → log has `upgrade`, no `setup`.
      Exit-0 stub → both, in order. **Executed-quoting variant (review
      finding):** repeat the exit-0 run with stub `ait` installed in roots
      whose directory names contain the test-6 special characters (space,
      `&&`, `$`, single quote, backtick) — proves the real shell parses the
      built command as the intended two invocations of *that* root's `ait`.
   9. `build_handoff_request`: exactly `{"root","version"}` keys, absolute
      root, invalid version raises.
   10. `write_handoff_request`: JSON round-trips; no `.handoff.`/temp residue
      left in the directory. **Failure-injection (review finding):**
      (a) unserializable request (contains a `set()`) → `TypeError` propagates
      AND no temp file remains; (b) `os.replace` failure (target path is an
      existing directory) → raises AND no temp file remains.

3. **Doc/spec edits (same commit set, via `./ait git` for task/plan files):**
   - Task file t1223_2: Contract C section — busy set = `tui_registry.TUI_NAMES`
     + `BRAINSTORM_PREFIX` + companion prefixes; three-state return with
     fail-closed `unknown`; quoting-test AC rewritten to the token-split +
     executed-roots form (explicit AC deviation notes).
   - Parent plan `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`
     Contract C: widened set, three-state `detect_target_activity`, and the
     force-override amendment replacing "There is no override flag".
   - Sibling task file t1223_3 — force-override spec, fully defined (review
     finding): on `busy`/`unknown` the action refuses; the refusal dialog MAY
     be escalated by the user via an explicit **destructive confirmation**
     that (a) re-enumerates windows and re-runs `detect_target_activity`
     **immediately before launch**, aborting the force if the fresh result
     differs from what was shown; (b) lists the freshly-detected window names
     (or the `unknown` reason) verbatim in the dialog body; (c) requires
     selecting a non-default option labeled
     "Force upgrade anyway — I accept the listed windows may break" (default
     focus = Cancel); (d) never persists a "don't ask again" state. Only
     literal `idle` permits an un-forced upgrade.

## Verification

```bash
python3 tests/test_framework_version.py
python3 -c "import sys; sys.path.insert(0,'.aitask-scripts/lib'); import framework_version"
```

Harness falsifiability (repo convention): after green, mutate and re-run —
swap `&&` for `;` in `build_upgrade_command` (test 8 must fail); drop the
`VERSION_RE` check (test 7 must fail); narrow the busy set back to switcher
names (test 5's `brainstorm` case must fail); make the import-failure fallback
return `"idle"` (test 5's fail-closed negative control must fail); replace the
process-group kill with a plain `p.kill()` (test 3's grandchild-cleanup must
fail). Restore by undoing only the mutation — never `git checkout --`.

Then Step 9 (Post-Implementation): merge approval N/A (current branch, fast
profile), gates run (`risk_evaluated` active), archival.

## Risk

### Code-health risk: low
- The module constructs a shell command that rewrites another repo's framework
  files — a quoting/injection defect here becomes arbitrary command execution
  in t1223_3 · severity: medium · → mitigation: covered in-task by tests 6–8
  (structural shlex.split asserts, injection rejection, failure-chain) with
  falsifiability runs
- `REPO` constant duplicates `aitask_upgrade.sh:9` · severity: low · →
  mitigation: accepted (matching the existing hardcode; single-line drift)

### Goal-achievement risk: low
- None identified. The API is pinned by the task file, every source anchor was
  re-verified against live source, and all spec gaps found (tuple-shaped
  KNOWN_TUIS, switcher-subset busy set, string-split quoting test, fail-open
  classifier fallback, orphaned resolver child, untested atomic cleanup,
  underspecified force override) were resolved with the user before planning
  closed.

## Out of scope

Any tmux enumeration or spawning, any UI, and the force-override *behavior*
(t1223_3 — spec updated here, implemented there).

## Final Implementation Notes

- **Actual work done:** Exactly the planned shape, two new files, zero existing
  code files touched. `.aitask-scripts/lib/framework_version.py` (256 lines):
  `read_installed_version`, `resolve_latest_version` (Popen +
  `start_new_session=True`, process-group SIGKILL on timeout, explicit
  `helper=`/`repo=` test seams, output validated against the numeric arm of
  `VERSION_RE`), `version_status` (zero-padded semver tuples),
  `is_self_target` (realpath both sides, str fallback on OSError),
  `detect_target_activity` (three-state fail-closed; busy set =
  `tui_registry.TUI_NAMES` + `agent-`/`create-`/`BRAINSTORM_PREFIX` prefixes,
  imported lazily inside the call), `build_upgrade_command`
  (validate-before-interpolate, `shlex.quote`, load-bearing `&&`, returns
  parts), `build_handoff_request` (exactly `{root, version}`),
  `write_handoff_request` (mkstemp in target dir + `os.replace`, temp
  unlinked on any failure). `tests/test_framework_version.py` (391 lines,
  42 tests) covers all 10 required groups plus the five review-driven
  additions. Spec edits in the same change: t1223_2 Contract C + tests 5/6
  AC amendments, parent-plan Contract C amendment (widened set, three-state,
  force-override), t1223_3 force-override dialog contract.

- **Deviations from plan:** One cosmetic: `VERSION_RE` is the raw string the
  task file pins (not pre-compiled as the plan draft said); matching uses
  `re.fullmatch`, which also hardens against the `$`-before-trailing-newline
  acceptance `re.match` would have had. Everything else landed as planned.

- **Issues encountered:**
  1. Falsifiability mutation 5 (plain `proc.kill()` instead of the
     process-group kill) made the timeout test hang ~60s before failing —
     the orphaned `sleep` grandchild held the stderr pipe open, which is a
     live demonstration of exactly the orphan hazard the review flagged.
  2. The worktree carried unrelated concurrent-session changes
     (`aitask_board.py`, board tests, `t1210_4` task edit on the data
     branch); commits were pathspec-limited to this task's files only.

- **Key decisions:**
  - **Fail-closed `unknown` state** (review-driven): on `tui_registry` import
    failure, prefix hits still return `busy`, but unclassifiable windows
    return `unknown:tui-registry-unavailable` — never `idle`. Consumers gate
    un-forced upgrades on literal `idle`.
  - **Shell-aware quoting assertions:** tests tokenize the whole command with
    `shlex.split` and split the token list on the standalone `&&` token —
    never the raw string, which a quoted root containing ` && ` defeats.
    Backed by executed-quoting tests running stub `ait` binaries from roots
    named with each special character.
  - **Process-group kill** covers the unbounded `git ls-remote` in
    `github_release.sh:94` that a plain child kill would orphan.
  - All five falsifiability mutations were run individually; each made the
    suite fail, and the restored suite is green (42/42).

- **Upstream defects identified:** None

- **Notes for sibling tasks:**
  - t1223_3: only a literal `"idle"` from `detect_target_activity` permits an
    un-forced upgrade; `busy:<names>` and `unknown:<reason>` both refuse. The
    force-override dialog contract (fresh re-check before launch, verbatim
    window list, Cancel-focused destructive confirm, no persisted opt-out,
    never bypasses the self-target rule) is pinned in t1223_3's task file.
  - `resolve_latest_version` accepts keyword-only `helper=`/`repo=` seams;
    production callers use the defaults (module-adjacent `github_release.sh`,
    `beyondeye/aitasks`).
  - `write_handoff_request` does NOT create the target directory — the
    wrapper owns and pre-creates the private handoff dir (Contract B).
  - Reuse `TempDirTestCase.make_root()` and `NASTY_ROOTS` from
    `tests/test_framework_version.py` for any further command-construction
    tests.
