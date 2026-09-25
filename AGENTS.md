# How to Work on This Repo
- Every time you have an issue, bug, or update to make: Follow `agents/planner_agent.md` to plan it and wait for the user's approval, then follow `agents/implementation_agent.md` to implement it.
- Before any code change, review the project documentation (`PRODUCT.md` and `DESIGN.md`).
- If the user explicitly says to skip planning for a small fix, skip the plan, but still follow the testing, commit and safety rules in those files.

# Version Control Rules
- At the end of every task or major step that involves modifying files, you MUST use the `run_command` tool to stage all changes, commit them with a descriptive commit message explaining the reason for the changes, and push them to the current branch on GitHub.
- Example command: `git add -A && git commit -m "feat: <description of changes>" && git push`

# NUC and Deployment Instructions
- NUC host: `192.168.68.126`. It is a shared production box also running `audio-scrobbler-app` and `UK-Expense-Tracker`. Treat it as multi-tenant, not a sandbox.
- Watchtower polls GHCR every 5 minutes and auto-updates images.
- Destructive-command caution: Always check the blast radius (`docker volume ls`, `docker ps -a`) before any delete/wipe/teardown on the NUC to avoid accidentally wiping shared volumes (e.g. Postgres data).
- Resave secrets after editing: Whenever you touch `.env`, proactively remind the user to re-save it.

# UI and Manual Steps
- For manual steps in the browser or UI, provide the exact text in a plain chat code block, so the user can easily copy it.

# Project Context (Sleep Wellness Tracker)
- Tracks sleep, HRV, mood, activities, and subjective ratings. Connects with Garmin via Garmin Connect API.
- Impeccable Design: The frontend follows the "Quiet Sanctuary" design language detailed in `DESIGN.md`. All UI components should adhere to the established CSS tokens (`frontend-web/src/tokens.css`).
