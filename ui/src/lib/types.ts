/** TypeScript types matching the Python backend models. */

export type DaemonState = "idle" | "detecting" | "recording" | "processing" | "unknown";

export type MeetingStatus =
  | "recording"
  | "transcribing"
  | "diarising"
  | "summarising"
  | "writing"
  | "complete"
  | "error";

export interface Meeting {
  id: string;
  title: string;
  started_at: number;
  ended_at: number | null;
  duration_seconds: number | null;
  status: MeetingStatus;
  audio_path: string | null;
  transcript_json: string | null;
  summary_markdown: string | null;
  tags: string[];
  language: string | null;
  word_count: number | null;
  created_at: number;
  updated_at: number;
}

export interface MeetingsResponse {
  meetings: Meeting[];
  total: number;
  limit: number;
  offset: number;
}

export interface StatusResponse {
  state: DaemonState;
  timestamp: number;
  active_meeting?: {
    meeting_id: string | null;
    started_at: number;
    elapsed_seconds: number;
  };
}

export interface HealthResponse {
  status: "ok";
  timestamp: number;
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
  speaker: string;
}

/** WebSocket event types pushed from the daemon. */
export type WSEvent =
  | { type: "meeting.detecting"; consecutive: number; required: number }
  | { type: "meeting.started"; started_at: number }
  | { type: "meeting.ended"; duration: number }
  | { type: "pipeline.stage"; meeting_id: string | null; stage: string }
  | { type: "pipeline.progress"; meeting_id: string | null; stage: string; percent: number }
  | { type: "pipeline.complete"; meeting_id: string | null }
  | { type: "pipeline.error"; meeting_id: string | null; stage: string; error: string }
  | { type: "transcript.segment"; meeting_id: string | null; segment: TranscriptSegment }
  | { type: "audio.level"; rms_system: number; rms_mic: number }
  | { type: "daemon.status"; state: DaemonState };
