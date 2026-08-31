import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message, Source } from "../types";

interface Props {
  message: Message;
  sources?: Source[];
  streaming?: boolean;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function sourceDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export default function ChatMessage({ message, sources, streaming }: Props) {
  const isUser = message.role === "user";
  const time = formatTime(message.created_at);

  return (
    <div className={`msg-row ${isUser ? "msg-user" : "msg-ai"}`}>
      {!isUser && <div className="msg-avatar">AI</div>}
      <div className={`msg-bubble ${isUser ? "bubble-user" : "bubble-ai"}`}>
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content || (streaming ? "…" : "")}
            </ReactMarkdown>
          </div>
        )}
        {streaming && <span className="blink-cursor">▌</span>}

        {sources && sources.length > 0 && !isUser && (
          <div className="msg-sources">
            {sources.map((s) =>
              s.source_type === "web" ? (
                <span
                  key={`web-${s.index}`}
                  className="source-chip source-web"
                  title={`${s.snippet}\n${s.url ?? ""}`}
                >
                  🌐 [网{s.index}] {s.filename} · {s.url ? sourceDomain(s.url) : ""}
                  <em className="web-tag">来源于网络</em>
                </span>
              ) : (
                <span key={s.index} className="source-chip" title={s.snippet}>
                  📄 [{s.index}] {s.filename}
                </span>
              )
            )}
          </div>
        )}

        {time && !streaming && <div className="msg-time">{time}</div>}
      </div>
    </div>
  );
}
