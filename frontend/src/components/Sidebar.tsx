import type { Session } from "../types";

interface Props {
  sessions: Session[];
  activeId: string | null;
  onSelect: (s: Session) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
}

export default function Sidebar({ sessions, activeId, onSelect, onCreate, onDelete }: Props) {
  return (
    <aside className="sidebar">
      <button className="sidebar-new" onClick={onCreate}>
        + 新建对话
      </button>
      <nav className="sidebar-list">
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`sidebar-item ${s.id === activeId ? "active" : ""}`}
            onClick={() => onSelect(s)}
          >
            <span className="sidebar-title">{s.title}</span>
            <button
              className="sidebar-del"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(s.id);
              }}
              title="删除"
            >
              ×
            </button>
          </div>
        ))}
        {sessions.length === 0 && (
          <p className="sidebar-empty">暂无对话，点上方按钮新建</p>
        )}
      </nav>
    </aside>
  );
}
