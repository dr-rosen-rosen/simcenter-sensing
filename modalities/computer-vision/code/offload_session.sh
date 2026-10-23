#!/usr/bin/env bash
# offload_session.sh - push a ZED session directory to the analysis laptop,
# verify every file's SHA-256 remotely, and only then delete the local copy.
#
# Runs ON THE ZEDBOX. Pure stock tooling on both ends: bash/scp/ssh here,
# OpenSSH server + PowerShell on the Windows analysis laptop (no rsync,
# which Windows OpenSSH does not ship).
#
# Usage:
#   ./offload_session.sh                 # newest session dir under ~/zed_rec
#   ./offload_session.sh ~/zed_rec/20261023-141530
#   ./offload_session.sh --dry-run       # show what would happen
#   ./offload_session.sh --keep          # transfer + verify, skip deletion
#
# Config (env vars or edit the defaults):
#   ZED_OFFLOAD_USER   SSH user on the analysis laptop   (default: simcenter)
#   ZED_OFFLOAD_HOST   analysis laptop IP on the lab LAN (REQUIRED)
#   ZED_OFFLOAD_BASE   destination dir, relative to that user's Windows home
#                      (default: sessions/zed - avoids C: drive-letter quoting)
#
# First-time Windows setup (one-time, on the analysis laptop):
#   Settings > System > Optional features > Add "OpenSSH Server",
#   then: Start-Service sshd; Set-Service sshd -StartupType Automatic
set -euo pipefail

DEST_USER="${ZED_OFFLOAD_USER:-simcenter}"
DEST_HOST="${ZED_OFFLOAD_HOST:-}"
DEST_BASE="${ZED_OFFLOAD_BASE:-sessions/zed}"
REC_ROOT="${ZED_REC_ROOT:-$HOME/zed_rec}"

DRY_RUN=0
KEEP=0
SESSION_DIR=""
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --keep)    KEEP=1 ;;
        -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)         SESSION_DIR="$arg" ;;
    esac
done

if [[ -z "$DEST_HOST" ]]; then
    echo "ERROR: set ZED_OFFLOAD_HOST to the analysis laptop's IP (e.g. 192.168.1.100)" >&2
    exit 1
fi

# Newest session directory if none given
if [[ -z "$SESSION_DIR" ]]; then
    SESSION_DIR=$(find "$REC_ROOT" -mindepth 1 -maxdepth 1 -type d | sort | tail -1)
fi
if [[ -z "$SESSION_DIR" || ! -d "$SESSION_DIR" ]]; then
    echo "ERROR: no session directory found (looked in $REC_ROOT)" >&2
    exit 1
fi
SESSION_NAME=$(basename "$SESSION_DIR")
DEST_DIR="$DEST_BASE/$SESSION_NAME"
REMOTE="$DEST_USER@$DEST_HOST"

FILES=()
while IFS= read -r f; do FILES+=("$f"); done < <(find "$SESSION_DIR" -maxdepth 1 -type f | sort)
if [[ ${#FILES[@]} -eq 0 ]]; then
    echo "ERROR: $SESSION_DIR contains no files" >&2
    exit 1
fi

echo "Session:     $SESSION_DIR  (${#FILES[@]} file(s), $(du -sh "$SESSION_DIR" | cut -f1))"
echo "Destination: $REMOTE:$DEST_DIR"
if [[ $DRY_RUN -eq 1 ]]; then
    printf '  would copy: %s\n' "${FILES[@]##*/}"
    echo "(dry run - nothing transferred)"
    exit 0
fi

# 1. Local checksums (also shipped alongside the data as provenance).
#    sha256sum on the ZedBox (Ubuntu); shasum fallback covers macOS testing.
if command -v sha256sum >/dev/null; then SHA="sha256sum"; else SHA="shasum -a 256"; fi
echo "[1/4] computing local SHA-256..."
MANIFEST="$SESSION_DIR/SHA256SUMS"
( cd "$SESSION_DIR" && $SHA $(printf '%q ' "${FILES[@]##*/}") > SHA256SUMS )

# 2. Create remote dir + copy (3 ssh round-trips total; use ssh keys to
#    avoid repeated password prompts - see README)
echo "[2/4] creating remote directory..."
ssh "$REMOTE" "powershell -NoProfile -Command \"New-Item -ItemType Directory -Force -Path '$DEST_DIR' | Out-Null\""

echo "[3/4] copying..."
scp -p "${FILES[@]}" "$MANIFEST" "$REMOTE:$DEST_DIR/"

# 3. Remote hashes, compared name-by-name
echo "[4/4] verifying remote checksums..."
REMOTE_HASHES=$(ssh "$REMOTE" "powershell -NoProfile -Command \"Get-ChildItem -LiteralPath '$DEST_DIR' -File | Where-Object { \\\$_.Name -ne 'SHA256SUMS' } | Get-FileHash -Algorithm SHA256 | ForEach-Object { \\\$_.Hash.ToLower() + ' ' + (Split-Path -Leaf \\\$_.Path) }\"")

FAIL=0
while read -r want_hash fname; do
    got_hash=$(printf '%s\n' "$REMOTE_HASHES" | awk -v f="$fname" '$2 == f {print $1}')
    if [[ "$got_hash" == "$want_hash" ]]; then
        echo "  ok   $fname"
    else
        echo "  FAIL $fname (local ${want_hash:0:12}... remote ${got_hash:0:12}...)" >&2
        FAIL=1
    fi
done < <(sed 's/  */ /' "$MANIFEST" | sed 's#\./##')

if [[ $FAIL -ne 0 ]]; then
    echo "VERIFICATION FAILED - local copy retained at $SESSION_DIR" >&2
    exit 2
fi

echo "All files verified on $DEST_HOST."
if [[ $KEEP -eq 1 ]]; then
    echo "--keep set: local copy retained at $SESSION_DIR"
else
    read -r -p "Delete local copy at $SESSION_DIR? [y/N] " ans
    if [[ "$ans" == "y" || "$ans" == "Y" ]]; then
        rm -rf "$SESSION_DIR"
        echo "Local copy deleted. ZedBox SSD is clear for the next session."
    else
        echo "Local copy retained."
    fi
fi
