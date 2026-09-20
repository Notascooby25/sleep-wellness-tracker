# Backup System Upgrade & Deployment Guide

This document outlines the steps required to deploy the enhanced backup architecture to your production NUC server. These enhancements include robust concurrency locking (`flock`), increased local retention (14 snapshots), cloud storage pruning (90-day retention), Garmin token backups, and Healthchecks.io dead-man alerting.

---

## 1. Sync the Code to the NUC

Since the script changes were made on your development workstation, you first need to sync them to the NUC. 

If you are using Git to sync your deployment directory, SSH into your NUC and pull the latest changes:

```bash
# SSH into your NUC
cd /srv/sleepwell
git pull
```

*(Ensure that the scripts are executable by running `chmod +x scripts/*.sh` if necessary).*

---

## 2. Set up the Healthchecks.io Alert

We are using a "dead man's switch" approach to alerting. Instead of the script trying to send an email when it fails, it will quietly ping Healthchecks.io when it succeeds. If Healthchecks.io *stops* receiving pings, it knows the server is offline or the cron job is silently failing, and it will alert you.

1. Go to [Healthchecks.io](https://healthchecks.io/) and sign up or log in (it is completely free for this usage).
2. Create a new "Check" and name it something like **Sleep Tracker DB Backup**.
3. Set the schedule to **Every 12 hours** (matching your DB backup cron schedule). You can set a grace period of 1 hour.
4. Copy the unique **Ping URL** provided for that check.
5. Open your `.env` file on the NUC:
   ```bash
   nano /srv/sleepwell/.env
   ```
6. Add the following line to the bottom of the file:
   ```env
   HEALTHCHECK_URL=https://hc-ping.com/your-unique-uuid-here
   ```
7. Save and exit (in nano, press `Ctrl+O`, `Enter`, then `Ctrl+X`).

---

## 3. Update the Cron Job Configuration

The default local retention has been increased from 4 snapshots to 14 (giving you 7 full days of local history). To apply this new setting to your active cron jobs, run the setup script:

```bash
cd /srv/sleepwell
./scripts/setup_db_backup_cron.sh
```

You can verify the cron job was updated correctly by running:
```bash
crontab -l
```
You should see `MAX_BACKUPS=14` in the `db_backup_rotation.sh` line.

---

## 4. Run a Disaster Recovery Drill (Optional but Recommended)

You can now instantly verify that your backups actually work. We created a brand new script that acts as an automated fire-drill.

```bash
cd /srv/sleepwell
./scripts/test_restore_dump.sh
```

**What this script does:**
1. Silently spins up a temporary PostgreSQL Docker container.
2. Finds your latest `.dump` backup file.
3. Restores the database into the temporary container.
4. Queries the database to count the rows (ensuring your moods and activities are actually there).
5. Cleans up and destroys the temporary container automatically.

If the script outputs `DR Test Passed successfully`, your backup architecture is 100% verified and working!

