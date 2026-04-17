# Deploying Sleep Wellness Tracker on Synology DS223 (ARM64)

This guide covers deploying the Sleep Wellness Tracker on a Synology DS223 NAS, which uses an **ARM64 (aarch64)** processor.

---

## Prerequisites

1. **Synology Container Manager** installed from the Package Center (replaces the older Docker package).
2. **SSH access** enabled on the NAS (*Control Panel → Terminal & SNMP → Enable SSH service*).
3. A terminal client (e.g., PuTTY on Windows, or the built-in terminal on macOS/Linux).

---

## Why ARM64?

The Synology DS223 uses a Realtek RTD1619B SoC, which is ARM64-based. Docker images built or pulled for `linux/amd64` (x86-64) will **not run natively** on this device and will produce the error:

```
The requested image's platform (linux/amd64) does not match the detected host platform (linux/arm64/v8)
```

All Dockerfiles in this project have been updated to omit any hardcoded `--platform` flags so that Docker automatically selects the correct architecture for the host.

---

## Step 1 – Copy Project Files to the NAS

Transfer the project directory to your NAS via SSH or File Station. A common location is:

```
/volume1/docker/sleep-wellness-tracker/
```

Using `scp` from your local machine:

```bash
scp -r ./sleep-wellness-tracker admin@<NAS_IP>:/volume1/docker/
```

---

## Step 2 – Verify the `.env` File

Ensure the `.env` file in the project root contains the following values. The defaults work out of the box for a single-host Docker Compose deployment:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=postgres
DATABASE_URL=postgresql://postgres:postgres@db:5432/postgres
API_BASE=http://sleep_backend:8000
```

> **Security note:** Change `POSTGRES_PASSWORD` to a strong password before deploying in a non-test environment.

---

## Step 3 – Build and Start the Containers

SSH into the NAS and navigate to the project directory:

```bash
ssh admin@<NAS_IP>
cd /volume1/docker/sleep-wellness-tracker
```

Pull base images and build the project images for ARM64:

```bash
docker compose build --no-cache
docker compose up -d
```

Docker will automatically select ARM64-compatible base images (`python:3.11-slim` and `postgres:15` both publish multi-architecture manifests).

---

## Step 4 – Verify the Deployment

Check that all three containers are running:

```bash
docker compose ps
```

Expected output (all services should show `running`):

```
NAME             IMAGE                                    STATUS
sleep_db         postgres:15                              running
sleep_backend    sleep-wellness-tracker-backend:latest    running
sleep_frontend   sleep-wellness-tracker-frontend:latest   running
```

Open the frontend in a browser:

```
http://<NAS_IP>:8501
```

The backend API docs are available at:

```
http://<NAS_IP>:8000/docs
```

---

## Troubleshooting

### Platform mismatch error
If you still see a platform mismatch error after rebuilding, confirm you are not using a cached image that was originally built on an x86-64 machine:

```bash
docker compose down --rmi all
docker compose build --no-cache
docker compose up -d
```

### Backend fails to connect to the database
The backend uses `db` as the hostname for PostgreSQL (the Docker Compose service name). Ensure the `DATABASE_URL` in `.env` uses `@db:5432` and not `localhost`.

### Port conflicts
If ports 8000 or 8501 are already in use, edit `docker-compose.yml` and change the host-side port mapping:

```yaml
ports:
  - "8080:8000"   # map host port 8080 → container port 8000
```

### Viewing logs

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f db
```

---

## Updating the Application

After pulling new code changes:

```bash
git pull
docker compose build --no-cache
docker compose up -d
```

To restart a single service without rebuilding:

```bash
docker compose restart frontend
```
