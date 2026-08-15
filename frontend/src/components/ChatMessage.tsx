import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message, Source } from "../types";

interface Props {
  message: Message;
  sources?: Source[];
  streaming?: boolean;
}

export default function ChatMessage({ message, sources, streaming }: Props) {
  const isUser = message.role === "user";

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
            {sources.map((s) => (
              <span key={s.index} className="source-chip" title={s.snippet}>
                [{s.index}] {s.filename}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
