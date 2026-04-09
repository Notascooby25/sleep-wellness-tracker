#!/usr/bin/env bash

WATCH_DIR="${1:-.}"
REMOTE="origin"
BRANCH="master"

# Use VS Code as the commit message editor
export GIT_EDITOR="code --wait"

# Watch for file saves
inotifywait -m -r -e CLOSE_WRITE --format '%w%f' "$WATCH_DIR" | while read -r filepath; do
    # Only handle files tracked by git
    if git ls-files --error-unmatch "$filepath" > /dev/null 2>&1; then
        echo "Change detected: $filepath"
        git add "$filepath"

        # Open VS Code commit editor
        git commit || echo "No changes to commit"

        # Push after commit
        git push "$REMOTE" "$BRANCH" || echo "Push failed"
    else
        echo "Ignored (not tracked by git): $filepath"
    fi
done
