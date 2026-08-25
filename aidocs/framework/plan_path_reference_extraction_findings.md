# Plan path-reference extraction: verified findings

How the framework decides which files a plan "references" — and the ways that
decision is currently wrong. Written as an input to **t1561** (generalize task
staleness detection), whose decision record has to answer the same question for
task premises: *given a task or plan, which files is it about, and have they
changed?*

The single implementation today is the extraction stage of
`.aitask-scripts/aitask_remote_drift_check.sh`:

```bash
grep -oE '[A-Za-z0-9_./-]+\.(sh|py|md|yaml|yml|json|toml)' "$PLAN_FILE" \
  | sed 's|^\./||' \
  | sort -u
```

Its output is intersected with `git diff --name-only <base>..origin/<base>` by
exact full-line match (`grep -Fxf`). The intersection is what makes the stage
safe: a token that is not a real remote-changed path is discarded there. It is
also what makes every finding below a **false negative** — a file the framework
believes the plan does not mention.

Each finding was executed, not reasoned about. The commands reproduce them.

## 1. The extension list excludes most languages

The regex requires one of `sh|py|md|yaml|yml|json|toml`. A plan referencing Go,
Kotlin, Rust, TypeScript, C# or Java sources yields **zero** tokens, so the
drift check is a no-op for those projects' primary sources.

```bash
printf 'We modify `internal/pkg/server.go`.\n' \
  | grep -oE '[A-Za-z0-9_./-]+\.(sh|py|md|yaml|yml|json|toml)'   # -> no output
```

This is a sibling of the root-directory allowlist removed in t1275: the same
mistake on the other axis. It was left in place deliberately to keep that fix
surgical.

## 2. The token character class silently truncates real paths

`[A-Za-z0-9_./-]` excludes characters git permits in filenames. The failure is
not a clean miss — it emits a **wrong** path that can never match, with no
signal that anything was dropped:

```bash
printf 'node_modules/@scope/pkg.js app/x.storyboardc\n' \
  | grep -oE '(\./)?([A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]*\.[A-Za-z0-9]{1,10}'
# -> scope/pkg.js
# -> app/x.storyboard
```

Dropped entirely: paths containing spaces, non-ASCII, `+`, `@`; and every
extensionless file (`bin/run`, `src/Makefile`), which is structurally invisible.

## 3. Inverting the search removes the grammar but needs a delimitation rule

Scanning the plan for each **remote-changed** path (rather than extracting
candidates from the plan) eliminates the filename grammar entirely — the
candidate set becomes whatever git reports, byte for byte. It then requires
deciding which characters delimit a reference, which is a design question with
verified traps:

- A delimiter set of `[A-Za-z0-9_./-]` reports `src/app.py` as referenced by the
  text `src/app.py@v2`, and `src/a` by `src/a+b.py` — `@` and `+` are path
  characters, not delimiters.
- The same set splits two equivalent anchor forms, accepting `src/app.py:42`
  while rejecting `src/app.py#L20`.

A workable set is *whitespace plus prose punctuation*, `#` included — treating
everything else (`@ + ~ %`, alphanumerics, non-ASCII) as path continuation:

```bash
D='[][:space:]'"'"'"`(){}<>,;:!?|=*#[]'
esc=$(printf '%s' "$p" | sed 's/[][\.^$*+?(){}|]/\\&/g')
grep -qE "(^|${D})(\./)?${esc}(${D}|\.(${D}|\$)|\$)" "$PLAN_FILE"
```

One residual is undecidable: whitespace must delimit bare references, so a
remote path that is a whitespace-delimited prefix of a longer quoted path
(remote `src/my`, plan `` `src/my file.py` ``) over-reports. Over-reporting
costs one advisory prompt; under-reporting costs the whole signal.

## 4. Unicode normalization is a correctness gap, not a test-harness quirk

APFS/HFS+ store filenames decomposed, so `git diff` reports NFD while a plan
authored in an editor carries NFC. Comparison is byte-exact, so the file drops
out silently:

```bash
NFC=$(printf 'src/caf\303\251.py'); NFD=$(printf 'src/cafe\314\201.py')
printf 'edit `%s`\n' "$NFC" | grep -qF "$NFD" || echo "no match"
```

It reproduces on any NFD-on-disk repository, so it is testable on Linux — a
fixture that commits an NFD filename and references it in NFC is the macOS shape
without needing macOS.

Reconciling the forms requires normalizing both sides **and an explicit
normalized-to-original mapping**: `grep -oFf` emits the matched normalized
string with no link to the pattern that produced it, so the obvious loop reports
the NFC form instead of the path git named. Keep a parallel array and emit the
original by index. Two paths colliding under NFC should report *both* originals;
picking one silently drops a real remote change.

## 5. Git paths may not be valid UTF-8, and this helper must never fail

`aitask_remote_drift_check.sh` documents "always exit 0; never fails the
workflow". A strict decode breaks that contract:

```bash
printf 'src/caf\351.py\n' \
  | python3 -c 'import sys,unicodedata; sys.stdout.write(unicodedata.normalize("NFC", sys.stdin.read()))'
# UnicodeDecodeError, exit 1
```

and under `set -e` a bare `x=$(python3 …)` **aborts the script**. Any
normalization work needs `surrogateescape` on both decode and encode (verified
to round-trip the invalid byte exactly) plus an errexit-suppressing guard:

```bash
if ! normalized=$(… 2>/dev/null); then norm_ok=false; fi
```

## 6. Tooling caveat when testing any of this

`grep` is not necessarily GNU grep. On a machine where it resolves to
**ugrep**, `[^[:cntrl:][:print:]]` is rejected as an empty character class,
though GNU grep accepts it. A portable non-ASCII probe:

```bash
[ -n "$(LC_ALL=C tr -d '\000-\177' < "$file" | head -c 1)" ]
```

Both greps the helper actually uses were re-run under GNU grep and agree, but
verify any new bracket expression against both.

## Related

- `.aitask-scripts/aitask_remote_drift_check.sh` — the sole implementation.
- `tests/test_remote_drift_check.sh` — Test 13 covers the consumer-project
  layout; none of the findings above are covered.
- `.claude/skills/task-workflow/remote-drift-check.md` — the consuming procedure
  and the `warn` / `strong-only` profile semantics that make a lost `OVERLAP`
  equivalent to no warning at all.
