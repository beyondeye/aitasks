#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

current_version=$(cat VERSION)

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

# Check if CHANGELOG.md has an entry for this version
if [[ -f CHANGELOG.md ]]; then
  if ./aiscripts/aitask_changelog.sh --check-version "$new_version" 2>/dev/null; then
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

echo "$new_version" > VERSION
git add VERSION
git commit -m "Bump version to $new_version"
git tag "v$new_version"
git push origin main --tags

echo ""
echo "Done! Release workflow triggered for v$new_version."
echo "Check: https://github.com/beyondeye/aitasks/actions"
