# Set-up answers
- **What it is and who uses it:** a personal sleep, mood and wellness tracker for the owner.
- **GitHub:** public. **Real data:** on the production server only, never in this repo.
- **How it goes live:** merging to `main` builds images and Watchtower updates production. **Master copy:** GitHub.
- **Preview:** `scripts/preview.sh`. **Process:** full (`safe-change` skill).

# How to Work on This Repo
- Every time you have an issue, bug, or update to make: Follow `agents/planner_agent.md` to plan it and wait for the user's approval, then follow `agents/implementation_agent.md` to implement it.
- Before any code change, review the project documentation (`PRODUCT.md` and `DESIGN.md`).
- If the user explicitly says to skip planning for a small fix, skip the plan, but still follow the testing, commit and safety rules in those files.

# Version Control Rules
- Follow the shared `safe-change` skill for every change. Commit and push to a working branch by explicit path, never to `main`. The owner merges, or gives the go-ahead for that specific merge. Never use `[skip ci]` in a pull request, because required checks would then wait forever. Docs-only merges don't redeploy.
- **CRITICAL:** Before any commit or push, you MUST verify the changes run successfully locally. Backend tests need a real Postgres: start a throwaway one, then run `cd backend && TEST_DATABASE_URL=<url> pytest tests -q`. Do NOT push untested backend code.
- **Preview:** `scripts/preview.sh up` runs a private copy of the branch with a copy of live data (`--phone` opens it to home Wi-Fi); `scripts/preview.sh down` stops it and deletes the copy.

# NUC and Deployment Instructions
- The NUC host is a shared production box also running `audio-scrobbler-app` and `UK-Expense-Tracker`. Treat it as multi-tenant, not a sandbox.
- Watchtower polls GHCR every 5 minutes and auto-updates images.
- **Production Compose Files:** When managing containers on the NUC, ALWAYS check which compose file is actively used by production containers (e.g., `docker inspect <container> | grep com.docker.compose.project.config_files`). Do NOT blindly run `docker-compose up -d` as it defaults to the development `docker-compose.yml`, which can mount local development volumes and cause apparent data loss. Always use `-f docker-compose.prod.yml` if it's the active production configuration.
- Destructive-command caution: Always check the blast radius (`docker volume ls`, `docker ps -a`) before any delete/wipe/teardown on the NUC to avoid accidentally wiping shared volumes (e.g. Postgres data).
- Resave secrets after editing: Whenever you touch `.env`, proactively remind the user to re-save it.

# UI and Manual Steps
- For manual steps in the browser or UI, provide the exact text in a plain chat code block, so the user can easily copy it.

# Project Context (Sleep Wellness Tracker)
- Tracks sleep, HRV, mood, activities, and subjective ratings. Connects with Garmin via Garmin Connect API.
- Impeccable Design: The frontend follows the "Quiet Sanctuary" design language detailed in `DESIGN.md`. All UI components should adhere to the established CSS tokens (`frontend-web/src/tokens.css`).
