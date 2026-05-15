import { describe, it, expect } from "vitest";
import { canRetryMeeting } from "../meetingStatus";
import type { Meeting } from "../types";

function makeMeeting(overrides: Partial<Meeting>): Meeting {
  return {
    id: "test",
    title: "Test",
    started_at: 0,
    ended_at: null,
    duration_seconds: null,
    status: "complete",
    audio_path: "/tmp/x.wav",
    transcript_json: null,
    summary_markdown: null,
    tags: [],
    language: null,
    word_count: null,
    label: "",
    calendar_event_title: "",
    attendees_json: "[]",
    calendar_confidence: 0,
    teams_join_url: "",
    teams_meeting_id: "",
    series_id: null,
    created_at: 0,
    updated_at: 0,
    ...overrides,
  } as Meeting;
}

describe("canRetryMeeting", () => {
  it("returns true for transcribing meeting with audio (Bug C2 fix)", () => {
    // Reproduces the user's stuck state: a meeting frozen in 'transcribing'
    // because the daemon crashed mid-pipeline. Currently the UI hides the
    // Retry button, leaving the user with no recovery action.
    const meeting = makeMeeting({
      status: "transcribing",
      audio_path: "/x.wav",
    });
    expect(canRetryMeeting(meeting)).toBe(true);
  });

  it("returns true for error meeting with audio", () => {
    const meeting = makeMeeting({ status: "error", audio_path: "/x.wav" });
    expect(canRetryMeeting(meeting)).toBe(true);
  });

  it("returns true for pending meeting with audio", () => {
    const meeting = makeMeeting({ status: "pending", audio_path: "/x.wav" });
    expect(canRetryMeeting(meeting)).toBe(true);
  });

  it("returns false for complete meeting", () => {
    const meeting = makeMeeting({ status: "complete", audio_path: "/x.wav" });
    expect(canRetryMeeting(meeting)).toBe(false);
  });

  it("returns false when no audio_path is available", () => {
    // Even if the status is retryable, we can't reprocess without audio.
    const meeting = makeMeeting({ status: "error", audio_path: null });
    expect(canRetryMeeting(meeting)).toBe(false);
  });

  it("returns false for recording status (still in flight)", () => {
    // 'recording' means the daemon believes the meeting is actively being
    // captured — retrying mid-capture would corrupt state.
    const meeting = makeMeeting({ status: "recording", audio_path: "/x.wav" });
    expect(canRetryMeeting(meeting)).toBe(false);
  });
});
