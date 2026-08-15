import { useState, useEffect, useRef, useCallback } from "react";
import Sidebar from "../components/Sidebar";
import ChatMessage from "../components/ChatMessage";
import {
  getSessions, createSession, deleteSession, getMessages,
  streamChat,
} from "../api";
import type { Session, Message, Source } from "../types";

const SUGGESTIONS = ["这个知识库主要讲了什么？", "帮我总结一下文档内容", "有哪些核心概念？"];

export default function ChatPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeId, setActiveId] = useState<string | null>(
    () => localStorage.getItem("rag_active_session")
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [pendingSources, setPendingSources] = useState<Source[] | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [input, setInput] = useState("");
  const [toast, setToast] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // --- session management ---
  const loadSessions = useCallback(async () => {
    try { setSessions(await getSessions()); } catch { /* */ }
  }, []);

  const switchSession = useCallback((s: Session) => {
    setActiveId(s.id);
    localStorage.setItem("rag_active_session", s.id);
    setPendingSources(null);
    abortRef.current?.abort();
    setStreaming(false);
  }, []);

  const newSession = useCallback(async () => {
    const s = await createSession();
    await loadSessions();
    switchSession(s);
  }, [loadSessions, switchSession]);

  const removeSession = useCallback(async (id: string) => {
    await deleteSession(id);
    await loadSessions();
    if (id === activeId) {
      const remaining = sessions.filter((s) => s.id !== id);
      if (remaining.length > 0) {
        switchSession(remaining[0]);
      } else {
        const s = await createSession();
        await loadSessions();
        switchSession(s);
      }
    }
  }, [activeId, sessions, loadSessions, switchSession, createSession]);

  // --- init ---
  useEffect(() => {
    (async () => {
      let list = await getSessions();
      if (list.length === 0) {
        await createSession();
        list = await getSessions();
      }
      setSessions(list);
      const sid = localStorage.getItem("rag_active_session");
      const target = list.find((s) => s.id === sid) || list[0];
      setActiveId(target.id);
    })();
  }, []);

  // --- load messages when active session changes ---
  useEffect(() => {
    if (!activeId) return;
    getMessages(activeId).then(setMessages).catch(() => setMessages([]));
    setPendingSources(null);
  }, [activeId]);

  // --- auto scroll ---
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // --- send ---
  const send = async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || streaming || !activeId) return;
    setInput("");
    setPendingSources(null);

    const userMsg: Message = {
      id: Date.now(), session_id: activeId, role: "user", content: msg, created_at: "",
    };
    setMessages((prev) => [...prev, userMsg]);

    const assistantMsg: Message = {
      id: Date.now() + 1, session_id: activeId, role: "assistant", content: "", created_at: "",
    };
    setMessages((prev) => [...prev, assistantMsg]);
    setStreaming(true);

    abortRef.current = streamChat(activeId, msg, {
      onSources: (evt) => setPendingSources(evt.sources),
      onDelta: (content) => {
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          copy[copy.length - 1] = { ...last, content: last.content + content };
          return copy;
        });
      },
      onDone: () => {
        setStreaming(false);
        abortRef.current = null;
        loadSessions();
      },
      onError: (msg) => {
        setToast(msg);
        setStreaming(false);
        abortRef.current = null;
        loadSessions();
      },
    });
  };

  const stop = () => {
    abortRef.current?.abort();
    setStreaming(false);
    setPendingSources(null);
    loadSessions();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="chat-layout">
      <Sidebar
        sessions={sessions}
        activeId={activeId}
        onSelect={switchSession}
        onCreate={newSession}
        onDelete={removeSession}
      />

      <main className="chat-main">
        {messages.length === 0 ? (
          <div className="chat-welcome">
            <h2>RAG 知识库问答</h2>
            <p>上传文档后，在这里向知识库提问</p>
            <div className="suggestions">
              {SUGGESTIONS.map((q) => (
                <button key={q} className="sug-btn" onClick={() => send(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat-messages">
            {messages.map((m, i) => (
              <ChatMessage
                key={m.id}
                message={m}
                sources={i === messages.length - 1 ? pendingSources ?? undefined : undefined}
                streaming={
                  streaming &&
                  i === messages.length - 1 &&
                  m.role === "assistant"
                }
              />
            ))}
            <div ref={bottomRef} />
          </div>
        )}

        <div className="chat-input-bar">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入问题，Enter 发送，Shift+Enter 换行"
            rows={2}
            disabled={streaming}
          />
          {streaming ? (
            <button className="btn-stop" onClick={stop}>
              停止
            </button>
          ) : (
            <button
              className="btn-send"
              disabled={!input.trim()}
              onClick={() => send()}
            >
              发送
            </button>
          )}
        </div>
      </main>

      {toast && (
        <div className="toast toast-error" onClick={() => setToast("")}>
          {toast}
        </div>
      )}
    </div>
  );
}
