---
Task: t2236_tmux_gateway_force_utf8_client.md
Base branch: main
Output branch: main
---

# t2236: force a UTF-8 tmux client (`tmux -u`) in the Python and shell gateways

## Context

When the tmux **client** process has no UTF-8 locale, tmux rewrites every
non-printable or non-ASCII byte in command output to `_`. The client's locale
decides this, not the server's. The rewrite hits the TAB in
`_SESSION_LIST_FORMAT` (`lib/agent_launch_utils.py:1292`): every session name
gains a trailing `_` and `discover_aitasks_sessions()` returns `[]`. Non-ASCII
paths are mangled too (`prój` comes back as `pr_j`).

- Python is exposed under `LC_ALL=C` / `POSIX` or a non-UTF-8 named locale.
  With no locale set at all, PEP 538 coercion hides the bug.
- Shell callers are exposed whenever the locale is unset.

The Go port (aitasks_go t103) now passes `tmux -u` on every invocation. This
task brings the two gateways, which the Go port follows, into line with it.

`-u` is a client flag. It never leaks into the environment of the panes tmux
creates, and it needs no installed `C.UTF-8` locale (macOS has none), so it is
a better fix than forcing `LC_CTYPE`.

## The text model (why `-u` alone is not enough in Python)

With `-u`, tmux speaks **UTF-8 in both directions** whatever the locale. Before,
a locale-less client got only ASCII `_` back, so no Python decoder ever saw a
high byte. Measurements on tmux 3.8 against a private server:

| measurement | result |
|---|---|
| `run` / `run_checked` with `-u` under `LC_ALL=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0` (preferred encoding ASCII, fs encoding `ascii`) | **uncaught `UnicodeDecodeError`**: `text=True` decodes with the locale codec |
| `TmuxControlClient.request` (`monitor_core.py:1647`) | writes `cmd_line.encode("utf-8")`, which is strict |
| invalid UTF-8 in a pane cwd / option (`b\xffd`) | format output passes the raw `\377` through (`#{pane_current_path}`, `@aitask_project_root`) |
| invalid UTF-8 printed into a pane | `capture-pane -p` already substitutes U+FFFD |
| `'#{a}\t#{b}'` in single quotes | tmux keeps a literal backslash-t, not a TAB |

`os.fsdecode` (an earlier draft of this plan) is wrong for this. Under an `ascii`
fs encoding it turns *valid* UTF-8 such as `prój` into surrogates. Text
consumers then crash: `monitor.concern_parser.concern_block_signature` calls
`normalized.encode("utf-8")`, and the control channel's
`request()` strict-encodes a surrogate-bearing name. Strings read from tmux are
**tmux text** (screen content, names, formats), not OS data.

**Rule. A tmux string in Python is real Unicode, carried as UTF-8 with
`surrogateescape` on every gateway route, both ways:**

- **Decode** (tmux → Python): `utf-8` + `surrogateescape`, in `run`,
  `run_checked` (stdout and stderr), `run_async`, the control-mode reader and the
  raw readers. Valid UTF-8 is always readable Unicode, so capture-pane text and
  accented names work in every lane. Only a genuinely invalid byte (possible
  only in paths and option values, never in captured screen text) becomes a lone
  surrogate, and it round-trips.
- **Encode** (Python → tmux), with one function, `encode_tmux_wire(s) -> bytes`,
  used by every route (argv elements and control `request()` lines alike, so
  `run_via_control` gives the same result on both paths): **`os.fsencode(s)`
  when that succeeds, otherwise `s.encode("utf-8", "surrogateescape")`.** In
  other words, a string goes out in its native OS bytes unless the OS codec
  cannot represent it (a scope decision; see below). The cases:
  - UTF-8 fs encoding: `fsencode` *is* utf-8 + surrogateescape, so the bytes
    are identical to today.
  - `ascii` fs encoding: an OS string (`os.getcwd()`, ASCII + surrogates)
    encodes natively, and tmux text containing `ï` falls back to UTF-8. A
    *mixed* string (a command embedding both) also comes out right, since
    UTF-8 + surrogateescape maps each surrogate back to its raw byte.

  The argv helper `encode_tmux_argv` keeps an element as `str` whenever its
  wire bytes equal `os.fsencode` (always, on UTF-8 hosts), so the existing
  argv-pinning tests see today's argv. It hands `subprocess` bytes only on the
  fallback. `subprocess` and `asyncio` accept mixed str/bytes argv on POSIX.
  `set_clipboard` stdin is buffer *content*, so it is always UTF-8 +
  `surrogateescape`.
- **Filesystem boundary**: a tmux-text path that is handed to the OS goes
  through a new `tmux_os_path(s)`, defined as
  `os.fsdecode(s.encode("utf-8", "surrogateescape"))`. It returns the same
  `s` under any UTF-8 fs encoding, so normal hosts are unaffected. Under `ascii`
  it yields Python's own OS representation, so `Path(...).is_file()` checks the
  real bytes.
- **Scope of support (user decision, 2026-11-08).**
  - **Fully supported**: UTF-8 locales, and C/POSIX with or without Python's
    UTF-8 mode or coercion. Names, paths, captured text and the control
    channel all round-trip.
  - **Single-byte named locales** (e.g. ISO-8859-1), partially supported:
    - The TAB separator and all ASCII content are fixed.
    - **OS paths keep their native bytes in both directions.** `fsencode`
      succeeds, so `-c <dir>` and path-valued options go out natively, and
      read-back paths reach the OS via `tmux_os_path`. This is no regression:
      today's argv encoded natively too.
    - Captured screen text reads as Unicode.
    - **Exact limitation, documented in policy 5:** a non-ASCII *tmux-text*
      argument, such as a session or window name read back from tmux, whose
      characters all lie inside the locale codec's repertoire (`wïn` under
      Latin-1) is sent in the locale codec rather than UTF-8. So it does not
      round-trip into a `-t` target, a `has-session`, or a control request.
      Characters outside the repertoire (`€`, CJK) fail `fsencode` and are sent
      as UTF-8, so they do round-trip.
      **Consequence:** pane-vote discovery issues `list-panes -t =wïn:`. tmux
      answers "can't find session", which `_checked` classifies as gone. So
      such a session is **silently absent** from discovery, with
      `complete=True`, and a control attach to it fails. A session whose root
      came with `list-sessions` (stamped) is still discovered, but cannot be
      targeted by its name.
    - A string that a gateway caller cannot classify is ambiguous: native OS
      path or tmux text.
  - **Follow-up for full support**: type the OS-path inputs at their builders
    as native bytes, and send everything else as UTF-8. It is recorded under
    `### Planned mitigations` (timing `after`) and created at Step 8d.

## Steps

1. **`.aitask-scripts/lib/tmux_exec.py`**
   - Constants: `TMUX_CLIENT_FLAGS = ("-u",)`, `TMUX_ENCODING = "utf-8"`,
     `TMUX_ERRORS = "surrogateescape"`, each commented with the rule (policy 5).
   - Helpers, each looked up at call time so the test can substitute the old
     behaviour:
     - `decode_tmux_output(b)`;
     - `tmux_text_kwargs()`, which returns
       `{"encoding": TMUX_ENCODING, "errors": TMUX_ERRORS}` for
       `subprocess.run`;
     - `encode_tmux_wire(s)`: `os.fsencode(s)`, or UTF-8 + surrogateescape on
       `UnicodeEncodeError`;
     - `encode_tmux_argv(argv)`: elements already `bytes` pass through; a
       `str` stays `str` when `encode_tmux_wire(a) == os.fsencode(a)`, and
       becomes `encode_tmux_wire(a)` otherwise;
     - `tmux_os_path(s)`.
   - `TmuxClient._argv` → `["tmux", *TMUX_CLIENT_FLAGS, *self._socket_args, *args]`.
   - `_launch` returns `encode_tmux_argv(argv)`. It is the single route for
     `run`, `run_checked`, `run_async`, `spawn`, `set_clipboard` and
     `resize_pane`; verify each one while editing.
   - `new_session_argv`: `base = [exe("tmux"), *TMUX_CLIENT_FLAGS, *self._socket_args, …]`.
     The function still returns `str` elements. Its docstring says the caller
     must `Popen(encode_tmux_argv(argv), env=client.spawn_env())`.
   - `run` / `run_checked`: replace `text=True` with `**tmux_text_kwargs()`.
     `run_async` uses `decode_tmux_output(stdout_bytes)`. `set_clipboard`
     passes `input=` as text with `**tmux_text_kwargs()`.
2. **`.aitask-scripts/monitor/monitor_core.py`** (the control-mode client)
   - `_attach_argv` → `["tmux", *TMUX_CLIENT_FLAGS, *self._socket_args, "-C", "attach", …]`;
     `start()` spawns `*encode_tmux_argv(self._attach_argv())`.
   - The reader (~1572) uses `decode_tmux_output`.
   - `request()` (~1647) builds the line **per argument**: `b" ".join(
     encode_tmux_wire(_quote_arg(a)) for a in args) + b"\n"`. Each argument
     keeps exactly the wire bytes it would get as a subprocess argv element.
     `_quote_arg` adds only ASCII quote and backslash characters, which encode
     identically under any codec.
     - Encoding the joined line once is wrong: a single non-encodable argument
       (`=€:` under Latin-1) would push the whole line to UTF-8 and silently
       re-encode an unrelated native OS-path argument in the same command (a
       reviewer reproduction against a private server stored
       `b"/tmp/pr\xc3\x83\xc2\xb3j"` through control and `b"/tmp/pr\xc3\xb3j"`
       through subprocess).
     - Extract the line builder as a pure function `_control_line(args) ->
       bytes` so it is unit-testable. The control route and the
     subprocess route of `run_via_control` then produce and accept the same
     strings.
3. **Discovery filesystem boundary** (`lib/agent_launch_utils.py`)
   - Wrap the three tmux-sourced path entry points in `tmux_os_path`:
     `_registered_root(value)` (the stamp), `_pane_vote` →
     `Path(raw_path)` (pane cwd), and `_registry_entry_from_output`
     (`AITASKS_PROJECT_<s>`).
   - `new-session`: `Popen(encode_tmux_argv(tmux_cmd), …)`. Its stderr
     `.decode()` (~2132) becomes `decode_tmux_output`.
   - **Consumer audit** while implementing:
     - grep the other `#{pane_current_path}` consumers
       (`agent_freeze.py:140`, `agent_frozen_ops.py:356`,
       `monitor_core.py:4996`) and convert every **filesystem** use to
       `tmux_os_path`;
     - leave uses that only go back to tmux or into records/display as tmux
       text;
     - grep `.decode(` / `text=True` near tmux spawns under `.aitask-scripts/`
       and convert every reader of tmux output (non-tmux subprocesses are out
       of scope);
     - list each converted site in the archived plan.
4. **Python ambient `$TMUX` self-probes** (allowlisted raw spawns)
   - `codebrowser_app.py:484,505`, `stats_app.py:247`,
     `minimonitor_app.py:6679` and `monitor_app.py:4140` each get
     `*TMUX_CLIENT_FLAGS` after `"tmux"` **and** `**tmux_text_kwargs()` in
     place of `text=True`. Without the second change, `-u` turns a mangled
     session name into an uncaught `UnicodeDecodeError` at TUI startup: these
     probes catch only `OSError` / `TimeoutExpired`.
   - `monitor_app.py:116` (`rename-window`, no output) gets the flag too, so
     the rule has no exceptions to remember.
   - Import from `tmux_exec`. `stats_app` reaches `lib/` through
     `lib.tui_switcher`, so place its import after that one.
5. **`.aitask-scripts/lib/tmux_exec.sh`**
   - Add `AIT_TMUX_CLIENT_FLAGS=(-u)` (with a mirror comment).
   - `ait_tmux`: `_argv=(tmux "${AIT_TMUX_CLIENT_FLAGS[@]}")`.
   - `ait_tmux_legacy`: `command tmux "${AIT_TMUX_CLIENT_FLAGS[@]}" -L default "$@"`.
   - New emitter **`ait_tmux_client_args`**: the client flags, then
     `ait_tmux_socket_args`, one argument per line, for `exec` / compound
     sites. The two `*_socket_args` emitters stay pure, because they are
     parity-pinned with Python's `tmux_socket_args()`.
   - Update the header usage example to `exec tmux $(ait_tmux_client_args) attach …`.
   - The shell has no decoding step: bytes pass straight through.
6. **Shell `exec` / ladder sites**
   - `aitask_ide.sh:93`: `_IDE_SOCK_ARGS` comes from `ait_tmux_client_args`
     (exec sites 181/191/230).
   - `aitask_ide.sh:207`: `_IDE_LEGACY_ARGS=("${AIT_TMUX_CLIENT_FLAGS[@]}")`
     before its read loop.
   - `lib/terminal_compat.sh:207`: `ait_tmux_new_session_persistent` reads
     `sock` from `ait_tmux_client_args`, so all 3 rungs get `-u`.
   - `-u` on interactive `attach` is deliberate. It assumes a UTF-8 terminal,
     which is what every framework TUI already emits; without it, a client with
     no locale draws every glyph as `_`.
   - **Unchanged:** `aitask_companion_cleanup.sh` (raw by design). It reads
     only pane ids and empty/non-empty values with a `|` separator, so mangling
     cannot change any decision, and its call shapes are pinned by
     `test_cleanup_rule_parity.sh`. Record this exception in the doc.
7. **`aidocs/framework/tmux_gateway.md`**
   - New policy **"5. Client UTF-8 and the tmux text model"**: the task's
     measured locale table, the measurement table above, the rule (decode,
     encode, filesystem boundary, scope of support), why `-u` beats
     `LC_CTYPE`, and why `os.fsdecode` is wrong. It also states the **exact
     single-byte-locale limitation**, verbatim from "Scope of support": which
     arguments it hits, which it spares (OS paths, characters outside the
     repertoire), and that it was a scope decision. It names the follow-up
     task id (back-filled at Step 8d), and says that the codec-level evidence
     is pinned by the unit table rather than by a live lane on hosts without
     such a locale.
   - Gateway-surface entries for the new constants and helpers and for
     `ait_tmux_client_args`.
   - Checklist lines:
     - never use `text=True` / `.decode()` / `.encode()` on tmux I/O — use the
       helpers;
     - convert a tmux path with `tmux_os_path` before touching the filesystem;
     - a caller that `Popen`s a gateway argv wraps it in `encode_tmux_argv`;
     - `exec` sites use `ait_tmux_client_args`;
     - in shell formats, the TAB separator is a real byte (`$'\t'`).
   - Rename "four centralized policies" to five, and note the companion-cleanup
     exception.
8. **Test audit and unit tests**
   - `tests/test_tmux_exec.py`:
     - add `-u` to the exact-argv asserts (lines ~155, 168, 295, 342,
       381–416, 563–578);
     - add asserts that `-u` precedes the socket flag in `_argv`, in both
       rungs of `new_session_argv` and in `_attach_argv`;
     - patched `subprocess.run` / `create_subprocess_exec` return
       `b"w\xc3\xafn\tpr\xc3\xb3j/b\xffd\n"`. For `run`, `run_checked`,
       `run_async`, check `stdout == "wïn\tprój/b\udcffd\n"`, i.e. readable
       Unicode with the invalid byte round-tripping. `run` / `run_checked`
       must pass `encoding`/`errors`, not `text=True`;
     - `encode_tmux_wire` / `encode_tmux_argv` table test. Patch `os.fsencode`
       to emulate each codec, so the run is platform-independent:
       - UTF-8: every element stays `str`;
       - `ascii` + surrogateescape: a surrogate OS path stays `str`; `wïn`
         becomes `b"w\xc3\xafn"`; a mixed string yields UTF-8 plus raw bytes;
       - latin-1: an OS path stays native; `wïn` gives `b"w\xefn"` (the
         documented limitation, pinned so a change in it is noticed); `€`
         falls back to UTF-8;
     - `tmux_os_path`: identity under UTF-8; under the patched codecs, a
       native round trip.
     - **Control/subprocess argument parity** (Latin-1, `ascii` and UTF-8
       emulated):
       - with the mixed command `["set-option", "-t", "=€:",
         "@aitask_project_root", os.fsdecode(b"/tmp/pr\xc3\xb3j")]`, every
         argument's bytes inside `_control_line(args)` (minus the ASCII
         quoting) must equal that argument's `encode_tmux_argv` wire bytes;
       - the path argument must be the native `b"/tmp/pr\xc3\xb3j"`;
       - a negative control pins the bug class: encoding the joined line once
         would change the path's bytes under Latin-1.
   - `tests/test_tmux_socket_args_sh.sh`: add `ait_tmux_client_args` cases
     (unset → `-u|-L|ait`; empty → `-u`) and shell↔python parity against
     `[*TMUX_CLIENT_FLAGS, *tmux_socket_args()]`.
   - Run the whole Python suite and the tmux-touching shell tests. Update
     every argv-pinning failure as a **shape-only** change, never a weakened
     assertion.
9. **Regression test: `tests/test_tmux_utf8_client_live.sh`** (new, modelled
   on `tests/test_list_panes_session_scope_live.sh`: private `-L` socket,
   short `TMUX_TMPDIR`, `-f /dev/null`, scratch cwd, trap cleanup, SKIP when
   there is no tmux)
   - **Fixture:** project roots `$TMPROOT/prój` and `$TMPROOT/b<0xff>d` (each
     with `aitasks/metadata/project_config.yaml`), plus the plain non-project
     dir `$TMPROOT/plain`. Sessions:
     - `stamped`: cwd and stamp `prój`;
     - `voted`: cwd `prój`, no stamp;
     - `legacy`: cwd `plain` + global env `AITASKS_PROJECT_legacy` = `prój`;
     - `wïn`: cwd `prój`;
     - `rawb`: cwd and stamp `b<0xff>d`, used only in byte-exact checks.

     A `concern` pane prints a **valid concern block whose text contains
     `prój`**, built from an existing `tests/test_concern_parser*` fixture so
     that the parser's real grammar is used.
   - **Python side: one script, run in probe-selected locale lanes.** Every
     lane runs with `env -u LANG -u LC_CTYPE -u PYTHONUTF8 -u
     PYTHONCOERCECLOCALE` plus `AITASKS_TMUX_SOCKET`. Nothing about locales or
     Python's encodings is assumed: Python on macOS uses UTF-8 as its
     filesystem encoding whatever the locale, and locale names vary by
     platform.
     - **Probes**, independent of the code under test:
       - `locale -a` picks the baseline UTF-8 locale (the first of `C.UTF-8`,
         `C.utf8`, `en_US.UTF-8`, `en_US.utf8`) and a single-byte one (an
         `ISO-8859-1` / `iso88591` name);
       - before each lane, a separate bare
         `python -c 'import sys; print(sys.getfilesystemencoding(), sys.flags.utf8_mode)'`
         runs in that lane's exact env and reports the lane's **actual** fs
         encoding;
       - a raw `tmux` probe without `-u`, in the same env, shows whether this
         tmux mangles the TAB under that locale.
     - **Lanes:**
       - **L0**: the probed UTF-8 locale, or `SKIP-LANE` when there is none;
       - **L1**: `LC_ALL=C`;
       - **L2**: `LC_ALL=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0`;
       - **L3**: the probed single-byte locale with `PYTHONUTF8=0`, or
         `SKIP-LANE` (none is installed on this host).
     - **Conditional checks** are keyed on the probed facts, never on lane
       names:
       - the generic checks below run in every lane;
       - the ascii-specific assertions and control B run only where the probe
         reported fs encoding `ascii`. Elsewhere (e.g. macOS L2) the lane
         prints `LANE-NOTE: fs=<enc>, ascii checks n/a` and still runs every
         generic check;
       - control A expects mangling only where the raw probe showed that this
         tmux mangles under that locale;
       - the L3-only checks pin the documented limitation.
     - The **expected CHECK count** per lane is computed on the shell side from
       those probe results, never self-reported by the script.

     Expected names and paths arrive as hex bytes in env, so no lane depends on
     its own codec to set up its expectations.

     **Expectations come from the probed codec, never from the lane name.** A
     named single-byte locale can coexist with a UTF-8 fs encoding, as on
     macOS. For each fixture name, the script computes
     `limited(name) = (os.fsencode(name) succeeds) and (os.fsencode(name) !=
     name.encode("utf-8"))`, using Python's codec directly and never the
     gateway's helpers, so the oracle is independent of the code under test.
     From that predicate and the accepted contract:
     - **expected discovered set** = every fixture session except an
       unstamped `limited` one, with `complete=True` either way. A stamped
       `limited` session would still be discovered; no fixture is stamped
       *and* limited, and this is noted in the test;
     - **expected targeting** (has-session, list-panes, control attach and
       request): success for non-`limited` names, failure for `limited`
       names;
     - **unconditional in every lane**: the path checks (byte-exact roots and
       `is_dir`), the native-directory check, captured text, the separator,
       and the control-line parity on a live `set-option` (the stored stamp's
       bytes read back via subprocess equal the native path for a command
       sent over control).

     Under UTF-8 and `ascii` codecs no name is `limited`, so this reduces to
     "all 5 discovered, all targetable". Under a real Latin-1 codec, `wïn` is
     expected absent and untargetable; a `€wn` fixture session (outside the
     repertoire) is added so that the UTF-8 fallback is exercised live.

     Each lane CHECKs:
     - **Full discovery**: `discover_aitasks_sessions()`, `_async()` and
       `_checked()` (complete = True) return exactly the expected discovered
       set;
       `s.session.encode("utf-8", "surrogateescape")` equals the expected name
       bytes, `os.fsencode(s.project_root)` equals the expected root bytes, and
       `s.project_root.is_dir()` holds.
     - **Argument round trip**: each fixture name is read back from
       `list-sessions`. Through `run`, `run_checked` and `run_async`,
       `has-session -t session_target(name)` gives the expected targeting
       result, and on success `list-panes -t session_scope_target(name) -F
       '#{pane_current_path}'` returns the byte-identical path.
     - **Control channel**: attach a `TmuxControlClient` to `wïn` (and to
       `€wn` where present). Where targeting is expected to succeed,
       `request(["display-message", "-p", "-t", session_scope_target(name),
       "#{session_name}"])` returns `name` exactly, with no
       `UnicodeEncodeError` in any lane; where it is expected to fail,
       `start()` returns False without raising. Then, over control, send
       `set-option -t <ASCII session> @aitask_t2236_probe <native non-ASCII
       path>` with a `=€wn:`-style non-encodable sibling argument in the same
       lane, and confirm via subprocess `show-options` that the stored bytes
       equal the native path.
     - **Captured screen text**: `capture-pane -p` on the `concern` pane (via
       `client.run` and via the monitor's own capture path) is fed through
       `concern_parser.concern_block_signature`. The call does not raise and
       returns a non-`None` signature, identical across lanes. The captured
       text contains `prój` as readable Unicode.
     - The raw `list-sessions -F _SESSION_LIST_FORMAT` has exactly one real
       TAB per row.
     - **Native start dir**: create a session via `new_session_argv(…,
       cwd=os.fsdecode(<prój bytes>))` and `Popen(encode_tmux_argv(…),
       env=client.spawn_env())`. Its `#{pane_current_path}` read back must be
       byte-identical. This proves OS-path args keep native bytes in every lane,
       including L3.
     - **Limitation pin** (wherever some fixture name is `limited`, keyed on
       the codec): the `limited` names fail targeting and are absent from
       discovery exactly as expected, while ASCII and `€wn` succeed. A change
       in the limitation therefore fails the test until the doc is updated.
     - **Control A** (`-u`): set `tmux_exec.TMUX_CLIENT_FLAGS = ()`. Where the
       raw probe showed mangling, sync discovery is then wrong (`[]` or an
       inexact root); where it did not (e.g. L0), discovery stays correct.
       Restore.
     - **Control B** (the text model; only where fs encoding is `ascii`):
       substitute the old behaviour —
       `tmux_text_kwargs` returns `{"text": True}` and `encode_tmux_argv` is
       the identity. Sync discovery must raise `UnicodeDecodeError`. Separately,
       a `request()` encoder with strict `utf-8` plus `fsdecode`-decoded names
       raises `UnicodeEncodeError`. That reproduces the reviewer's finding and
       shows why the plan rejects `fsdecode`. Restore.
     - Assert the CHECK-line count per lane, to guard against a Python side
       that printed nothing.
   - **Shell side** (`env -i` with only `PATH`/`HOME`/`TMUX_TMPDIR`, no locale
     at all):
     - source `lib/tmux_exec.sh` and run `ait_tmux list-sessions -F
       "#{session_name}"$'\t'"#{@aitask_project_root}"`. The separator is a
       real TAB byte. Compare bytes with `od` to show that every row holds 0x09
       and the exact `ó` bytes;
     - control: with `AIT_TMUX_CLIENT_FLAGS=()`, the TAB becomes `_`;
     - `ait_tmux_client_args` emits `-u` followed by the socket args.

### Step 9 (Post-Implementation)

Commit the code (`bug: … (t2236)`) and the plan separately, then archive via
task-workflow Step 9.

## Verification

- `bash tests/test_tmux_utf8_client_live.sh`: every applicable check passes in
  every lane that ran. On this Linux host that is L0/L1/L2 with fs encoding
  `ascii` in L2; L3 is SKIP-LANE because no Latin-1 locale is installed.
  Control A sees mangling wherever the raw probe predicts it, and control B
  sees the old decode crash and the fsdecode/strict-encode crash.
- Portability self-check of the test, run once by hand: re-run it with the
  fs-encoding probe forced to report `utf-8` for L2 (an env knob local to the
  test, e.g. `T_FORCE_FS_PROBE=utf-8`). It must take the macOS-shaped branch:
  print `LANE-NOTE`, skip the ascii checks and control B, still pass the
  generic checks, and still match its computed CHECK count.
- `bash tests/test_tmux_socket_args_sh.sh`, `bash tests/test_no_raw_tmux.sh`,
  `bash tests/test_list_panes_session_scope_live.sh`,
  `bash tests/test_tmux_persistent_scope.sh`,
  `bash tests/test_tmux_spawn_path_live.sh`, `bash tests/test_tmux_run_parity.sh`,
  `bash tests/test_cleanup_rule_parity.sh`.
- `bash tests/run_all_python_tests.sh`: read the verdict from the last line,
  using `set -o pipefail` if piping.
- `shellcheck .aitask-scripts/lib/tmux_exec.sh .aitask-scripts/lib/terminal_compat.sh .aitask-scripts/aitask_ide.sh`.

## Risk

### Code-health risk: medium
- Test doubles or argv-pinning tests that index tmux's positional argv (`$1 == -L`) break on the new leading `-u` · severity: low · → mitigation: covered by plan step 8 (full-suite sweep; shape-only updates)
- Converting a tmux path for the filesystem is a per-consumer duty. A missed consumer (one beyond the discovery entry points) under an `ascii` fs encoding gets `False` / `UnicodeEncodeError` where it used to get a mangled `_` path · severity: medium · → mitigation: covered by plan step 3 (grep-driven consumer audit with a listed result). `tmux_os_path` is the identity on UTF-8 hosts, so only explicitly locale-hostile environments are affected
- The `encode_tmux_argv` mixed str/bytes argv depends on POSIX `subprocess` semantics · severity: low · → mitigation: covered by the L2 live lane, which exercises it through real `subprocess` and `asyncio` spawns

### Goal-achievement risk: medium
- Under single-byte named locales, non-ASCII tmux-text arguments (names read back from tmux) do not round-trip. This is a deliberate partial delivery of the task's "non-UTF-8 named locale" case, decided by the user. OS paths, the separator and captured text are covered · severity: medium · → mitigation: full_native_byte_tmux_typing
- No single-byte locale is installed here, so the L3 lane cannot run on this host; that behaviour is pinned only by the codec-patched unit table · severity: low · → mitigation: covered by plan step 8 (codec-patched `encode_tmux_wire` table) plus the probe-gated L3 lane wherever such a locale exists

### Planned mitigations
- timing: after | name: full_native_byte_tmux_typing | type: enhancement | priority: low | effort: medium | inline_risk: high | added_complexity: high | addresses: single-byte-locale tmux-text round trip | desc: Type the OS-path inputs to the tmux gateway at their builders (launcher argv[0], `-c <dir>`, pane shell commands, path-valued options/env such as @aitask_project_root and AITASKS_PROJECT_<s>) as native bytes, and send all other tmux text as UTF-8, so that non-ASCII names round-trip under single-byte named locales too (removes the policy-5 limitation from t2236)

## Post-Review Changes

### Change Request 1 (2026-11-08 12:25)
- **Requested by user:** `tests/test_tmux_utf8_client_live.sh` built the invalid-UTF-8 `b\xffd` directory unconditionally. APFS (macOS) rejects such a file name, so `set -e` aborted setup before any locale probe or Unicode check ran. Probe for invalid-byte filename support and drop only `rawb` and its dependent expectations and counts, keeping the valid-Unicode checks; invalid-byte codec coverage stays in the unit tests.
- **Changes made:**
  - A `mkdir` probe sets `HAVE_RAWB`. Without support the test prints `SKIP-PART: rawb`, omits the `rawb` session, passes an empty `T_RAWB`, and the Python side drops `rawb` from `NAMES` / `ROOTS`.
  - The shell row count becomes `5 + HAVE_RAWB`, and `GENERIC_CHECKS` becomes `35 + 4 * HAVE_RAWB`.
  - New self-check knob `T_FORCE_NO_RAWB=1` emulates the rejection on Linux.
  - Verified: normal run 131/131; `T_FORCE_NO_RAWB=1` 119/119; plus `T_FORCE_FS_PROBE=utf-8` 117/117.
- **Files affected:** `tests/test_tmux_utf8_client_live.sh`

## Final Implementation Notes
- **Actual work done:**
  - **Every framework tmux client passes `-u`.** Python: `TMUX_CLIENT_FLAGS` in `TmuxClient._argv` (so `run` / `run_checked` / `run_async` / `spawn` / `set_clipboard` / `resize_pane` all get it), `new_session_argv` (all three rungs), the control-mode `_attach_argv`, and the ambient `$TMUX` probes in `codebrowser_app.py` (`#S`, `#{window_index}`), `stats_app.py`, `minimonitor_app.py` and `monitor_app.py` (`#S`, `rename-window`). Shell: `AIT_TMUX_CLIENT_FLAGS` in `ait_tmux` and `ait_tmux_legacy`, plus the new `ait_tmux_client_args` emitter, used by the `aitask_ide.sh` exec sites, the legacy-attach array, and all three rungs of the `terminal_compat.sh` new-session ladder.
  - **The Python text model** (`tmux_exec.py`): `tmux_text_kwargs()` / `decode_tmux_output()` (UTF-8 + surrogateescape); `encode_tmux_wire()` (`os.fsencode`, falling back to UTF-8 + surrogateescape only when the OS codec cannot represent the string); `encode_tmux_argv()` (a `str` element stays `str` unless the encodings differ); `tmux_os_path()`.
  - **The control client** builds its wire line per argument (`monitor_core._control_line`) and decodes with `decode_tmux_output`.
  - **Converted consumer sites** (the plan's step-3 audit result):
    - `agent_launch_utils.py`: `_registered_root`, `_pane_vote`, `_registry_entry_from_output` (`tmux_os_path`); the `new-session` Popen (`encode_tmux_argv`); its stderr decode (`decode_tmux_output`).
    - `agent_freeze.py` `_walk_up_to_project` (`tmux_os_path` on the pane-cwd fact).
    - `monitor_core.py`: `_sitrep_rows` (sitrep root and TUI-root stamps, cwd) and `match_scratchpad_pane` (store key), both via `tmux_os_path`.
    - **Left as tmux text by design:** `_Observed.path` (never read), the `RunIdentity` TUI root (emptiness check only), `aitask_companion_cleanup.sh` (pane ids and emptiness only).
    - Other `text=True` / `.decode(` sites near these files are non-tmux subprocesses (ps, shell helpers), so they are out of scope.
  - **Doc:** `aidocs/framework/tmux_gateway.md` gains policy 5, gateway-surface entries, checklist item 5, the companion-cleanup exception, and the single-byte-locale limitation and its discovery consequence.
- **Deviations from plan:**
  - The audit turned up two more path consumers that the plan had not listed: the sitrep root / TUI-root / cwd matcher, and the scratchpad store-key matcher. Both compare a tmux-read path with a canonical OS root, so they were converted too; without that, L2 would mis-match them.
  - The live test does **not** use a separate `€wn`-style sibling argument inside one `set-option`, because tmux's `set-option` takes exactly option + value. It uses the reviewer's own shape instead: the target `=€wn:` (non-encodable under Latin-1) beside a native OS-path value, in one control command.
  - The fixture uses `set-option -t =<s>:`. On tmux 3.8 `set-option`'s `-t` is pane-typed, and a bare `=<s>` fails with "no such session" (the framework's bootstrap already uses `=<s>:`).
  - Post-review: the APFS probe for `rawb` (see Post-Review Changes).
- **Issues encountered:**
  - `python -I` / `-E` ignore `PYTHONUTF8` / `PYTHONCOERCECLOCALE`, so the first fs-encoding probe misreported L2 as `utf-8`. The probe now runs plain `python -c` in the empty scratch cwd.
  - The new test initially lacked `PASS=0 FAIL=0 TOTAL=0`. An unset `FAIL` makes `[[ "$FAIL" -eq 0 ]]` pass even after failures; this was caught by the empty count in the summary.
  - `printf '%s\n'` with no operands prints an empty line, so the emitter guards an emptied `AIT_TMUX_CLIENT_FLAGS`.
  - Ten test files matched tmux's exact argv or positional verb (`argv[:2] == ["tmux", "list-sessions"]`, `cmd[1] == "display-message"`, a shell shim's `$1`). All were updated shape-only: `test_tmux_exec.py`, `test_discover_include_registered.py`, `test_discover_default_unchanged.py`, `test_codebrowser_detect_tmux_window.py`, `test_monitor_rename_gate.py`, `test_monitor_rename_window_target.sh`, `test_multi_session_monitor.sh`, `test_multi_session_primitives.sh`, `test_session_claim.sh` and `test_tmux_socket_args_sh.sh` (extended).
- **Verification:**
  - **New live test:** `test_tmux_utf8_client_live.sh` passes 131/131 (L0/L1/L2, L2 at fs `ascii`; L3 is SKIP-LANE because no Latin-1 locale is installed). It also passes 129/129 with `T_FORCE_FS_PROBE=utf-8`, 119/119 with `T_FORCE_NO_RAWB=1`, and 117/117 with both.
  - **Mutants**, each in an isolated scratch copy of the repo, all detected:
    - `TMUX_CLIENT_FLAGS = ()`: 38 failures;
    - no `tmux_os_path` in `_pane_vote`: 3;
    - `tmux_text_kwargs` → `text=True`: the lanes crash;
    - whole-line control encoding: the lanes crash;
    - shell `AIT_TMUX_CLIENT_FLAGS=()`: 4.
  - **In-process unit mutants** (4) were all detected. `test_tmux_exec.py` passes 100/100.
  - **Python suite:** final run is `PYTHON SUITE: FAILED`, with one failure: `test_contribution_workflow_contract`. A concurrent session was editing `.github/workflows/contribution-check.yml` during the run; the test passes 6/6 in isolation, and this change touches no `.github` file.
  - **Shell sweep** over every `tests/*.sh` that mentions tmux: 76 OK. Not run: 9 tests that refuse to run inside a tmux session (`test_cleanup_rule_parity`, `test_freeze_engine_live`, `test_frozen_agents_acceptance`, `test_frozen_standin_spike`, `test_monitor_harvest_close_live`, `test_monitor_shadow_spawn_live`, `test_restore_flows_live`, `test_scratchpad_spawn_live`, `test_sitrep_window_hook_live`).
  - **Unrelated failure:** `test_note_with_live_composition` checks rendered task-workflow skill text, which this change does not touch; another session has uncommitted edits to `.claude/skills/task-workflow/`.
  - The `run_all_python_tests.sh` entry in the sweep timed out under the sweep's 240 s cap; it was run separately, as above.
- **Key decisions:**
  - `-u` rather than `LC_CTYPE`.
  - tmux text is real Unicode, never `os.fsdecode` (it breaks text consumers).
  - Encoding is per argument, native-first.
  - Scope (user decision): UTF-8 and C/POSIX fully supported; single-byte named locales partially supported, with a documented limitation and a follow-up (planned mitigation `full_native_byte_tmux_typing`, created at Step 8d).
  - Interactive `attach` also gets `-u`.
- **Upstream defects identified:** None
