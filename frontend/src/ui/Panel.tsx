import type { CSSProperties, ReactNode } from 'react';
import styles from './Panel.module.css';

export interface PanelProps {
  eyebrow?: string;
  title?: string;
  /** Справа от заголовка: бейдж, живой индикатор. */
  aside?: ReactNode;
  /** highlight — главный блок экрана; danger — отказ; success — выдача. */
  tone?: 'default' | 'highlight' | 'danger' | 'success';
  footer?: ReactNode;
  index?: number;
  children?: ReactNode;
}

/** Рабочая поверхность с заголовком: из таких собираются экраны. */
export function Panel({ eyebrow, title, aside, tone = 'default', footer, index = 0, children }: PanelProps) {
  return (
    <section className={`${styles.panel} ${styles[tone]}`} style={{ '--i': index } as CSSProperties}>
      {(eyebrow || title || aside) && (
        <header className={styles.head}>
          <div className={styles.titles}>
            {eyebrow && <p className={styles.eyebrow}>{eyebrow}</p>}
            {title && <h2 className={styles.title}>{title}</h2>}
          </div>
          {aside && <div className={styles.aside}>{aside}</div>}
        </header>
      )}
      {children && <div className={styles.body}>{children}</div>}
      {footer && <footer className={styles.footer}>{footer}</footer>}
    </section>
  );
}
