#!/usr/bin/env bash

WATCH_DIR="${1:-.}"
REMOTE="origin"
BRANCH="master"

# Ensure VS Code is used for commit messages
export GIT_EDITOR="code --wait"

# Watch everything except .git and __pycache__
inotifywait -m -r \
    --exclude '(\.git|__pycache__)' \
    -e modify -e create -e delete -e move \
    "$WATCH_DIR" | while read -r directory events filename; do

    echo "Change detected: $directory$filename ($events)"

    # Stage ALL changes, including new/untracked/deleted files
    git add -A

    # Open VS Code commit editor
    git commit || echo "No changes to commit"

    # Push after commit
    git push "$REMOTE" "$BRANCH" || echo "Push failed"
done
