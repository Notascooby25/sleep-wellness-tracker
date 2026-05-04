# 🛌 Sleep & Wellness Tracker

A self-hosted, personal health dashboard for tracking sleep, mood, activity, and a broad range of Garmin biometric data — all in one place. Built to run on a home Intel NUC and accessed via a local web browser.

---

## 📖 What is it?

Sleep & Wellness Tracker is a full-stack web application that acts as a personal health journal and biometric dashboard. At its core it lets you log how you're feeling day-to-day (mood, activities, notes), while automatically pulling in rich data from a connected Garmin device — sleep stages, body battery, HRV, stress, hydration, steps, and more.

The goal is to build a long-term picture of your health and to correlate lifestyle choices (what you did, how you felt) against objective biometric data from your Garmin watch.

---

## ✨ Features

### 😴 Garmin Sleep Tracking
- Automatic daily sync of Garmin sleep data including:
  - Total sleep duration, Sleep score
  - Sleep stage breakdown — Deep, Light, REM, and Awake minutes
  - Sleep start/end times
  - Body Battery at wake-up and at bedtime

### ⚡ Garmin Biometrics
Full automatic sync of supporting biometric data:
| Metric | Details |
|---|---|
| **Body Battery** | Morning value, end-of-day value, daily peak & low |
| **HRV** | Daily HRV, weekly average, baseline range & status |
| **Resting Heart Rate** | Daily resting, min, and max heart rate |
| **Stress** | Overall stress level, time in rest/low/medium/high stress |
| **Hydration** | Daily consumed ml vs. daily goal ml |
| **Steps** | Total steps, distance, and calories burned |
| **Activities** | Workout type, name, duration, distance, calories, average & max HR |

### 🔄 Automated Garmin Sync
The backend runs a background autosync loop with two timed windows each day (UK timezone):
- **Morning sync (08:00–09:00)** — Pulls overnight data: Sleep, HRV, Resting Heart Rate
- **Evening sync (23:50+)** — Pulls end-of-day data: Body Battery, Hydration, Stress, Steps, Activities

Autosync can be enabled/disabled via the `GARMIN_AUTOSYNC_ENABLED` environment variable. Manual syncs can also be triggered from the UI.

### 😊 Mood & Wellbeing Journal
- Log a daily mood entry with a numeric score
- Add free-text notes to each entry
- Tag entries with one or more **activities** to record what you did that day
- Full mood history log to review past entries

### 🏷️ Activities & Categories
- Create custom **categories** (e.g. *Exercise*, *Health*, *Social*) with optional per-category rating labels
- Create custom **activities** within categories (e.g. *Running*, *Physio*, *Cinema*)
- Activities are tagged against mood entries to build a lifestyle picture over time
- Full management UI for adding, editing, and deleting categories and activities

### 📊 Analytics & Lifestyle Impact
- **Analytics dashboard** — visualise trends across sleep, mood, and Garmin metrics over time
- **Garmin Log** — chronological view of raw synced Garmin data
- **Garmin Lifestyle Impact** — cross-reference your Garmin biometrics with logged activities to explore how lifestyle choices relate to your sleep quality, HRV, stress, and body battery

### 📤 Data Export
- Export your tracked data via the backend API for use in external tools

### ⚙️ Settings
- Manage Garmin connection credentials and sync configuration from the Settings page

---

## 🏗️ Architecture

The application is made up of three containerised services:

```
┌─────────────────────────────────────────────┐
│               Browser (port 8510)            │
└──────────────────────┬──────────────────────┘
                       │
         ┌─────────────▼─────────────┐
         │   Frontend  (SvelteKit)    │  :3000 (internal)
         │   frontend-web container   │
         └─────────────┬─────────────┘
                       │ HTTP (API_BASE)
         ┌─────────────▼─────────────┐
         │   Backend   (FastAPI)      │  :8000 (localhost only)
         │   sleep_backend container  │
         └─────────────┬─────────────┘
                       │ SQLAlchemy / psycopg2
         ┌─────────────▼─────────────┐
         │   Database  (PostgreSQL)   │
         │   sleep_db container       │
         └───────────────────────────┘
```

| Layer | Technology |
|---|---|
| **Frontend** | SvelteKit (Svelte + TypeScript), Vite |
| **Backend** | Python, FastAPI, Uvicorn |
| **ORM / Migrations** | SQLAlchemy, Alembic |
| **Database** | PostgreSQL 15 |
| **Garmin Client** | `garminconnect`, `curl_cffi` |
| **Containerisation** | Docker, Docker Compose |
| **Image Registry** | GitHub Container Registry (GHCR) |
| **Auto-updates** | Watchtower (production) |

---

## 🗂️ Project Structure

```
sleep-wellness-tracker/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, autosync background thread
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── database.py          # DB session & connection
│   │   ├── garmin_client.py     # Garmin Connect API client
│   │   ├── routes/
│   │   │   ├── mood.py
│   │   │   ├── categories.py
│   │   │   ├── activities.py
│   │   │   ├── garmin.py        # Garmin sync & data endpoints
│   │   │   ├── lifestyle_impact.py
│   │   │   └── export.py
│   │   └── services/
│   │       └── garmin_sync.py   # Per-metric sync logic
│   ├── Dockerfile
│   └── requirements.txt
├── frontend-web/
│   ├── src/
│   │   ├── routes/
│   │   │   ├── +layout.svelte       # App shell / navigation
│   │   │   ├── analytics/           # Analytics dashboard
│   │   │   ├── garmin-log/          # Garmin data log view
│   │   │   ├── garmin-lifestyle-impact/ # Biometric vs lifestyle
│   │   │   ├── mood-entry/          # New mood entry form
│   │   │   ├── mood-log/            # Mood history
│   │   │   ├── manage-activities/   # Activity management
│   │   │   ├── manage-categories/   # Category management
│   │   │   └── settings/            # App & Garmin settings
│   │   └── lib/                     # Shared components & utilities
│   └── Dockerfile
├── db/                          # Database migration files
├── scripts/                     # Utility scripts
├── .github/workflows/
│   ├── main.yml                 # Builds ARM64 images
│   └── build-amd64.yml          # Builds & pushes AMD64 images to GHCR
├── docker-compose.yml           # Local development stack
├── docker-compose.prod.yml      # Production stack (NUC deployment)
├── bulk_insert.sh               # Bulk data import script
└── .env.example                 # Environment variable template
```

---

## 🚀 Deployment

### Prerequisites
- Docker & Docker Compose
- A Garmin Connect account
- A `.env` file (copy from `.env.example`)

### Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```dotenv
# Database
POSTGRES_USER=sleepuser
POSTGRES_PASSWORD=change_me_strong_password
POSTGRES_DB=sleepdb
DATABASE_URL=postgresql://sleepuser:change_me_strong_password@db:5432/sleepdb

# Garmin Connect credentials
GARMIN_EMAIL=your@email.com
GARMIN_PASSWORD=your_garmin_password
GARMIN_TOKEN_DIR=/app/garmin_tokens

# How many days of history to backfill on first sync
GARMIN_SLEEP_BACKFILL_DAYS=30
GARMIN_BODY_BACKFILL_DAYS=30
GARMIN_HRV_BACKFILL_DAYS=30
GARMIN_RHR_BACKFILL_DAYS=30
GARMIN_STRESS_BACKFILL_DAYS=30
GARMIN_HYDRATION_BACKFILL_DAYS=30

# Enable/disable the background autosync loop
GARMIN_AUTOSYNC_ENABLED=true

# Production image references (GHCR)
BACKEND_IMAGE=ghcr.io/notascooby25/sleep-wellness-tracker-backend:latest
FRONTEND_WEB_IMAGE=ghcr.io/notascooby25/sleep-wellness-tracker-frontend-web:latest
```

### Local Development

```bash
docker compose -f docker-compose.yml up --build
```

Frontend will be available at **http://localhost:8510**

### Production (NUC)

The production stack uses pre-built images pulled from GHCR and includes **Watchtower** for automatic image update polling (every 5 minutes):

```bash
docker compose -f docker-compose.prod.yml up -d
```

---

## ⚙️ CI / CD

Two GitHub Actions workflows build Docker images and push them to GHCR:

| Workflow | Trigger | Target |
|---|---|---|
| `build-amd64.yml` | Push to `main` | AMD64 images → GHCR |
| `main.yml` | Manual (`workflow_dispatch`) | ARM64 images (build artefacts) |

The production NUC runs the AMD64 images. Watchtower polls GHCR every 5 minutes and automatically pulls & restarts updated containers.

---

## 🗄️ Database

> **⚠️ Important:** Always take a database backup before making any schema changes or running migrations.

```bash
# Backup
docker exec sleep_db pg_dump -U sleepuser sleepdb > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore
docker exec -i sleep_db psql -U sleepuser sleepdb < backup_YYYYMMDD_HHMMSS.sql
```

The database schema is managed with **Alembic** migrations (located in `db/`).

### Automated Backups (Every 12 Hours, Keep Latest 4)

Use the included scripts to run a backup every 12 hours and keep only the latest 4 backup snapshots.

```bash
# Install/update cron entry for the current user
./scripts/setup_db_backup_cron.sh

# Verify
crontab -l | grep run_db_backup_rotation.sh
```

What gets installed:

```cron
0 */12 * * * MAX_BACKUPS=4 BACKUP_DIR=/srv/shared/backups /home/andyl/sleep-wellness-tracker/scripts/run_db_backup_rotation.sh >> /srv/shared/backups/db_backup_cron.log 2>&1
```

Manual run (same logic as cron):

```bash
./scripts/run_db_backup_rotation.sh
```

Retention behavior:
- A snapshot is all files that share one timestamp stem (for example `.dump` + `.sql.gz`).
- Cleanup keeps the newest 4 snapshots and removes older ones.

### Data Models

| Table | Description |
|---|---|
| `moods` | Mood entries — score, notes, timestamp |
| `activities` | User-defined activities |
| `categories` | Activity categories with optional rating config |
| `mood_activities` | Many-to-many: mood entries ↔ activities |
| `garmin_sleep_daily` | Daily sleep data from Garmin |
| `garmin_body_battery_daily` | Daily body battery metrics |
| `garmin_hrv_daily` | Daily HRV & baseline |
| `garmin_resting_heart_rate_daily` | Daily resting heart rate |
| `garmin_stress_daily` | Daily stress breakdown |
| `garmin_hydration_daily` | Daily hydration vs goal |
| `garmin_steps_daily` | Daily steps, distance, calories |
| `garmin_activities` | Individual Garmin workout records |
| `garmin_sync_state` | Tracks last sync time per metric |

---

## 🔮 Roadmap / Planned Features

- [ ] Deeper Garmin sleep data integration (full sleep stage timelines)
- [ ] Expanded analytics with correlation charts (e.g. mood vs. HRV, sleep score vs. stress)
- [ ] Additional biometric data sources
- [ ] Richer export formats (CSV, JSON)

---

## 🛠️ Tech Stack Summary

| | |
|---|---|
| **Backend language** | Python 3 |
| **API framework** | FastAPI |
| **Frontend framework** | SvelteKit |
| **Database** | PostgreSQL 15 |
| **Containerisation** | Docker / Docker Compose |
| **Image registry** | GitHub Container Registry (GHCR) |
| **Auto-update** | Watchtower |
| **Development OS** | Fedora Linux |
| **Deployment target** | Intel NUC (self-hosted) |
