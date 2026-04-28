#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

current_version=$(cat .aitask-scripts/VERSION)

echo "Current version: $current_version"
read -rp "New version (without 'v' prefix): " new_version

if [[ -z "$new_version" ]]; then
  echo "Aborted: no version provided."
  exit 1
fi

if [[ "$new_version" == "$current_version" ]]; then
  echo "Aborted: new version is the same as current."
  exit 1
fi

if git rev-parse "v$new_version" >/dev/null 2>&1; then
  echo "Aborted: tag v$new_version already exists."
  exit 1
fi

# Sync with remote so the final 'git push origin main --tags' is fast-forward.
# A failed push *after* the tag has already been pushed leaves the remote with
# the tag pointing at a commit that is not in main's history.
current_branch=$(git rev-parse --abbrev-ref HEAD)
if [[ "$current_branch" != "main" ]]; then
  echo "Aborted: releases must be cut from 'main' (current: $current_branch)."
  exit 1
fi

echo ""
echo "Fetching origin to verify main is in sync..."
if ! git fetch origin --quiet; then
  echo -e "\033[1;33mWARNING:\033[0m git fetch origin failed. Cannot verify remote state."
  read -rp "Continue without sync verification? [y/N] " fetch_confirm
  if [[ "$fetch_confirm" != [yY] ]]; then
    echo "Aborted."
    exit 1
  fi
else
  local_sha=$(git rev-parse main)
  remote_sha=$(git rev-parse origin/main)
  if [[ "$local_sha" != "$remote_sha" ]]; then
    behind=$(git rev-list --count main..origin/main)
    if [[ "$behind" -gt 0 ]]; then
      ahead=$(git rev-list --count origin/main..main)
      echo "Local main is $ahead ahead and $behind behind origin/main."
      echo "Rebasing on origin/main before continuing..."
      if ! git pull --rebase origin main; then
        echo -e "\033[0;31mERROR:\033[0m Rebase failed. Resolve conflicts manually, then re-run."
        exit 1
      fi
      echo -e "\033[0;32mSynced with origin/main.\033[0m"
    fi
  fi
fi

# Check if CHANGELOG.md has an entry for this version
if [[ -f CHANGELOG.md ]]; then
  if ./.aitask-scripts/aitask_changelog.sh --check-version "$new_version" 2>/dev/null; then
    echo -e "\033[0;32mCHANGELOG.md has entry for v${new_version}. Will be used as release notes.\033[0m"
  else
    echo ""
    echo -e "\033[1;33mWARNING:\033[0m No CHANGELOG.md entry found for v${new_version}."
    echo "Consider running /aitask-changelog first to generate the changelog entry."
    read -rp "Continue without changelog? [y/N] " changelog_confirm
    if [[ "$changelog_confirm" != [yY] ]]; then
      echo "Aborted. Run /aitask-changelog to generate the changelog entry first."
      exit 1
    fi
  fi
else
  echo ""
  echo -e "\033[1;33mWARNING:\033[0m No CHANGELOG.md file found."
  echo "Consider running /aitask-changelog first to generate the changelog."
  read -rp "Continue without changelog? [y/N] " changelog_confirm
  if [[ "$changelog_confirm" != [yY] ]]; then
    echo "Aborted."
    exit 1
  fi
fi

echo ""
echo "Will update VERSION $current_version -> $new_version"
echo "Will create tag v$new_version and push to trigger release workflow."
read -rp "Continue? [y/N] " confirm
if [[ "$confirm" != [yY] ]]; then
  echo "Aborted."
  exit 1
fi

echo "$new_version" > .aitask-scripts/VERSION

# Generate blog post from changelog (auto mode, non-fatal)
if [[ -x ./website/new_release_post.sh ]]; then
  echo ""
  echo "Generating release blog post..."
  ./website/new_release_post.sh --auto "$new_version" || echo -e "\033[1;33mWARNING:\033[0m Blog post generation failed (non-fatal)."
fi

git add .aitask-scripts/VERSION
git add website/content/blog/ 2>/dev/null || true
git add website/content/_index.md 2>/dev/null || true
git commit -m "ait: Bump version to $new_version"
git tag "v$new_version"
git push origin main --tags

echo ""
echo "Done! Release workflow triggered for v$new_version."
echo "Check: https://github.com/beyondeye/aitasks/actions"
