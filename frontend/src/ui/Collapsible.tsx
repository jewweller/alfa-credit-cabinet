import type { ReactNode } from 'react';
import styles from './Collapsible.module.css';

/**
 * Свёрнутый по умолчанию блок на нативном <details>. По умолчанию — для тёмной зоны;
 * onSurface — внутри светлой карточки.
 */
export function Collapsible({
  title,
  count,
  onSurface = false,
  children,
}: {
  title: string;
  count?: number;
  onSurface?: boolean;
  children: ReactNode;
}) {
  return (
    <details className={`${styles.details} ${onSurface ? styles.onSurface : ''}`}>
      <summary className={styles.summary}>
        <span className={styles.chevron} aria-hidden="true" />
        {title}
        {count !== undefined && <span className={styles.count}>{String(count).padStart(2, '0')}</span>}
      </summary>
      <div className={styles.content}>{children}</div>
    </details>
  );
}
