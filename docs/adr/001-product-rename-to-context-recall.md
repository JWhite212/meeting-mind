# ADR 001: Rename MeetingMind to Context Recall

## Context

The original MeetingMind name overlaps with other products in the meeting assistant and transcription space. The project needs a more distinctive name for portfolio presentation, product clarity, and future release polish.

## Decision

Rename the product to Context Recall.

Canonical naming:

- Display name: Context Recall
- Slug: context-recall
- Compact identifier: contextrecall
- Bundle identifier: dev.jamiewhite.contextrecall
- Daemon binary: context-recall-daemon
- Launch Agent: dev.jamiewhite.contextrecall.agent
- macOS data directory: ~/Library/Application Support/Context Recall
- macOS logs: ~/Library/Logs/Context Recall

## Consequences

- Existing local installs may retain old Launch Agents or data directories.
- A legacy cleanup script is provided for old MeetingMind Launch Agent files.
- Existing data is not deleted automatically.
- Branding, documentation, packaging, and release artefacts now use Context Recall.
