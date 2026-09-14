# Encrypted Cloud Backup Access Guide

This guide explains how to use the terminal to view, access, and restore your encrypted backup files stored on Google Drive.

## How it Works

Your offsite backups are stored on Google Drive, but they are protected by **client-side encryption** using `rclone`. This means that if you look at your Google Drive through the web browser, you will only see scrambled file names and unreadable contents. 

To read or restore these files, you must use the `rclone` command-line tool on a machine that has your `rclone.conf` and the decryption password configured. The configured remote is called `gdrive-crypt`.

## Prerequisites

You need access to a terminal where `rclone` is installed and the `gdrive-crypt` remote is configured. This is typically your NUC, but it can be any machine where you have securely copied your `~/.config/rclone/rclone.conf`.

---

## 1. Viewing the Encrypted Files

To see a human-readable list of your backed-up files, use the `ls` or `lsf` (list files) command. `rclone` will decrypt the names on the fly.

**List all files and directories:**
```bash
rclone lsf gdrive-crypt:backups/sleep-wellness
```

**List files with sizes and modification times:**
```bash
rclone lsl gdrive-crypt:backups/sleep-wellness
```

---

## 2. Restoring Specific Files

If you need to recover a specific database dump or mood image archive, you can copy it back to your local machine. 

**Command Syntax:**
```bash
rclone copy gdrive-crypt:backups/sleep-wellness/<filename> <local-destination-directory> --progress
```

**Example - Restoring a single database dump to `/tmp/recover`:**
```bash
mkdir -p /tmp/recover
rclone copy gdrive-crypt:backups/sleep-wellness/sleepdb_20260914T120000Z.dump /tmp/recover/ --progress
```
*Note: The file will be decrypted automatically as it downloads.*

---

## 3. Restoring Everything (Full Disaster Recovery)

If you have completely lost your local server and NAS, you can pull the entire backup repository down from Google Drive.

**Command:**
```bash
mkdir -p /srv/shared/recovered-backups
rclone copy gdrive-crypt:backups/sleep-wellness/ /srv/shared/recovered-backups/ --progress
```
*This will download all DB dumps, mood image tarballs, and manifest files.*

---

## 4. Mounting the Cloud Drive Locally (Advanced)

If you don't want to download the files immediately, you can mount the encrypted Google Drive as if it were a local folder on your computer. You can then browse it using standard tools like `ls`, `cat`, or `cp`.

**Create a mount point and mount it:**
```bash
mkdir -p /mnt/google_backups
rclone mount gdrive-crypt:backups/sleep-wellness /mnt/google_backups --daemon
```

Now, if you list the contents of `/mnt/google_backups`, you will see your decrypted files:
```bash
ls -lh /mnt/google_backups
```

**To unmount when finished:**
```bash
fusermount -u /mnt/google_backups
```

---

## Troubleshooting

- **`Failed to create file system for...`**: Ensure your `rclone.conf` is correctly located (usually `~/.config/rclone/rclone.conf`) and that the Google Drive API tokens haven't expired.
- **`rclone: command not found`**: Ensure `rclone` is installed on your current system (`sudo apt install rclone` or via curl install script).

