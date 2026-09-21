#!/usr/bin/env bash
# backup_host_config.sh — snapshot the NUC's host-level configuration as text.
#
# Everything under /srv is mirrored to the NAS, but the things that make the NUC
# *work* live outside it: the crontab, the systemd user timers, the Tailscale Funnel
# mapping, which containers run on which ports. Lose the host and those are
# reconstructed from memory. This captures them into one small tarball that then
# rides the existing NAS mirror (append-only) and the encrypted Google copy.
#
# Output: $OUT_DIR/host_config_<UTC>.tar.gz   (mode 600; newest KEEP are kept)
#
# Deliberately NOT captured — these are secrets, keep them in a password manager:
#   ~/.config/rclone/rclone.conf   (Google + crypt passwords; only remote *names* are listed)
#   ~/.ssh/*                       (private keys, including the NAS key)
#   ~/.docker/config.json          (registry credentials)
# Values that look like secrets (URLs, tokens, passwords, keys) are redacted from
# everything that is captured, as defence in depth.
#
# Usage:  ./scripts/backup_host_config.sh
# Environment: OUT_DIR (default /srv/shared/backups/host-config), KEEP (default 14),
#   SRV_ROOT (default /srv), NAS_ENV_FILE, GOOGLE_ENV_FILE
#
# Never fails because one probe failed: a section that cannot be captured is noted
# in the archive (and in the log) and the rest is still saved.

set -euo pipefail
umask 077

OUT_DIR="${OUT_DIR:-/srv/shared/backups/host-config}"
KEEP="${KEEP:-14}"
SRV_ROOT="${SRV_ROOT:-/srv}"
NAS_ENV_FILE="${NAS_ENV_FILE:-$HOME/.config/nas-sync.env}"
GOOGLE_ENV_FILE="${GOOGLE_ENV_FILE:-$HOME/.config/google-sync.env}"

log() { echo "[backup_host_config] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

[[ "$KEEP" =~ ^[0-9]+$ && "$KEEP" -ge 1 ]] || die "KEEP must be a positive integer (got: $KEEP)"

# cron gives a minimal environment: no XDG_RUNTIME_DIR, so `systemctl --user` cannot
# find the user manager. Lingering keeps that manager alive; point at its socket.
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
uid="$(id -u)"
if [[ -z "${XDG_RUNTIME_DIR:-}" && -d "/run/user/$uid" ]]; then
    XDG_RUNTIME_DIR="/run/user/$uid"
    export XDG_RUNTIME_DIR
fi
if [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" && -n "${XDG_RUNTIME_DIR:-}" ]]; then
    DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
    export DBUS_SESSION_BUS_ADDRESS
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"

STAGE="$(mktemp -d)"
FINAL="$OUT_DIR/host_config_${STAMP}.tar.gz"
TMP_TAR="$FINAL.tmp"
trap 'rm -rf -- "$STAGE" "$TMP_TAR"' EXIT

NOTES=()

# capture <relative-output-file> <command> [args...]
capture() {
    local out="$STAGE/$1"; shift
    mkdir -p "$(dirname "$out")"
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "(not captured: '$1' is not installed)" > "$out"
        NOTES+=("$1 not installed")
        return 0
    fi
    if ! "$@" > "$out" 2>&1; then
        echo "(command exited non-zero: $*)" >> "$out"
        NOTES+=("failed: $*")
    fi
    return 0
}

# capture_env <relative-output-file> <env-file>: keep the shape of a key=value file
# but blank anything that could be a credential, whatever the key is called.
capture_env() {
    local out="$STAGE/$1" src="$2"
    if [[ -f "$src" ]]; then
        sed -E 's/^([A-Za-z0-9_]*(URL|TOKEN|PASS|PASSWORD|SECRET|KEY)[A-Za-z0-9_]*)=.*/\1=<redacted>/' "$src" > "$out"
    else
        echo "(not present: $src)" > "$out"
    fi
}

# ── scheduling ────────────────────────────────────────────────────────────────
capture crontab.txt crontab -l
capture systemd-user/list-timers.txt systemctl --user list-timers --all --no-pager
capture systemd-user/linger.txt loginctl show-user "$(id -un)" --property=Linger
if [[ -d "$HOME/.config/systemd/user" ]]; then
    mkdir -p "$STAGE/systemd-user/units"
    find "$HOME/.config/systemd/user" -maxdepth 1 -type f \( -name '*.service' -o -name '*.timer' \) \
        -exec cp -- {} "$STAGE/systemd-user/units/" \;
fi

# ── exposure, containers, remotes ─────────────────────────────────────────────
capture tailscale/funnel-status.txt tailscale funnel status
capture tailscale/serve-status.txt tailscale serve status
capture docker/ps.txt docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
capture docker/volumes.txt docker volume ls
capture rclone/remote-names.txt rclone listremotes
capture_env nas-sync.env.redacted "$NAS_ENV_FILE"
capture_env google-sync.env.redacted "$GOOGLE_ENV_FILE"

# ── the host itself ───────────────────────────────────────────────────────────
capture system/os-release.txt cat /etc/os-release
capture system/uname.txt uname -a
capture system/df.txt df -hT
capture system/fstab.txt cat /etc/fstab
capture system/srv-listing.txt ls -la "$SRV_ROOT" "$SRV_ROOT"/shared
{
    for tool in docker rclone rsync tailscale; do
        if command -v "$tool" >/dev/null 2>&1; then
            printf '%s: ' "$tool"; "$tool" --version 2>&1 | sed -n '1p'
        else
            printf '%s: not installed\n' "$tool"
        fi
    done
} > "$STAGE/system/versions.txt" 2>&1 || true

# ── what each checkout is on, and what is edited only on this host ────────────
# `git diff` matters: a NUC-only edit (e.g. a compose override) is in no repo and,
# apart from the NAS folder mirror, in no backup.
mkdir -p "$STAGE/git"
for d in "$SRV_ROOT"/*/; do
    [[ -d "${d}.git" ]] || continue
    name="$(basename "$d")"
    {
        echo "# HEAD";          git -C "$d" log -1 --format='%H %s' 2>&1 || true
        echo "# remotes";       git -C "$d" remote -v 2>&1 || true
        echo "# status";        git -C "$d" status --short 2>&1 | sed -n '1,50p' || true
        echo "# diff (first 400 lines)"; git -C "$d" diff 2>&1 | sed -n '1,400p' || true
    } > "$STAGE/git/${name}.txt"
done

cat > "$STAGE/README.txt" <<EOF
Host configuration snapshot taken ${STAMP} on $(hostname).
Use it to rebuild the NUC's cron jobs, timers, Funnel mapping and container layout.
Secrets are NOT in here: rclone.conf, SSH keys and docker credentials must come from
your password manager. See docs/nuc-backup-overview.md in the sleepwell repo.
EOF
if (( ${#NOTES[@]} > 0 )); then
    { echo "Sections that could not be fully captured:"; printf ' - %s\n' "${NOTES[@]}"; } >> "$STAGE/README.txt"
fi

# ── redact, pack, promote ─────────────────────────────────────────────────────
# Applied to every captured file, not just env files: catches a URL, credential in a
# git remote, or an inline password in an fstab or unit file.
find "$STAGE" -type f -print0 | xargs -0 -r sed -i -E \
    -e 's#(hc-ping\.com/)[A-Za-z0-9-]+#\1<redacted>#g' \
    -e 's#(://)[^/@[:space:]]+@#\1<redacted>@#g' \
    -e 's#((password|passwd|token|secret|apikey|api_key)=)[^[:space:],]*#\1<redacted>#Ig'

tar -czf "$TMP_TAR" -C "$STAGE" .
tar -tzf "$TMP_TAR" >/dev/null || die "Snapshot archive is unreadable: $TMP_TAR"
mv -- "$TMP_TAR" "$FINAL"
chmod 600 "$FINAL"

# ── retention ─────────────────────────────────────────────────────────────────
mapfile -t archives < <(find "$OUT_DIR" -maxdepth 1 -type f -name 'host_config_*.tar.gz' -printf '%f\n' | sort -r)
if (( ${#archives[@]} > KEEP )); then
    for old in "${archives[@]:KEEP}"; do
        rm -f -- "$OUT_DIR/$old"
        log "Pruned old snapshot: $old"
    done
fi

if (( ${#NOTES[@]} > 0 )); then
    log "Warning: ${#NOTES[@]} section(s) not fully captured (see README.txt in the archive)."
fi
log "Snapshot: $FINAL ($(wc -c < "$FINAL") bytes)"
