import { useCallback, useRef, useState } from "react";

interface Props {
  onUpload: (files: File[]) => void;
  uploading: boolean;
}

export default function FileDrop({ onUpload, uploading }: Props) {
  const [dragover, setDragover] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragover(false);
      const files = Array.from(e.dataTransfer.files).filter(
        (f) => f.name.match(/\.(pdf|txt|docx)$/i) || f.type.match(/(pdf|text|word)/)
      );
      if (files.length) onUpload(files);
    },
    [onUpload]
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) {
      onUpload(Array.from(e.target.files));
      e.target.value = "";
    }
  };

  return (
    <div
      className={`file-drop ${dragover ? "dragover" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setDragover(true); }}
      onDragLeave={() => setDragover(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.txt,.docx"
        style={{ display: "none" }}
        onChange={handleChange}
      />
      <div className="file-drop-icon">📄</div>
      <p className="file-drop-text">
        {uploading
          ? "上传中..."
          : "拖拽 PDF / TXT / DOCX 文件到此处，或点击选择"}
      </p>
    </div>
  );
}
