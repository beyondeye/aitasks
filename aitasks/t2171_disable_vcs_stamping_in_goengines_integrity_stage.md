---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
followup_kind: upstream_defect
created_at: 2026-10-30 13:50
updated_at: 2026-11-03 17:45
---

## Origin

Spawned from **aitasks_go#t56** (Step 8b review): the private exporter's
root-test gate flake during the t22_3 bootstrap export. That task fixed the
private exporter (`promote/gocmd.go` `stageEnv`: `-buildvcs=false` for every
go command run in the export stage, aitasks_go commit 3756a5a). This public
script has the same defect.

## Upstream defect

- `.github/scripts/goengines_integrity.sh:349` (also `:328`, `:378`) — `run_go`
  stage builds / `go list -deps` in its `mktemp -d` work dir run under
  `-buildvcs=auto`, so a transient empty ancestor `.git` (the Codex sandbox
  creates one in `/tmp`) fails `independent-build` / `closure` with
  `error obtaining VCS status: exit status 128`.

Line numbers are as of aitasks `08c3304dd`.

## Diagnostic context

- A concurrent Codex session's sandbox (`codex-linux-sandbox` → `bwrap …
  --bind /tmp /tmp`) creates an empty `/tmp/.git` (owner: the user) for the
  duration of each sandboxed command and removes it afterwards (observed with
  `inotifywait` on 2026-10-30, windows from about 1 s up to ~26 s).
- While it exists, `go build` and `go list -deps` under the default
  `-buildvcs=auto` in any `/tmp` directory without a repository of its own walk
  up to it, run `git status`, and fail with exit 128.
  `go vet`, `go mod tidy` and `go list -m` are unaffected.
- Reproduced deterministically: a module dir under an empty ancestor `.git`
  fails `go build ./...` and `go list -deps -json ./...` with that error;
  `GOFLAGS=-buildvcs=false` passes.
- Effect here: `goengines_integrity.sh check` run locally (e.g. by aitasks_go's
  `TestPublicIntegrityAcceptsExport`, with TMPDIR under an empty `.git`)
  reports `INTEGRITY_FAIL:independent-build:<target>: go build ./... failed:
  error obtaining VCS status` and `INTEGRITY_FAIL:closure:…`. GitHub-hosted
  runners have no such sandbox, so CI is unlikely to hit it. Local runs on a
  host with a concurrent Codex session can.

## Suggested fix

Add `-buildvcs=false` to the `GOFLAGS=` of the `run_go` calls that build or
`go list -deps` in the work dir (the work dir is a bare tree, never a
repository, so stamping there is always wrong). Keep `INDEPENDENT_ENV` itself
unchanged. Verify by running `check` with `TMPDIR` under a private empty
`.git` (e.g. `mkdir -p /tmp/x/.git /tmp/x/tmp; TMPDIR=/tmp/x/tmp …`), before
and after.
