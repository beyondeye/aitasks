---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [git-integration, contribution]
anchor: 2235
followup_kind: risk_mitigation
created_at: 2026-11-08 18:20
updated_at: 2026-11-09 09:40
artifacts:
  - handle: art:trail-contribution-gitlab-bitbucket
    kind: implementation_trail
    name: GitLab/Bitbucket contribution follow-ups
---

## Origin

Risk-mitigation ("after") follow-up for t2241, created at Step 8d after implementation landed.

## Risk addressed

The drop and the glab --paginate/:id behaviour were not tested on a live GitLab.

> The drop was proved from GitLab source and docs but not on a live GitLab. The output of glab's `:id` placeholder and `--paginate` is taken from `glab api --help` (1.126) and the stubs, not from a real server · severity: medium · → mitigation: gitlab_contribution_live_verification

> The CI job's runtime is Alpine with BusyBox ash and BusyBox date, not the test host. The inherited `date -d '6 hours ago'` cutoff fails there, which is now fixed with jq. A BusyBox-modelling `date` stub, a POSIX-shell run and a pre-fix control cover this on the host. Only the live run proves it in the real image · severity: medium · → mitigation: gitlab_contribution_live_verification

## Goal

Confirm what t2241 proved from GitLab source and host-side stubs, with an autonomous route that needs **no gitlab.com credentials**. The checks fall into two groups:

- **Regressions in our code**: real server responses, glab `:id` and `--paginate`, and the CI job under real BusyBox. These are worth re-running and are automated.
- **One-time facts about GitLab**: a non-member's label is dropped, and the scheduler fires the job. A pinned local GitLab CE checks these; gitlab.com is optional (Part C).

## Part A — credential-free checks (done 2026-11-08, from the t2241 session)

**A1. Real Alpine runtime, without Docker.**
- Download the Alpine minirootfs named by `https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/x86_64/latest-releases.yaml` (`flavor: alpine-minirootfs`) into its own scratch directory and verify its `sha256` from that file.
  - Used: 3.24.4, `cdaa38cb8de3537967ee5b6c9b6cd00cc962da2b018e6eea48696bb274923012`.
- Extract it to `$R`, then copy `/etc/resolv.conf` into it.
- Install the job's `before_script` packages:
  `bwrap --unshare-user --uid 0 --gid 0 --bind "$R" / --proc /proc --dev /dev --tmpfs /tmp --share-net --die-with-parent --clearenv --setenv PATH /usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /bin/sh -c 'apk add --no-cache bash curl jq git'`
  - Result: BusyBox v1.37.0 provides both `/bin/sh` and `date`, and jq is 1.8.2.
- Prepare the job directory `$J`:
  - Extract `contribution-check.script[0]` from the template into `$J/job.sh`.
  - Install `tests/lib/glab_contribution_stub.sh` into `$J/stub`.
  - Add a fake `$J/work/.aitask-scripts/aitask_contribution_check.sh` that appends `$1` to `$J/checked`.
- Run `$J/job.sh` with `sh` inside the same sandbox, without network, with `--bind "$J" "$J"` placed **after** `--tmpfs /tmp`, and with `PATH="$J/stub/bin:$PATH" GITLAB_TOKEN=t CI_PROJECT_PATH=o/r CI_API_V4_URL=https://gitlab.example/api/v4`.
- Results:
  - Scheduled mode: rc=0. Exactly `101 100 15 12` were checked over 2 curl calls, none of them `labels=`. The cutoff `updated_after` was 21600 s before `date -u +%s`.
  - `GLAB_STUB_CURL_FAIL_PAGE=2`: rc=1, nothing checked, `ERROR: could not list issues (page 2)`.
  - `GLAB_STUB_CURL_REPEAT_PAGE=1`: rc=1 after 2 calls, nothing checked, `ERROR: issue list page 2 repeats page 1`.
  - `ISSUE_IID=42`: rc=0, checked `42`.
  - Control: the pre-t2241 cutoff under real BusyBox `date` failed with rc=1 (`date: invalid date '6 hours ago'`, `date: unrecognized option: v`).

**A2. Real gitlab.com responses, anonymous.**
- Setup: a scratch git repo with `origin` = `https://gitlab.com/gitlab-org/cli.git`, an empty `GLAB_CONFIG_DIR`, and `GITLAB_TOKEN`, `GITLAB_ACCESS_TOKEN`, `OAUTH_TOKEN` and `GITLAB_HOST` all unset. `glab auth status` returned 401, i.e. not authenticated.
- `glab api --paginate "projects/:id/issues?state=opened&per_page=100"` returned rc=0. `:id` resolved from the remote.
  - The output was **3 top-level JSON arrays** (one per page) holding 256 issues: 256 unique iids, all `state: opened`, `labels` all strings, `description` and `web_url` present.
  - `_gitlab_select_contribution_issues` parsed it into an array (0 contributions in that project, which is expected).
- Anonymous REST: `projects/gitlab-org%2Fcli/issues?state=opened&per_page=100&page=N` honours `page`.
  - Page 1 covers iids 8724..8200 and page 2 covers 8191..7456, 100 each.
  - Headers: `x-next-page: 3`, `x-total: 256`, `x-total-pages: 3`.
- **Finding:** glab 1.126 really prints one array per page, contradicting `glab api --help` ("Arrays are output as a single JSON array"). The shipped code accepts both formats (`jq -s add`). The stub, however, defaults to the merged format and makes the real one opt-in (`GLAB_STUB_PAGINATE_FORMAT=concat`).

## Part B — local GitLab CE, fully scripted (needs a container runtime)

Prerequisites:
- Rootless `podman`. The base package is enough; `podman-docker` and `podman-compose` are not needed.
- `/etc/subuid` and `/etc/subgid` already map `ddt:100000:65536`.
- For the runner, `systemctl --user enable --now podman.socket`.
- Resources: ~3 GB image, 4–8 GB RAM, several minutes to boot.

Script all of it, re-runnable, and tear it down at the end. Never echo a token: keep tokens in files under the scratch directory, mode 600.
1. Start a **pinned** `gitlab/gitlab-ce:<exact version>` container with `GITLAB_ROOT_PASSWORD` and an `external_url` on a localhost port, and record the version here. Wait for `/-/readiness` to report ready.
2. As root, through the API:
   - create users `maint` and `outsider` (`POST /users`, `skip_confirmation=true`);
   - create an `api`-scope personal access token for each (`POST /users/:id/personal_access_tokens`);
   - as `maint`, create a public project `aitask-ct` with a `contribution` label.
   - Optionally add a `guest` user as a Guest member, for the member control.
3. Give each account its own glab configuration (`GLAB_CONFIG_DIR=<dir>/<user>`, `glab auth login --hostname localhost:<port> --stdin`, `api_protocol http`).
4. Write a non-interactive driver that sources `.aitask-scripts/aitask_contribute.sh` and calls `gitlab_create_issue "<root>/aitask-ct" <title> <body-with-metadata> false`. The body comes from `aitask_contribute.sh --dry-run`. `/aitask-contribute` itself is interactive, so it can't be used here.

### Part B record (2026-11-08, run from the t2241 follow-up session)

- Versions: `gitlab/gitlab-ce:19.4.5-ce.0` (API reports 19.4.5, revision 2c6f5521891, CE) and `gitlab/gitlab-runner:alpine-v19.5.3`; rootless podman 6.1.4 (runc, netavark).
- Server settings: published on `127.0.0.1:8929` with `external_url 'http://localhost:8929'`, 2 Puma workers, Sidekiq concurrency 5, Prometheus/KAS/registry off. Ready after about 9 minutes, using about 3.5 GB.
- Root token: seeded with `gitlab-rails runner` (`personal_access_tokens.build(...).set_token(ENV["SEED_TOKEN"])`, scopes api and admin_mode). User tokens: `POST /users/:id/personal_access_tokens`.
- Project: `maint/aitask-ct`, public, labels `contribution` and `area:scripts`, with `guest` added at access level 10.
- glab: **pass `--insecure-storage` to `glab auth login`**. Without it, glab 1.126 stores the token in the OS keyring keyed by host, and every per-account `GLAB_CONFIG_DIR` then shares the last login.
- Driver: a `bash -c` that sources `.aitask-scripts/aitask_contribute.sh` and calls `gitlab_create_issue "http://localhost:8929/maint/aitask-ct" <title> <body> false`. The body comes from `_glab_stub_metadata` (`tests/lib/glab_contribution_stub.sh`).
- Runner: registered with `POST /user/runners`, `config.toml` written by hand, container started with `--network host -v /run/user/1000/podman/podman.sock:/var/run/docker.sock`. The project holds `.gitlab-ci.yml` (the template), `.aitask-scripts/aitask_contribution_check.sh` and `.aitask-scripts/lib/`, with CI variable `GITLAB_TOKEN` (masked).
- **Defect D1 (t2241, shipped):** `_gitlab_verify_contribution_label` (`.aitask-scripts/aitask_contribute.sh`) matches `https://[^[:space:]]+/-/issues/[0-9]+`. That fails in two ways:
  - glab 1.126 prints `http://localhost:8929/maint/aitask-ct/-/work_items/1`;
  - REST `web_url` is `/-/work_items/<iid>` both locally and on gitlab.com (`gitlab-org/cli` #8724), and `http://` self-managed hosts never match.

  The result is that the "label was silently dropped" warning never fires; contributors always get "Could not verify". The unit tests did not catch it because their fake glab output prints `/-/issues/77`. Fix: match `https?://[^[:space:]]+/-/(issues|work_items)/[0-9]+`, and switch the test fixture to the real `work_items` output. **Fixed by t2250 (`b40f13b69`)**, unit-tested against the captured Part B output. To confirm it live, re-run Part B: outsider's create must then print the dropped-label warning instead of "Could not verify".

## Verification Checklist

- [x] Job script under real Alpine BusyBox ash and date — scheduled scan, failure paths, trigger mode, legacy-cutoff control — PASS 2026-11-08 auto: Part A1 (recorded from the t2241 follow-up session, not from a pick of this task)
- [x] glab `:id` resolution and `--paginate` output, plus REST paging, against real gitlab.com responses — PASS 2026-11-08 auto: Part A2, anonymous. Finding: glab prints one array per page (see the stub item below)
- [ ] Switch the default of `tests/lib/glab_contribution_stub.sh` to one array per page (the real glab 1.126 output), and keep the merged form behind a knob. Adjust Test 28/28b in `tests/test_contribution_check.sh` so the default leg models real glab.
- [x] Part B: `outsider` (a non-member) creates an issue through the driver, and the issue exists without `contribution` — PASS 2026-11-08 auto: #1 rc=0 `labels=[]` (GitLab CE 19.4.5). Separate sub-check, **FAIL**: stderr was "Could not verify that the 'contribution' label was applied to the new issue.", not the dropped-label warning. See Part B record, defect D1
- [x] Part B: `maint` and `guest` create issues and the label is kept — PASS 2026-11-08 auto: #3 (maint, Owner) and #2 (guest, Guest) carry `contribution`. Stderr showed the same D1 "Could not verify" warning instead of nothing
- [x] Part B, glab path: `list-issues --platform gitlab` from a checkout whose origin is the local project, with outsider's glab config and `GITLAB_TOKEN` unset — PASS 2026-11-08 auto: listed #3, #2, #1, all `HAS_METADATA:true`, including unlabeled #1; ordinary #4 not listed. The curl path cannot run without a token, so `:id` was resolved by glab
- [x] Part B, curl path: `aitask_contribution_check.sh 1 --platform gitlab --repo maint/aitask-ct --dry-run` with `CI_API_V4_URL` and maint's token — PASS 2026-11-08 auto: #3 scored 8 (high, same file) and #2 scored 5 (likely)
- [x] Part B, runner: pinned `gitlab/gitlab-runner:alpine-v19.5.3`, Docker executor on the rootless podman socket, `network_mode=host`; schedule played through the API — PASS 2026-11-08 auto: pipeline 1 succeeded in 25 s on job image `alpine:latest`. The trace shows `--- Checking issue #3/#2/#1 ---` (3 checks) and no `date:` line; #4 got 0 comments
  - Start `gitlab/gitlab-runner` (pinned) with the Docker executor on `unix:///run/user/$UID/podman/podman.sock`, registered via `POST /user/runners`.
  - Commit the template as `.gitlab-ci.yml` plus `.aitask-scripts/` to `aitask-ct`, and set the `GITLAB_TOKEN` CI variable.
  - Create and play a pipeline schedule (`POST /projects/:id/pipeline_schedules`, then `.../play`).
  - Read the job log (`GET /projects/:id/jobs/:job_id/trace`): it shows `--- Checking issue #<iid> ---` for the unlabeled contribution, checks no ordinary issue, and has no `date` error.
- [x] Part B teardown — PASS 2026-11-08: containers and volumes removed (0 left), tokens shredded, glab configs deleted. Images are kept for re-runs; remove them with `podman rmi docker.io/gitlab/gitlab-ce:19.4.5-ce.0 docker.io/gitlab/gitlab-runner:alpine-v19.5.3`

## Part C — optional one-time gitlab.com confirmation

This is only needed to confirm the hosted service's configuration, as opposed to the same GitLab code. It takes two free gitlab.com accounts created by a person: `maint` owns a public scratch project, and `outsider` is not a member. Run the Part B items 4–5 once with the same driver against `gitlab.com`, then delete the project. Do not automate this permanently. Shared runners may need account verification, so the runner check stays in Part B.
