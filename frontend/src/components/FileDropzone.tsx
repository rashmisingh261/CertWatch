import { DragEvent, useId, useRef, useState } from "react";

export const MAX_FILE_BYTES = 1_000_000;

interface Props {
  label: string;
  file: File | null;
  disabled?: boolean;
  onChange: (file: File | null) => void;
  onReject: (message: string) => void;
}

function formatSize(n: number): string {
  return n < 1024 ? `${n} B` : `${(n / 1024).toFixed(1)} KB`;
}

export function FileDropzone({ label, file, disabled, onChange, onReject }: Props) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  function accept(f: File | undefined) {
    if (!f) return;
    if (f.size > MAX_FILE_BYTES) {
      onReject(`${label}: file is too large (${formatSize(f.size)}). The limit is 1 MB.`);
      return;
    }
    if (f.size === 0) {
      onReject(`${label}: the selected file is empty.`);
      return;
    }
    onChange(f);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setOver(false);
    if (!disabled) accept(e.dataTransfer.files[0]);
  }

  return (
    <div
      className={`dropzone${over ? " over" : ""}${file ? " has-file" : ""}`}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
    >
      <h3>{label}</h3>
      {file ? (
        <p className="file-name" data-testid={`file-${label}`}>
          📄 {file.name} <span className="muted">({formatSize(file.size)})</span>
        </p>
      ) : (
        <p className="muted">Drag a PEM certificate here, or choose a file.</p>
      )}
      <label htmlFor={id} className="file-button">
        {file ? "Change file" : "Choose file"}
      </label>
      <input
        id={id}
        ref={input}
        className="sr-only"
        type="file"
        aria-label={label}
        accept=".pem,.crt,.cer,.txt,application/x-pem-file"
        disabled={disabled}
        onChange={(e) => {
          accept(e.target.files?.[0]);
          e.target.value = ""; // allow re-selecting the same file
        }}
      />
      {file && !disabled && (
        <button type="button" className="link-button" onClick={() => onChange(null)}>
          Remove
        </button>
      )}
    </div>
  );
}
