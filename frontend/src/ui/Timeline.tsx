import type { CSSProperties } from 'react';
import styles from './Timeline.module.css';

export interface TimelineEntry {
  key: string;
  title: string;
  meta: string;
  time: string;
  /** current — где заявка сейчас; failed — отказ; complete — путь завершён успешно. */
  state: 'past' | 'current' | 'failed' | 'complete';
}

/** Вертикальная история статусов, свежие сверху. */
export function Timeline({ entries }: { entries: TimelineEntry[] }) {
  return (
    <ol className={styles.timeline}>
      {entries.map((entry, i) => (
        <li key={entry.key} className={`${styles.entry} ${styles[entry.state]}`} style={{ '--i': i } as CSSProperties}>
          <span className={styles.dot} aria-hidden="true" />
          <div className={styles.content}>
            <p className={styles.title}>{entry.title}</p>
            <p className={styles.meta}>
              <span>{entry.meta}</span>
              <span aria-hidden="true">·</span>
              <span>{entry.time}</span>
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
