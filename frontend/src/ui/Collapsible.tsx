import type { ReactNode } from 'react';
import styles from './Collapsible.module.css';

/** Свёрнутый по умолчанию блок на нативном <details>. */
export function Collapsible({ title, count, children }: { title: string; count?: number; children: ReactNode }) {
  return (
    <details className={styles.details}>
      <summary className={styles.summary}>
        <span className={styles.chevron} aria-hidden="true" />
        {title}
        {count !== undefined && <span className={styles.count}>{String(count).padStart(2, '0')}</span>}
      </summary>
      <div className={styles.content}>{children}</div>
    </details>
  );
}
