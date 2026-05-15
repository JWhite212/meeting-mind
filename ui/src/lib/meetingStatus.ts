import type { Meeting } from "./types";

const RETRYABLE_STATUSES = new Set<Meeting["status"]>([
  "error",
  "pending",
  "transcribing",
]);

/**
 * Whether the user can usefully click "Retry / Process" on a meeting.
 *
 * Includes "transcribing" so meetings orphaned by a daemon crash
 * (Bug C2) can be recovered from the UI rather than only after the
 * server-side reset_stale_inflight_meetings flips them to "error".
 */
export function canRetryMeeting(meeting: Meeting): boolean {
  if (!meeting.audio_path) return false;
  return RETRYABLE_STATUSES.has(meeting.status);
}
