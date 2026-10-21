#!/usr/bin/env bash
# Helper script for dev-document-spec to gather context deterministically
set -euo pipefail

SPEC_NAME="${1:-}"

# 1. Resolve SpecName deterministically
if [ -z "$SPEC_NAME" ]; then
    # Look for directories in docs/specs or docs
    SEARCH_DIRS=("docs/specs" "docs")
    FOUND_SPECS=()

    for dir in "${SEARCH_DIRS[@]}"; do
        if [ -d "$dir" ]; then
            for spec_dir in "$dir"/*; do
                if [ -d "$spec_dir" ]; then
                    rev_file="$spec_dir/review.md"
                    if [ -f "$rev_file" ] && grep -qE '^[[:space:]]*-?[[:space:]]*(Verdict|Status|Decision)?[[:space:]]*:?[[:space:]]*APPROVED[[:space:]]*$' -i "$rev_file"; then
                        FOUND_SPECS+=("$(basename "$spec_dir")")
                    fi
                fi
            done
        fi
    done

    if [ ${#FOUND_SPECS[@]} -eq 0 ]; then
        echo "ERROR: No approved specification found." >&2
        exit 1
    elif [ ${#FOUND_SPECS[@]} -eq 1 ]; then
        SPEC_NAME="${FOUND_SPECS[0]}"
    else
        # Tie-break: sort reverse alphabetically (latest timestamp/name)
        IFS=$'\n' SORTED=($(sort -r <<<"${FOUND_SPECS[*]}"))
        unset IFS
        SPEC_NAME="${SORTED[0]}"
        echo "INFO: Multiple approved specs found. Selected latest: $SPEC_NAME" >&2
    fi
fi

echo "SPEC_NAME=$SPEC_NAME"

SPEC_DIR="docs/specs/$SPEC_NAME"
if [ ! -d "$SPEC_DIR" ] && [ -d "docs/$SPEC_NAME" ]; then
    SPEC_DIR="docs/$SPEC_NAME"
fi

echo "SPEC_DIR=$SPEC_DIR"

# 2. Check artifacts
echo "--- Artifacts Check ---"
for art in "spec.md" "plan.md" "review.md"; do
    if [ -f "$SPEC_DIR/$art" ]; then
        echo "FOUND: $SPEC_DIR/$art"
    else
        echo "MISSING: $SPEC_DIR/$art (Skip and note in summary)"
    fi
done

# 3. Git Diff & Scope Filtering
echo "--- Git Diff Summary ---"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    BASE_REF=$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || true)
    if [ -z "$BASE_REF" ] && [ -f "$SPEC_DIR/review.md" ]; then
        BASE_REF=$(git log -1 --format=%H -- "$SPEC_DIR/review.md" 2>/dev/null || true)
    fi
    if [ -z "$BASE_REF" ]; then
        BASE_REF="HEAD~1"
    fi
    echo "BASE_REF: $BASE_REF"

    EXCLUDE_REGEX='^(vendor/|node_modules/|dist/|build/|target/|\.gradle/|\.idea/|package-lock\.json|yarn\.lock|pnpm-lock\.yaml|go\.sum|Cargo\.lock|.*_generated\..*|\.min\.(js|css))$'

    CHANGED_FILES=$(git diff --name-only --diff-filter=d "$BASE_REF" 2>/dev/null || git status --short | awk '{print $NF}')
    FILTERED_CHANGED=$(echo "$CHANGED_FILES" | grep -vE "$EXCLUDE_REGEX" || true)

    FILE_COUNT=$(echo "$FILTERED_CHANGED" | grep -c . || true)
    echo "Changed/Added files ($FILE_COUNT in scope):"
    if [ "$FILE_COUNT" -gt 40 ]; then
        echo "WARNING: Diff exceeds 40 files ($FILE_COUNT files). Prioritizing first 40 files / files in plan.md (truncation flagged)."
        echo "$FILTERED_CHANGED" | head -n 40
    else
        echo "$FILTERED_CHANGED"
    fi

    echo "Removed/Renamed files:"
    git diff --name-only --diff-filter=DR "$BASE_REF" 2>/dev/null | grep -vE "$EXCLUDE_REGEX" || true
else
    echo "WARNING: Not a git repository. Fall back to manual file inspection."
fi
