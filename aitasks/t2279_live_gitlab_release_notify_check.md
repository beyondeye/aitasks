---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [release_scripts, bash_scripts, issue_integration]
anchor: 2261
followup_kind: risk_mitigation
created_at: 2026-11-10 18:21
updated_at: 2026-11-10 18:21
---

## Origin

Risk-mitigation ("after") follow-up for t2261_2, created at Step 8d after implementation landed.

## Risk addressed

GitLab notes-listing misread causing duplicate release comments.

> The GitLab path (`glab api --paginate` notes, `glab issue note`, GitLab
> releases API, and `glab release download -n/-D` for manifests) is verified
> only against stubs. A misread listing could miss the marker and duplicate a
> comment. A wrong download flag would keep a manifest-configured GitLab
> project blocked (fail-closed, `unknown:api_error`). · severity: medium

## Goal

Live-check `ait release-notify`'s GitLab path against the local GitLab CE
harness (rootless podman, credential-free; see the t2248 harness) instead of the
hand-written glab stubs in `tests/lib/release_notify_fixture.sh`:

- `gitlab_list_comment_bodies` (`lib/issue_backends.sh`): `glab api --paginate
  "projects/<enc>/issues/<iid>/notes?per_page=100" | jq -r '.[].body'` returns
  every note body across more than one page (create >100 notes), and the
  release marker is found on a later page;
- `glab issue note <iid> -R <slug> -m <body>` posts exactly one note, and a
  re-run finds the marker and posts nothing (re-run idempotency);
- `release_publication_check` (`lib/release_publication.sh`) against a real
  GitLab release: `glab api projects/<enc>/releases/<tag>` (404 →
  `pending:no_release`, `upcoming_release` → `pending:upcoming`), and
  `assets.links[].name` for required assets;
- `glab release download <tag> -R <repo> -n <name> -D <dir>` really writes
  `<dir>/<name>` for a link asset (checksum manifests); confirm the flag names
  against the installed glab and fix the code if they differ;
- self-hosted host handling: `--hostname` for `glab api` and the full-URL
  `-R` form used for non-gitlab.com hosts.

Then replace the hand-written glab stub responses in
`tests/lib/release_notify_fixture.sh` with output captured from the harness
(keep the stubs for the offline suite, but make their JSON shapes the captured
ones), and record the captures in the archived plan.
