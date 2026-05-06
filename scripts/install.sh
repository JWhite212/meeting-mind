#!/bin/bash
# Install the Context Recall launch agent for the current user.
#
# This copies dev.jamiewhite.contextrecall.agent.plist into
# ~/Library/LaunchAgents, substituting the /Users/USER/ placeholder with
# the real home directory, then loads the agent via launchctl.
#
# Usage: ./scripts/install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PLIST_NAME="dev.jamiewhite.contextrecall.agent.plist"
PLIST_LABEL="dev.jamiewhite.contextrecall.agent"
LEGACY_LABEL="com.meetingmind.agent"

PLIST_SRC="$PROJECT_ROOT/$PLIST_NAME"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"
LOG_DIR="$HOME/Library/Logs/Context Recall"
USERNAME="$(whoami)"

echo "==> Installing launch agent for $USERNAME"

# Warn if the legacy MeetingMind agent is still loaded. Do not auto-unload
# it; let the user run the dedicated cleanup script so they can review
# what is removed first.
if launchctl list "$LEGACY_LABEL" &>/dev/null; then
    echo ""
    echo "WARNING: The legacy '$LEGACY_LABEL' launch agent is currently loaded."
    echo "         Run './scripts/remove_legacy_meetingmind.sh' to unload and"
    echo "         remove it before continuing. Aborting to avoid running two"
    echo "         daemons in parallel."
    echo ""
    exit 1
fi

# Substitute the /Users/USER/ placeholder with the real path.
sed "s|/Users/USER/|/Users/$USERNAME/|g" "$PLIST_SRC" > "$PLIST_DST"

# Ensure the log directory exists.
mkdir -p "$LOG_DIR"

# Load the agent (unload first if already loaded, to pick up changes).
if launchctl list "$PLIST_LABEL" &>/dev/null; then
    echo "==> Unloading existing agent"
    launchctl unload "$PLIST_DST" 2>/dev/null || true
fi

launchctl load "$PLIST_DST"

echo ""
echo "==> Launch agent installed"
echo "    Plist:  $PLIST_DST"
echo "    Logs:   $LOG_DIR/"
echo ""
echo "To uninstall:"
echo "    launchctl unload $PLIST_DST"
echo "    rm $PLIST_DST"
