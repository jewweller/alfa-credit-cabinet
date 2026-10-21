import { useId, useRef, useState, type DragEvent } from 'react';
import styles from './FileDrop.module.css';

export interface FileDropProps {
  label: string;
  hint: string;
  accept: string;
  busy?: boolean;
  busyLabel: string;
  error?: string | null;
  onFile: (file: File) => void;
}

/** Зона загрузки: перетащить файл или выбрать на устройстве. */
export function FileDrop({ label, hint, accept, busy = false, busyLabel, error, onFile }: FileDropProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const pick = (files: FileList | null) => {
    const file = files?.[0];
    if (file && !busy) onFile(file);
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    pick(event.dataTransfer.files);
  };

  return (
    <div className={styles.wrap}>
      <label
        htmlFor={inputId}
        className={`${styles.zone} ${dragging ? styles.dragging : ''} ${busy ? styles.busy : ''} ${error ? styles.invalid : ''}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <span className={styles.icon} aria-hidden="true">
          <svg viewBox="0 0 24 24" width="18" height="18">
            <path
              d="M12 16V4m0 0-4.5 4.5M12 4l4.5 4.5M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        <span className={styles.text}>
          <span className={styles.label}>{busy ? busyLabel : label}</span>
          <span className={styles.hint}>{hint}</span>
        </span>
        {busy && <span className={styles.progress} aria-hidden="true" />}
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept={accept}
          className={styles.input}
          disabled={busy}
          onChange={(event) => {
            pick(event.target.files);
            event.target.value = '';
          }}
        />
      </label>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
