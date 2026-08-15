import type { Session, DocRecord, Message, UploadResult, StreamEvent } from "../types";

const BASE = "/api";

// ---- Upload ----

export async function uploadFiles(files: File[]): Promise<UploadResult[]> {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: fd });
  return res.json();
}

export async function getDocuments(): Promise<DocRecord[]> {
  const res = await fetch(`${BASE}/documents`);
  return res.json();
}

export async function deleteDocument(id: string): Promise<void> {
  await fetch(`${BASE}/documents/${id}`, { method: "DELETE" });
}

// ---- Sessions ----

export async function getSessions(): Promise<Session[]> {
  const res = await fetch(`${BASE}/sessions`);
  return res.json();
}

export async function createSession(): Promise<Session> {
  const res = await fetch(`${BASE}/sessions`, { method: "POST" });
  return res.json();
}

export async function deleteSession(id: string): Promise<void> {
  await fetch(`${BASE}/sessions/${id}`, { method: "DELETE" });
}

export async function getMessages(sessionId: string): Promise<Message[]> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/messages`);
  return res.json();
}

// ---- Chat SSE ----

export interface ChatHandlers {
  onSources: (sources: StreamEvent & { type: "sources" }) => void;
  onDelta: (content: string) => void;
  onDone: () => void;
  onError: (msg: string) => void;
}

export function streamChat(
  sessionId: string,
  message: string,
  handlers: ChatHandlers
): AbortController {
  const controller = new AbortController();

  fetch(`${BASE}/chat/${sessionId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "请求失败" }));
        handlers.onError(err.detail || "请求失败");
        return;
      }
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n\n");
        buf = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const evt: StreamEvent = JSON.parse(line.slice(6));
            switch (evt.type) {
              case "sources":
                handlers.onSources(evt);
                break;
              case "delta":
                handlers.onDelta(evt.content);
                break;
              case "done":
                handlers.onDone();
                break;
              case "error":
                handlers.onError(evt.message);
                break;
            }
          } catch { /* skip malformed lines */ }
        }
      }
    })
    .catch((e) => {
      if (e.name !== "AbortError") {
        handlers.onError(e.message || "网络错误");
      }
    });

  return controller;
}
