#!/usr/bin/env bash
set -euo pipefail

# new_release_post.sh - Create a Hugo blog post for an aitasks release
#
# Usage:
#   ./website/new_release_post.sh [--auto] [VERSION]
#
# Modes:
#   (default)  Create a scaffold with TODOs for manual/AI editing
#   --auto     Create a publishable blog post from the changelog content
#
# If VERSION is not provided, reads from aiscripts/VERSION.
# This script lives in website/ so it is NOT included in the release tarball.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONTENT_DIR="$SCRIPT_DIR/content/blog"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

die() { echo -e "${RED}ERROR:${NC} $1" >&2; exit 1; }
info() { echo -e "${GREEN}$1${NC}"; }
warn() { echo -e "${YELLOW}$1${NC}"; }

# Format YYYY-MM-DD as "Mon DD, YYYY" (e.g., "Feb 25, 2026")
# Portable: works on both macOS BSD date and GNU date
format_display_date() {
    local input_date="$1"
    if [[ "$(uname -s)" == "Darwin" ]]; then
        date -j -f "%Y-%m-%d" "$input_date" "+%b %-d, %Y" 2>/dev/null || echo "$input_date"
    else
        date -d "$input_date" "+%b %-d, %Y" 2>/dev/null || echo "$input_date"
    fi
}

# Update the "Latest Releases" section in _index.md
# Inserts the new release at the top and keeps only 3 entries
update_landing_page() {
    local title="$1"
    local slug="$2"
    local release_date="$3"
    local index_file="$SCRIPT_DIR/content/_index.md"

    if [[ ! -f "$index_file" ]]; then
        warn "Landing page not found: $index_file (skipping update)"
        return 0
    fi

    local display_date
    display_date=$(format_display_date "$release_date")

    local new_entry="- **[${title}](blog/${slug}/)** -- ${display_date}"

    # Check for duplicate
    if grep -qF "blog/${slug}/" "$index_file"; then
        info "Landing page already has entry for $slug (skipping)"
        return 0
    fi

    # Verify there are existing release entries to anchor on
    if ! grep -q '^- \*\*\[v' "$index_file"; then
        warn "No existing release entries found in $index_file (skipping)"
        return 0
    fi

    local tmp_file
    tmp_file=$(mktemp "${TMPDIR:-/tmp}/ait_index_XXXXXX")

    awk -v new_entry="$new_entry" '
    BEGIN { entry_count = 0; inserted = 0 }
    /^- \*\*\[v/ {
        if (!inserted) {
            print new_entry
            inserted = 1
            entry_count = 1
        }
        entry_count++
        if (entry_count <= 3) { print }
        next
    }
    { print }
    ' "$index_file" > "$tmp_file"

    if [[ ! -s "$tmp_file" ]]; then
        warn "Landing page update produced empty output (skipping)"
        rm -f "$tmp_file"
        return 0
    fi

    mv "$tmp_file" "$index_file"
    info "Updated landing page with $title"
}

# --- Parse arguments ---
AUTO_MODE=false
VERSION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --auto) AUTO_MODE=true; shift ;;
        -*) die "Unknown flag: $1" ;;
        *) VERSION="$1"; shift ;;
    esac
done

# --- Determine version ---
if [[ -z "$VERSION" ]]; then
    VERSION=$(cat "$REPO_ROOT/aiscripts/VERSION" 2>/dev/null || true)
    if [[ -z "$VERSION" ]]; then
        if command -v gh &>/dev/null; then
            VERSION=$(gh release view --json tagName -q '.tagName' 2>/dev/null || true)
            VERSION="${VERSION#v}"
        fi
    fi
    if [[ -z "$VERSION" ]]; then
        die "Cannot determine version. Pass it as argument: $0 [--auto] 0.6.0"
    fi
    info "Detected version: v$VERSION"
fi

VERSION="${VERSION#v}"

# --- Get release date ---
TAG="v$VERSION"
RELEASE_DATE=""

if git rev-parse "$TAG" &>/dev/null; then
    RELEASE_DATE=$(git for-each-ref --format='%(creatordate:short)' "refs/tags/$TAG" 2>/dev/null || true)
fi

if [[ -z "$RELEASE_DATE" ]]; then
    RELEASE_DATE=$(date +%Y-%m-%d)
    if [[ "$AUTO_MODE" == false ]]; then
        warn "Could not find tag date for $TAG, using today: $RELEASE_DATE"
    fi
fi

# --- Extract changelog section (prefer humanized version) ---
CHANGELOG_SECTION=""
HUMANIZED=false

# Try CHANGELOG_HUMANIZED.md first (informal blog-style content)
if [[ -f "$REPO_ROOT/CHANGELOG_HUMANIZED.md" ]]; then
    CHANGELOG_SECTION=$(sed -n "/^## v${VERSION}$/,/^## v/{
        /^## v${VERSION}$/d
        /^## v/d
        p
    }" "$REPO_ROOT/CHANGELOG_HUMANIZED.md")
    if [[ -n "$CHANGELOG_SECTION" ]]; then
        HUMANIZED=true
        info "Using humanized changelog for v$VERSION"
    fi
fi

# Fall back to CHANGELOG.md
if [[ -z "$CHANGELOG_SECTION" ]] && [[ -f "$REPO_ROOT/CHANGELOG.md" ]]; then
    CHANGELOG_SECTION=$(sed -n "/^## v${VERSION}$/,/^## v/{
        /^## v${VERSION}$/d
        /^## v/d
        p
    }" "$REPO_ROOT/CHANGELOG.md")
fi

if [[ -z "$CHANGELOG_SECTION" ]]; then
    if [[ "$AUTO_MODE" == true ]]; then
        die "No changelog section found for v$VERSION. Cannot auto-generate blog post."
    fi
    warn "No changelog section found for v$VERSION. Creating empty scaffold."
fi

# --- Generate filename slug ---
SLUG="v${VERSION//\.}"

if [[ -n "$CHANGELOG_SECTION" ]]; then
    if [[ "$HUMANIZED" == true ]]; then
        # Humanized format: extract ## headings as keywords
        KEYWORDS=$(echo "$CHANGELOG_SECTION" | grep '^## ' | head -3 | sed 's/^## //' | \
            tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr '\n' '-' | sed 's/-$//') || true
    else
        # Standard changelog: extract bold feature names from Features section
        KEYWORDS=$(echo "$CHANGELOG_SECTION" | sed -n '/^### Features$/,/^### /{
            /^### /d
            p
        }' | grep -o '\*\*[^*]*\*\*' | sed 's/\*\*//g' | head -3 | \
            tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr '\n' '-' | sed 's/-$//') || true
    fi
    if [[ -n "$KEYWORDS" ]]; then
        SLUG="${SLUG}-${KEYWORDS}"
    fi
fi

# Sanitize and truncate slug to max 80 chars
SLUG=$(echo "$SLUG" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | sed 's/--*/-/g' | sed 's/-$//')
SLUG="${SLUG:0:80}"
SLUG="${SLUG%-}"

OUTPUT_FILE="$CONTENT_DIR/${SLUG}.md"

# Check for existing blog post (by exact file or by version prefix)
VERSION_NO_DOTS="${VERSION//\.}"
EXISTING_POST=$(find "$CONTENT_DIR" -maxdepth 1 -name "v${VERSION_NO_DOTS}*.md" -o -name "v${VERSION_NO_DOTS}-*.md" 2>/dev/null | head -1)

if [[ -n "$EXISTING_POST" ]] || [[ -f "$OUTPUT_FILE" ]]; then
    if [[ "$AUTO_MODE" == true ]]; then
        info "Blog post already exists for v$VERSION (skipping)"
        exit 0
    fi
    die "Blog post already exists: ${EXISTING_POST:-$OUTPUT_FILE}"
fi

# --- Extract title from top feature names ---
generate_title() {
    if [[ "$HUMANIZED" == true ]]; then
        # Humanized format uses ## headings for features
        local headings
        headings=$(echo "$CHANGELOG_SECTION" | grep '^## ' | head -3 | sed 's/^## //')
        if [[ -n "$headings" ]]; then
            local title
            title=$(echo "$headings" | paste -sd ',' | sed 's/,/, /g' | sed 's/\(.*\), /\1, and /')
            echo "v$VERSION: $title"
        else
            echo "v$VERSION Release"
        fi
    else
        local features
        features=$(echo "$CHANGELOG_SECTION" | sed -n '/^### Features$/,/^### /{
            /^### /d
            p
        }' | grep -o '\*\*[^*]*\*\*' | sed 's/\*\*//g' | head -3)
        if [[ -n "$features" ]]; then
            local title
            title=$(echo "$features" | paste -sd ',' | sed 's/,/, /g' | sed 's/\(.*\), /\1, and /')
            echo "v$VERSION: $title"
        else
            echo "v$VERSION Release"
        fi
    fi
}

# --- Generate one-line description ---
generate_description() {
    if [[ "$HUMANIZED" == true ]]; then
        # Use first non-empty, non-heading line as description
        local first_para
        first_para=$(echo "$CHANGELOG_SECTION" | grep -v '^$' | grep -v '^#' | head -1 | sed 's/^ *//')
        if [[ -n "$first_para" ]]; then
            echo "$first_para"
        else
            echo "aitasks v$VERSION release highlights."
        fi
    else
        local count
        count=$(echo "$CHANGELOG_SECTION" | grep -c '^\- ' || true)
        local feature_count
        feature_count=$(echo "$CHANGELOG_SECTION" | sed -n '/^### Features$/,/^### /{
            /^### /d
            p
        }' | grep -c '^\- ' || true)
        echo "aitasks v$VERSION with $feature_count new features and $count total changes."
    fi
}

# --- Create blog content ---
mkdir -p "$CONTENT_DIR"

if [[ "$AUTO_MODE" == true ]]; then
    # Auto mode: generate a publishable blog post from changelog
    TITLE=$(generate_title)
    DESCRIPTION=$(generate_description)

    {
        cat << FRONTMATTER
---
date: $RELEASE_DATE
title: "$TITLE"
linkTitle: "v$VERSION"
description: "$DESCRIPTION"
author: "aitasks team"
---

FRONTMATTER

        # Output the changelog section as the blog post body
        echo "$CHANGELOG_SECTION"

        cat << FOOTER

---

**Full changelog:** [v$VERSION on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v$VERSION)
FOOTER
    } > "$OUTPUT_FILE"

    info "Created blog post: $OUTPUT_FILE"

    # Update the "Latest Releases" section on the landing page
    update_landing_page "$TITLE" "$SLUG" "$RELEASE_DATE"

    echo "$OUTPUT_FILE"
else
    # Scaffold mode: create a template for manual editing
    cat > "$OUTPUT_FILE" << SCAFFOLD
---
date: $RELEASE_DATE
title: "v$VERSION: TODO_TITLE_WITH_TOP_FEATURES"
linkTitle: "v$VERSION"
description: "aitasks v$VERSION — TODO one-sentence summary"
author: "aitasks team"
---

<!--
  INSTRUCTIONS FOR EDITING:

  1. Replace the TODO placeholders in the frontmatter above
  2. Write 3-5 paragraphs below highlighting the most notable features
  3. Use an informal, conversational tone
  4. Focus on what each feature MEANS for the user, not implementation details
  5. Do NOT list every bug fix — the full changelog link covers those
  6. Delete this comment block when done

  CHANGELOG REFERENCE (for your convenience):
$CHANGELOG_SECTION
-->

TODO: Write informal release summary here. Highlight 3-5 features.

---

**Full changelog:** [v$VERSION on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v$VERSION)
SCAFFOLD

    info "Created blog post scaffold: $OUTPUT_FILE"
    echo ""
    echo "Next steps:"
    echo "  1. Edit $OUTPUT_FILE"
    echo "  2. Write informal feature summaries (the changelog is in a comment for reference)"
    echo "  3. Update the 'Latest Releases' section in website/content/_index.md"
    echo "     (This is done automatically when using --auto mode)"
    echo "  4. Preview: cd website && hugo server"
fi
