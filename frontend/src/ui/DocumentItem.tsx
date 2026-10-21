import type { CSSProperties, ReactNode } from 'react';
import styles from './DocumentItem.module.css';

export interface DocumentFile {
  id: string;
  name: string;
  meta: string;
  onDownload: () => void;
}

export interface DocumentItemProps {
  title: string;
  tag: string;
  /** Обязательный пункт ещё без файла — подсвечиваем. */
  required: boolean;
  done: boolean;
  doneLabel: string;
  files: DocumentFile[];
  index?: number;
  /** Зона загрузки, если загружать сейчас можно. */
  children?: ReactNode;
}

export function DocumentItem({ title, tag, required, done, doneLabel, files, index = 0, children }: DocumentItemProps) {
  return (
    <div
      className={`${styles.item} ${done ? styles.done : ''} ${required && !done ? styles.pending : ''}`}
      style={{ '--i': index } as CSSProperties}
    >
      <div className={styles.head}>
        <span className={styles.check} aria-hidden="true">
          {done && (
            <svg viewBox="0 0 16 16" width="12" height="12">
              <path d="m3.5 8.5 3 3 6-7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </span>
        <p className={styles.title}>{title}</p>
        <span className={styles.tag}>{done ? doneLabel : tag}</span>
      </div>

      {files.length > 0 && (
        <ul className={styles.files}>
          {files.map((file) => (
            <li key={file.id} className={styles.file}>
              <svg className={styles.fileIcon} viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
                <path
                  d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zm0 0v5h5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinejoin="round"
                />
              </svg>
              <button type="button" className={styles.fileName} onClick={file.onDownload}>
                {file.name}
              </button>
              <span className={styles.fileMeta}>{file.meta}</span>
            </li>
          ))}
        </ul>
      )}

      {children}
    </div>
  );
}
