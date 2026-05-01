#!/usr/bin/env bash
set -euo pipefail

WATCH_DIR="${1:-.}"
REMOTE="${2:-$(git remote | head -n 1)}"
BRANCH="${3:-$(git branch --show-current)}"

# Default: safer on laptops. Set AUTO_PUSH=1 to re-enable automatic push.
AUTO_PUSH="${AUTO_PUSH:-0}"
DEBOUNCE_SECONDS="${DEBOUNCE_SECONDS:-15}"

if [[ -z "${REMOTE}" ]]; then
    REMOTE="origin"
fi

if [[ -z "${BRANCH}" ]]; then
    BRANCH="master"
fi

export GIT_EDITOR="code --wait"

# Keep auto-commit focused on source/config files to avoid huge staging sets.
TRACKED_PATHS=(
    "backend/app"
    "backend/requirements.txt"
    "frontend-web/src"
    "frontend-web/package.json"
    "frontend-web/svelte.config.js"
    "frontend-web/vite.config.ts"
    "docker-compose.yml"
    "docker-compose.prod.yml"
    "db"
    "scripts"
)

EXCLUDE_REGEX='(\.git|\.venv|node_modules|__pycache__|\.svelte-kit|build|dist|logs|Images_issues|\.history|\.db$|\.sql$|\.tar$|\.tar\.gz$|\.zip$|build_podman\.log$)'

commit_with_prompt() {
    if [[ -n "${VSCODE_IPC_HOOK_CLI:-}" || -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
        git -c core.editor="code --wait" commit
        return $?
    fi

    if [[ -t 0 ]]; then
        local msg
        read -r -p "Commit message: " msg
        if [[ -z "${msg}" ]]; then
            echo "Skipping commit: empty message"
            return 1
        fi
        git commit -m "${msg}"
        return $?
    fi

    echo "Cannot prompt for commit message: no GUI or interactive terminal."
    return 1
}

stage_tracked_paths() {
    git add -A -- "${TRACKED_PATHS[@]}"
}

has_staged_changes() {
    ! git diff --cached --quiet
}

maybe_push() {
    if [[ "${AUTO_PUSH}" == "1" ]]; then
        git push "${REMOTE}" "${BRANCH}" || echo "Push failed"
    else
        echo "AUTO_PUSH=0, skipping push. Run push manually when ready."
    fi
}

echo "Watching ${WATCH_DIR}"
echo "Debounce: ${DEBOUNCE_SECONDS}s"
echo "Auto-push: ${AUTO_PUSH}"

while true; do
    inotifywait -q -r \
        --exclude "${EXCLUDE_REGEX}" \
        -e modify -e create -e delete -e move \
        "${WATCH_DIR}" > /dev/null

    sleep "${DEBOUNCE_SECONDS}"

    # Drain bursty events so one prompt handles a grouped change set.
    while inotifywait -q -t 1 -r \
        --exclude "${EXCLUDE_REGEX}" \
        -e modify -e create -e delete -e move \
        "${WATCH_DIR}" > /dev/null; do
        :
    done

    stage_tracked_paths

    if has_staged_changes; then
        echo "Changes detected in tracked paths."
        if commit_with_prompt; then
            maybe_push
        else
            echo "No commit created"
        fi
    else
        echo "No staged changes in tracked paths."
    fi
done
