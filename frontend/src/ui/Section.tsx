import type { ReactNode } from 'react';
import styles from './Section.module.css';

export interface SectionProps {
  title: string;
  count?: number;
  /** Выделенный блок: «Нужно ваше действие». */
  highlighted?: boolean;
  /** Подпись живого индикатора справа, например «обновляется сам». */
  live?: string;
  children: ReactNode;
}

const pad = (n: number) => String(n).padStart(2, '0');

export function Section({ title, count, highlighted = false, live, children }: SectionProps) {
  return (
    <section className={`${styles.section} ${highlighted ? styles.highlighted : ''}`}>
      <header className={styles.head}>
        <h2 className={styles.title}>
          {highlighted && <span className={styles.beacon} aria-hidden="true" />}
          {title}
          {count !== undefined && <span className={styles.count}>{pad(count)}</span>}
        </h2>
        {live && (
          <span className={styles.live}>
            <span className={styles.liveDot} aria-hidden="true" />
            {live}
          </span>
        )}
      </header>
      <div className={styles.list}>{children}</div>
    </section>
  );
}
