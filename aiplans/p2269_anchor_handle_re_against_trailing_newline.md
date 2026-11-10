---
Task: t2269_anchor_handle_re_against_trailing_newline.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: anchor artifact/attachment validator regexes against a trailing newline (t2269)

## Context

`HANDLE_RE`, `HASH_RE` and `BACKEND_RE` in `.aitask-scripts/lib/artifact_manifest.py:58-60`
end in `$`. In Python, `$` also matches just before a final `\n`, so
`HANDLE_RE.match("art:a\n")` succeeds. These regexes are the only gate on
untrusted handle/hash/backend values, and two of the consumers build **file paths**
from the validated value:

- `manifest_path()` (artifact_manifest.py:71-78) → `art:a\n` becomes the filename `a\n.json`.
- `attachment_meta.meta_path()` (attachment_meta.py:48-53, its own copy of `HASH_RE`)
  → `sha256:<64hex>\n` becomes a filename ending in `\n.json`.

The trails consumers (`launch_or_focus_trails`, `trails_app.main --trail`) accept a
newline-terminated handle and pass it on. t2211_10 introduced `_TRAILS_TARGET_RE`
ending in `\Z`, and its grammar-equality test pins the `$`/`\Z` mismatch as a known
difference that should flip once this is fixed.

Fix: end each of these regexes in `\Z` instead of `$`. Every consumer keeps using
`.match()`, so the change lives in one place per regex, and it follows the
convention that `_TRAILS_TARGET_RE`, `BOARD_TASK_ID_RE` and
`sitrep_refresh._TRAIL_HANDLE_RE` already use.

### Consumer audit (done during planning)

`grep -rn "HANDLE_RE\|HASH_RE\|BACKEND_RE"` over `.aitask-scripts/` and `tests/`:

| regex (definition) | consumer | value source |
|---|---|---|
| `artifact_manifest.HANDLE_RE` | `manifest_path` (every cmd_*), `validate_record` (:104) | argv from `aitask_artifact.sh` / `artifact_manifest.sh`; manifest JSON `handle` |
| | `trail_discovery_cache.manifest_current` (:215) | handles from trail discovery |
| | `agent_launch_utils.launch_or_focus_trails` (:3227) | caller-supplied handle (untrusted) |
| | `agent_launch_utils.parse_trails_focus_request` → `parse_pane_request` (:3045) | tmux pane option, `.strip()`ed first, so a trailing `\n` never reaches the regex. Behaviour is unchanged. |
| | `board/trails_app.py main()` (:1023) | `--trail` argv |
| `artifact_manifest.HASH_RE` | `validate_record` (:114), `check_hash` (:203) | argv; manifest JSON `versions` |
| `artifact_manifest.BACKEND_RE` | `validate_record` (:121), `cmd_set_backend` (:259) | argv; manifest JSON |
| `attachment_meta.HASH_RE` (:40, separate copy) | `meta_path` (:49) | argv from `attachment_meta.sh` |
| `artifact_registry.BACKEND_RE` (:44, separate copy "artifact_manifest.py shape") | `registered_backends` (:105), `cmd_default_backend` (:188) | YAML keys/values from project config |

No legitimate caller depends on the `$` tolerance:
- Shell callers pass values as argv built by `$(…)`, which strips trailing newlines.
- YAML and JSON parse to exact strings.
- The pane-request path strips its input first.

So a value with a trailing `\n` reaching any of these regexes is malformed input, and refusing it is the intended behaviour. The bash-side `grep -E` checks are line-based and are a different issue, so they are out of scope.

## Implementation steps

1. **`.aitask-scripts/lib/artifact_manifest.py:58-60`.** Replace the trailing `$` with `\Z` in
   all three regexes:
   ```python
   HANDLE_RE = re.compile(r"^art:[a-z0-9][a-z0-9._-]{0,127}\Z")
   HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}\Z")
   BACKEND_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}\Z")
   ```
   Add a one-line comment above them: `\Z`, not `$`, because `$` also matches
   before a final newline and these regexes gate untrusted values that become
   file names.

2. **`.aitask-scripts/lib/attachment_meta.py:40`.** Change `HASH_RE` to the same `\Z` form.

3. **`.aitask-scripts/lib/artifact_registry.py:44`.** Change `BACKEND_RE` to the same `\Z` form.
   It is documented as "artifact_manifest.py shape", so keep the two in step.

4. **`tests/test_trails_focus_writer.py:331-333`.** Flip the special case in
   `test_the_target_grammar_is_the_handle_and_task_id_grammars`:
   - Drop the "one deliberate difference" comment and the `assertTrue(HANDLE_RE.match("art:a\n"))`.
   - Add `"art:a\n"` to the `handles` list, so the existing equality loop asserts that both grammars refuse it.
   - Add an explicit `assertIsNone(HANDLE_RE.match("art:a\n"))`.

5. **New test `tests/test_validator_regex_trailing_newline.py`** (unittest, temp dirs).

   **Fixture rule.** The old code already refuses some of these values for unrelated reasons:
   - an absent `a\n.json` file;
   - a filename that disagrees with the handle;
   - an unregistered default backend.

   So each refusal case is built so that the OLD code ACCEPTS it, and the only remaining refusal is the anchor:
   - Malformed manifests are written under their matching malformed filename (`a\n.json`, which Linux allows).
   - Where some other check would still refuse the value, the test asserts the specific new diagnostic rather than a bare refusal.

   Cases (ids used in the table below):
   - **R1–R5 regex level.** For each of manifest `HANDLE_RE`, `HASH_RE` and `BACKEND_RE`, `attachment_meta.HASH_RE` and `artifact_registry.BACKEND_RE`:
     - `Rn.ok`: `.match(valid)` is truthy;
     - `Rn.nl`: `.match(valid + "\n")` is None.
   - **M1 `manifest_path`.** `manifest_path(tmp, "art:a\n")` raises SystemExit (M1.nl). `manifest_path(tmp, "art:a")` is `tmp/a.json` (M1.ok).
   - **M2 CLI `create` (subprocess `sys.executable artifact_manifest.py --manifest-dir <tmp> create …`).**
     - M2.handle: `create "art:a\n" <H>` exits non-zero, stderr contains `invalid handle`, and `tmp` stays empty. The old code exits 0 and writes `a\n.json`.
     - M2.hash: `create art:a "<H>\n"` exits non-zero, stderr contains `invalid hash`, and `a.json` is absent. The old code exits 0 and writes a record whose `versions` holds the newline value.
     - M2.ok: `create art:a <H>` exits 0 and writes `a.json`.
   - **M3 `manifest_violation`.** Each fixture is otherwise valid and written so the old code returns None:
     - M3.handle: `tmp/a\n.json` with `handle: "art:a\n"`. The violation names `invalid handle`. Before the fix filename agreement holds, so the old code reports nothing.
     - M3.hash: `tmp/a.json` with `current` and `versions[0]` both equal to `<H>\n` (so `current in versions` holds). The violation names `invalid version hash`.
     - M3.backend: `tmp/a.json` with `backend: "local\n"`. The violation names `invalid backend name`.
     - M3.ok: the clean record gives None.
   - **A1 `attachment_meta.meta_path`.** `meta_path(tmp, H + "\n")` raises SystemExit (A1.nl). `meta_path(tmp, H)` is the sharded path (A1.ok).
   - **G1 `artifact_registry`.**
     - G1.reg: `registered_backends({"artifacts": {"backends": {"local\n": {}}}}, p)` raises SystemExit. The old code returns the mapping.
     - G1.ok: the `"local"`-keyed variant returns the mapping.
     - G1.default: `cmd_default_backend` with `default_backend: "local\n"` and no backends raises SystemExit, and the captured stderr contains `is not a valid backend name`. The old code also dies, but with `is not registered`, so the assertion is on the diagnostic, not the refusal.
   - **T1 `trail_discovery_cache.manifest_current`.**
     - T1.nl: seed `tmp/a\n.json`, a valid manifest with `handle: "art:a\n"` and `current: <H>`. `manifest_current("art:a\n", tmp)` is None; the old code returns `<H>`.
     - T1.ok: seed `tmp/a.json` (`art:a`, `<H>`). `manifest_current("art:a", tmp) == <H>`.
   - **L1 `launch_or_focus_trails`.** Patch `agent_launch_utils._TMUX.run` with a mock returning `(1, "")`.
     - L1.nl: `launch_or_focus_trails("s", root, "art:a\n")` returns `(False, msg)` with `msg` starting `invalid trail handle`, and the mock is never called. The old code calls tmux and returns `tmux list-panes failed`.
   - **P1 `trails_app.main`.** Put `.aitask-scripts/board` and `lib` on `sys.path` as `tests/test_board_fixture_harness.py` does. Patch `trails_app.TrailsApp` with a stub whose constructor raises a sentinel `_Booted`, so no case can start the app, the pre-fix run included.
     - P1.nl: `main(["--trail", "art:a\n"])` raises `SystemExit(2)` and stderr contains `invalid trail handle`. The old code reaches the stub and raises `_Booted`.
     - P1.ok: `main(["--trail", "art:a"])` raises `_Booted`, which proves validation passed.
   - **F1–F3, `tests/test_trails_focus_writer.py` (step 4).**
     - F1 is removed: `assertTrue(HANDLE_RE.match("art:a\n"))`.
     - F2 is new: `assertIsNone(HANDLE_RE.match("art:a\n"))`.
     - F3 is `"art:a\n"` added to the `handles` list. The equality subtests then compare the two grammars on it.

6. **Pre-fix control, classified per assertion.**
   - Write the tests first and run them against the unmodified regexes, then apply steps 1–3 and re-run.
   - Classes: **D** = defect demo (red before the fix, green after); **C** = pre-existing assertion whose contract this task changes; **P** = already-correct behaviour pinned (green both); **S** = supporting/self-test (green both).

   | assertion | class | baseline | after |
   |---|---|---|---|
   | R1.nl–R5.nl | D | red | green |
   | R1.ok–R5.ok | P | green | green |
   | M1.nl, M2.handle, M2.hash | D | red | green |
   | M1.ok, M2.ok | P | green | green |
   | M3.handle, M3.hash, M3.backend | D | red | green |
   | M3.ok | P | green | green |
   | A1.nl | D | red | green |
   | A1.ok | P | green | green |
   | G1.reg | D | red | green |
   | G1.default (diagnostic) | D | red (old diagnostic is "not registered") | green |
   | G1.ok | P | green | green |
   | T1.nl | D | red (old returns `<H>`) | green |
   | T1.ok | S | green | green |
   | L1.nl | D | red | green |
   | P1.nl | D | red (`_Booted`) | green |
   | P1.ok | S | green | green |
   | F1 `test_trails_focus_writer.py:333` | C (removed) | green | n/a (would be red after the fix) |
   | F2, F3 subtests | D | red | green |
   | `test_trails_focus_writer.py:334` `_TRAILS_TARGET_RE.match("art:a\n")` is None | P | green | green |

   - **Acceptance:** the set of failing assertions on the baseline equals the D set exactly, and every assertion is green after the fix.
   - A D-row that comes out green on the baseline means its fixture does not isolate the anchor. It is fixed before proceeding, never reclassified.
   - Pre-existing literals: `grep` over `tests/` for newline-terminated `art:` / `sha256:` literals found only `test_trails_focus_writer.py:333-334` (F1 and the P row above). No other existing assertion is expected to change.
   - The two runs' failing-description sets are recorded verbatim in Final Implementation Notes.

7. **Side observation to settle during implementation, not to fix here.** `cmd_create` (artifact_manifest.py:207-217) never checks its `backend=` kv against `BACKEND_RE`, unlike `cmd_set_backend`. Check whether the shell wrapper validates it. If nothing does, record it under "Upstream defects identified" for a Step 8b follow-up.

## Verification

- `python3 -m pytest tests/test_validator_regex_trailing_newline.py tests/test_trails_focus_writer.py -q` (or the unittest equivalent).
- `bash tests/test_artifact_manifest_lib.sh`, `bash tests/test_attachment_meta_lib.sh`,
  `bash tests/test_artifact_dir_backend.sh`, `bash tests/test_artifact_gitbranch_backend.sh`. These are existing regressions for the touched libs.
- `python3 -m pytest tests/test_trail_discovery_cache.py tests/test_settings_artifacts_tab.py tests/test_linked_trail_jump.py -q`.
- `bash tests/run_all_python_tests.sh` with `set -o pipefail`; read the final `PYTHON SUITE:` line.

## Step 9 (Post-Implementation)

Commit the code as `bug: Anchor artifact/attachment validator regexes with \Z (t2269)`, then consolidate the plan, archive it, and push, per the task-workflow Step 9.

## Risk

### Code-health risk: low
None identified. The change is a one-token regex anchor edit in three files. All consumers keep `.match()`. The consumer audit above found no caller that relies on the `$` newline tolerance.

### Goal-achievement risk: low
None identified. Every regex and consumer the task names, plus the two duplicate copies (`attachment_meta.HASH_RE`, `artifact_registry.BACKEND_RE`), gets the fix and a per-consumer regression case with a pre-fix control. The t2211_10 grammar-equality test is flipped as requested.
