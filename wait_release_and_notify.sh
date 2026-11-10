#!/usr/bin/env bash
# wait_release_and_notify.sh - Wait until the release workflow has published
# <tag>, then notify the resolved issues it ships (t2261_2). Framework-only:
# run by create_new_release.sh after the tag push; not shipped to projects.
#
# Usage: ./wait_release_and_notify.sh <tag> [--timeout S] [--interval S]
#   Defaults 1800 s / 20 s; env AIT_RELEASE_WAIT_TIMEOUT / AIT_RELEASE_POLL_INTERVAL.
#
# It only WAITS. Every poll is the shared release_publication_check, which
# applies this repository's publication policy (project_config.yaml), and the
# consumer re-checks freshness, designation and publication itself before it
# posts anything, so this script can never weaken the gate.
#
# Exit: 0 notified | 1 usage or setup error | 2 the release workflow failed |
#       3 timed out | 4 partial notification | 5 not attempted (this is not the
#       designated machine, reconciliation failed, or the consumer refused)
# Every non-zero exit prints the exact retry command.

set -euo pipefail

cd "$(dirname "$0")"

# shellcheck source=.aitask-scripts/lib/task_utils.sh
source .aitask-scripts/lib/task_utils.sh
# shellcheck source=.aitask-scripts/lib/release_issue_ledger.sh
source .aitask-scripts/lib/release_issue_ledger.sh

TAG=""
TIMEOUT="${AIT_RELEASE_WAIT_TIMEOUT:-1800}"
INTERVAL="${AIT_RELEASE_POLL_INTERVAL:-20}"

usage() {
    echo "Usage: ./wait_release_and_notify.sh <tag> [--timeout S] [--interval S]" >&2
}

retry_exit() {
    echo "RETRY: ./wait_release_and_notify.sh $TAG"
    exit "$1"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --timeout)  [[ $# -ge 2 ]] || { usage; exit 1; }; TIMEOUT="$2"; shift 2 ;;
        --interval) [[ $# -ge 2 ]] || { usage; exit 1; }; INTERVAL="$2"; shift 2 ;;
        -h|--help)  usage; exit 0 ;;
        -*)         usage; exit 1 ;;
        *)          [[ -z "$TAG" ]] || { usage; exit 1; }; TAG="$1"; shift ;;
    esac
done
[[ -n "$TAG" ]] || { usage; exit 1; }
rp_valid_tag "$TAG" || { echo "invalid tag: $TAG" >&2; exit 1; }
[[ "$TIMEOUT" =~ ^[0123456789]+$ && "$INTERVAL" =~ ^[0123456789]+$ ]] \
    || { echo "--timeout and --interval take whole seconds" >&2; exit 1; }

# A framework release is never generic-gated by accident.
if ! release_publication_policy_load; then
    echo "SETUP_ERROR:policy_unreadable:$RP_POLICY_ERR"
    retry_exit 1
fi
if [[ -z "$RP_WORKFLOW" || ${#RP_ASSETS[@]} -eq 0 ]]; then
    echo "SETUP_ERROR:policy_incomplete (set release_publication_workflow and release_publication_assets in aitasks/metadata/project_config.yaml)"
    retry_exit 1
fi

# Not the notification machine: say where to run it, before any API call.
if ! desig="$(release_notify_designation)"; then
    case "$desig" in
        not_designated:*)
            d="${desig#not_designated:}"
            echo "NOT_DESIGNATED:$desig"
            echo "notifications run only on ${d%%|*}: run ./wait_release_and_notify.sh $TAG there" ;;
        *)
            echo "NOT_DESIGNATED:$desig"
            echo "set release_notify_host in aitasks/metadata/project_config.yaml to the notification machine's hostname" ;;
    esac
    retry_exit 5
fi

# Poll the shared check until published, failed, or the deadline.
deadline=$(( SECONDS + TIMEOUT ))
last=""
while :; do
    rc=0
    last="$(release_publication_check "$TAG")" || rc=$?
    case "$last" in
        PUBLICATION:published\|*)
            echo "$last"
            break ;;
        PUBLICATION:failed:workflow_failed:*)
            echo "WORKFLOW_FAILED:${last#PUBLICATION:failed:workflow_failed:}"
            echo "nothing was posted; every record stays pending"
            retry_exit 2 ;;
        PUBLICATION:pending:*)
            echo "WAIT:${last#PUBLICATION:pending:}" ;;
        *)
            # Other failures and unknowns may be transient (an API hiccup, a
            # tag push still propagating): keep polling until the deadline.
            echo "WAIT:${last:-no_answer (rc $rc)}" ;;
    esac
    if (( SECONDS >= deadline )); then
        echo "TIMEOUT:$last"
        echo "nothing was posted; every record stays pending"
        retry_exit 3
    fi
    sleep "$INTERVAL"
done

# Reconcile the task data first (branch mode). Legacy mode keeps it on main,
# which create_new_release.sh has just pushed. Either way the consumer's own
# freshness check is the authority.
if [[ "$(ait_data_mode)" == branch ]]; then
    sync_rc=0
    sync_out="$(./ait sync --batch 2>/dev/null)" || sync_rc=$?
    # The status token is the FIRST line; continuation lines may follow it.
    token="${sync_out%%$'\n'*}"
    case "$token" in
        SYNCED|PUSHED|PULLED|NOTHING|AUTOMERGED|MERGED)
            if [[ "$sync_rc" != 0 ]]; then
                echo "RECONCILE_FAILED:$token (rc $sync_rc)"
                echo "resolve with ./ait sync, then retry"
                retry_exit 5
            fi
            echo "RECONCILED:$token" ;;
        *)
            echo "RECONCILE_FAILED:${token:-no_output}"
            echo "resolve with ./ait sync, then retry"
            retry_exit 5 ;;
    esac
fi

# Notify. The consumer re-checks everything before it posts.
crc=0
out="$(./.aitask-scripts/aitask_release_notify.sh --tag "$TAG")" || crc=$?
while IFS= read -r line; do
    printf '%s\n' "$line"
    case "$line" in
        SHIPPED_EARLIER:*)
            echo "HINT:notify it with: ./wait_release_and_notify.sh ${line##*|}" ;;
    esac
done <<< "$out"
case "$crc" in
    0) exit 0 ;;
    3) retry_exit 5 ;;
    4) retry_exit 4 ;;
    *) retry_exit 1 ;;
esac
