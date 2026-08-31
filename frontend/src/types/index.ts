export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface DocRecord {
  id: string;
  filename: string;
  size: number;
  chunk_count: number;
  created_at: string;
}

export interface Message {
  id: number;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface Source {
  index: number;
  filename: string;
  snippet: string;
  source_type?: "local" | "web";
  url?: string;
}

export interface TraceStep {
  step: string;
  detail: string;
}

export interface Trace {
  id: number;
  question: string;
  steps: TraceStep[];
  created_at: string;
}

export type StreamEvent =
  | { type: "sources"; sources: Source[] }
  | { type: "delta"; content: string }
  | { type: "done" }
  | { type: "error"; message: string };

export interface UploadResult {
  id?: string;
  filename: string;
  size?: number;
  chunk_count?: number;
  status: "ok" | "error" | "duplicate";
  message?: string;
}
