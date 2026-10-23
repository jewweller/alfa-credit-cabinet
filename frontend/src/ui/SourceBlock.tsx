import type { ReactNode } from 'react';
import styles from './SourceBlock.module.css';

/** Раздел внутри панели: заголовок с бейджем справа, затем содержимое; разделы идут через линию. */
export function SourceBlock({ title, badge, children }: { title: string; badge?: ReactNode; children: ReactNode }) {
  return (
    <section className={styles.block}>
      <div className={styles.head}>
        <h3 className={styles.title}>{title}</h3>
        {badge}
      </div>
      {children}
    </section>
  );
}
