#!/bin/bash
# remove_legacy_meetingmind.sh
#
# Purpose:
#   Cleanly remove the legacy MeetingMind launch agent so that the new
#   Context Recall launch agent (dev.jamiewhite.contextrecall.agent) can
#   run without conflict.
#
#   By default this script ONLY unloads the legacy launchd job and removes
#   the legacy plist at ~/Library/LaunchAgents/com.meetingmind.agent.plist.
#   Your recordings, transcripts, summaries, configuration and log files
#   are preserved. The script will print the legacy data paths it found
#   so you can review or remove them yourself.
#
#   Pass --delete-legacy-data to additionally delete the legacy data,
#   config, cache and log directories. You will be asked to confirm with
#   a typed "yes" before anything is removed, and the size of each
#   directory is printed so you know what you are losing.
#
# Usage:
#   ./scripts/remove_legacy_meetingmind.sh
#   ./scripts/remove_legacy_meetingmind.sh --delete-legacy-data
#
# Notes:
#   - This script is intentionally conservative. It does not touch the
#     new Context Recall agent, plist, or data directories.
#   - If both the legacy and new agents are loaded the script aborts so
#     you can decide which to keep.

set -euo pipefail

LEGACY_LABEL="com.meetingmind.agent"
LEGACY_PLIST="$HOME/Library/LaunchAgents/com.meetingmind.agent.plist"
NEW_LABEL="dev.jamiewhite.contextrecall.agent"

DELETE_LEGACY_DATA="no"

for arg in "$@"; do
    case "$arg" in
        --delete-legacy-data)
            DELETE_LEGACY_DATA="yes"
            ;;
        -h|--help)
            cat <<'USAGE'
remove_legacy_meetingmind.sh

Removes the legacy MeetingMind launch agent and (optionally) its data.

Usage:
  ./scripts/remove_legacy_meetingmind.sh
  ./scripts/remove_legacy_meetingmind.sh --delete-legacy-data

Without flags the script unloads com.meetingmind.agent and removes its
plist only. Recordings, configuration and logs are preserved.

With --delete-legacy-data, after confirmation the script also deletes
the legacy data, config, cache and log directories under ~/Library and
~/.config / ~/.local/share.
USAGE
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            echo "Usage: $0 [--delete-legacy-data]" >&2
            exit 2
            ;;
    esac
done

LEGACY_DATA_PATHS=(
    "$HOME/.config/meetingmind"
    "$HOME/.local/share/meetingmind"
    "$HOME/Library/Logs/meetingmind"
    "$HOME/Library/Logs/MeetingMind"
    "$HOME/Library/Application Support/MeetingMind"
    "$HOME/Library/Caches/MeetingMind"
)

echo "==> Checking launchd state"

NEW_LOADED="no"
if launchctl list "$NEW_LABEL" &>/dev/null; then
    NEW_LOADED="yes"
fi

LEGACY_LOADED="no"
if launchctl list "$LEGACY_LABEL" &>/dev/null; then
    LEGACY_LOADED="yes"
fi

# Refuse to proceed if both are loaded; the user should decide.
if [ "$LEGACY_LOADED" = "yes" ] && [ "$NEW_LOADED" = "yes" ]; then
    echo ""
    echo "WARNING: Both the legacy ($LEGACY_LABEL) and the new"
    echo "         ($NEW_LABEL) launch agents are currently loaded."
    echo "         Please unload the one you do not want first, for example:"
    echo "             launchctl unload \"$LEGACY_PLIST\""
    echo "         then re-run this script."
    exit 1
fi

if [ "$NEW_LOADED" = "yes" ]; then
    echo "    Note: the new agent ($NEW_LABEL) is already loaded; that is fine."
fi

# Unload the legacy agent if it is currently loaded.
if [ "$LEGACY_LOADED" = "yes" ]; then
    if [ -f "$LEGACY_PLIST" ]; then
        echo "==> Unloading legacy agent $LEGACY_LABEL"
        launchctl unload "$LEGACY_PLIST" 2>/dev/null || true
    else
        echo "==> Legacy agent $LEGACY_LABEL is loaded but plist is missing"
        echo "    Attempting to remove via launchctl remove"
        launchctl remove "$LEGACY_LABEL" 2>/dev/null || true
    fi
else
    echo "    Legacy agent $LEGACY_LABEL is not loaded; nothing to unload."
fi

# Remove the legacy plist file if it exists.
if [ -f "$LEGACY_PLIST" ]; then
    echo "==> Removing legacy plist $LEGACY_PLIST"
    rm -f "$LEGACY_PLIST"
else
    echo "    Legacy plist not present at $LEGACY_PLIST"
fi

# Report on legacy data directories.
echo ""
echo "==> Legacy data, config, cache and log directories"
FOUND_PATHS=()
for path in "${LEGACY_DATA_PATHS[@]}"; do
    if [ -e "$path" ]; then
        size=$(du -sh "$path" 2>/dev/null | cut -f1 || echo "?")
        echo "    [present] $path ($size)"
        FOUND_PATHS+=("$path")
    else
        echo "    [absent ] $path"
    fi
done

if [ "${#FOUND_PATHS[@]}" -eq 0 ]; then
    echo ""
    echo "    No legacy data directories were found. Nothing more to do."
    echo ""
    echo "==> Done"
    exit 0
fi

if [ "$DELETE_LEGACY_DATA" != "yes" ]; then
    echo ""
    echo "Data is preserved by default. To delete the directories listed"
    echo "above, re-run with: $0 --delete-legacy-data"
    echo ""
    echo "==> Done"
    exit 0
fi

# --delete-legacy-data path: confirm with typed yes, then delete.
echo ""
echo "You have asked to delete legacy data. The directories above will be"
echo "permanently removed. This cannot be undone."
read -r -p "Type 'yes' to confirm deletion: " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted; no files were deleted."
    exit 1
fi

for path in "${FOUND_PATHS[@]}"; do
    echo "==> Removing $path"
    rm -rf -- "$path"
done

echo ""
echo "==> Legacy data removed."
echo "==> Done"
