#!/usr/bin/env bash

WATCH_DIR="${1:-.}"
REMOTE="$(git remote | head -n 1)"
BRANCH="$(git branch --show-current)"

if [[ -z "$REMOTE" ]]; then
    REMOTE="origin"
fi

if [[ -z "$BRANCH" ]]; then
    BRANCH="master"
fi

# Ensure VS Code is used for commit messages
export GIT_EDITOR="code --wait"

commit_with_prompt() {
    # Prefer VS Code commit editor when desktop/VS Code session is available.
    if [[ -n "$VSCODE_IPC_HOOK_CLI" || -n "$DISPLAY" || -n "$WAYLAND_DISPLAY" ]]; then
        git -c core.editor="code --wait" commit
        return $?
    fi

    # Fallback to terminal prompt if running interactively.
    if [[ -t 0 ]]; then
        local msg
        read -r -p "Commit message: " msg
        if [[ -z "$msg" ]]; then
            echo "Skipping commit: empty message"
            return 1
        fi
        git commit -m "$msg"
        return $?
    fi

    echo "Cannot prompt for commit message: no GUI or interactive terminal."
    echo "Start watcher from a VS Code terminal to restore commit prompts."
    return 1
}

# Watch everything except .git and __pycache__
inotifywait -m -r \
    --exclude '(\.git|__pycache__)' \
    -e modify -e create -e delete -e move \
    "$WATCH_DIR" | while read -r directory events filename; do

    echo "Change detected: $directory$filename ($events)"

    # Stage ALL changes, including new/untracked/deleted files
    git add -A

    # Prompt for commit message via VS Code or terminal.
    commit_with_prompt || echo "No commit created"

    # Push after commit
    git push "$REMOTE" "$BRANCH" || echo "Push failed"
done
