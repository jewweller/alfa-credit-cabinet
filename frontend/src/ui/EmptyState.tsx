import type { ReactNode } from 'react';
import styles from './EmptyState.module.css';

export function EmptyState({
  eyebrow,
  title,
  text,
  action,
  compact = false,
}: {
  eyebrow?: string;
  title: string;
  text?: string;
  action?: ReactNode;
  /** Компактный вариант — внутри панели, без своей карточки. */
  compact?: boolean;
}) {
  return (
    <div className={`${styles.empty} ${compact ? styles.compact : ''}`}>
      {!compact && (
        <span className={styles.mark} aria-hidden="true">
          <svg viewBox="0 0 24 24" width="22" height="22">
            <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </span>
      )}
      {eyebrow && <p className={styles.eyebrow}>{eyebrow}</p>}
      <h2 className={styles.title}>{title}</h2>
      {text && <p className={styles.text}>{text}</p>}
      {action && <div className={styles.action}>{action}</div>}
    </div>
  );
}
