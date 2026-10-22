import type { CSSProperties } from 'react';
import styles from './StepList.module.css';

export interface StepItem {
  title: string;
  /** note — просто пункт списка (советы), без статуса. */
  state: 'done' | 'current' | 'todo' | 'note';
}

/** Короткий список шагов с галочками: что банк уже сделал и что делает сейчас. */
export function StepList({ items }: { items: StepItem[] }) {
  return (
    <ol className={styles.list}>
      {items.map((item, i) => (
        <li key={item.title} className={`${styles.item} ${styles[item.state]}`} style={{ '--i': i } as CSSProperties}>
          <span className={styles.mark} aria-hidden="true">
            {item.state === 'done' && (
              <svg viewBox="0 0 16 16" width="12" height="12">
                <path d="m3.5 8.5 3 3 6-7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </span>
          <span className={styles.title}>{item.title}</span>
        </li>
      ))}
    </ol>
  );
}
