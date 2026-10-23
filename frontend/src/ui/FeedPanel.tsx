import type { ReactNode } from 'react';
import { Link } from 'react-router';
import styles from './FeedPanel.module.css';

export interface FeedPanelProps {
  title: string;
  /** Короткая подпись справа от заголовка, например «по вашему профилю». */
  caption?: string;
  children: ReactNode;
  footer?: { label: string; to: string };
}

export function FeedPanel({ title, caption, children, footer }: FeedPanelProps) {
  return (
    <section className={styles.panel} aria-label={title}>
      <header className={styles.head}>
        <h2 className={styles.title}>{title}</h2>
        {caption && <span className={styles.caption}>{caption}</span>}
      </header>
      <div className={styles.list}>{children}</div>
      {footer && (
        <Link to={footer.to} className={styles.footer}>
          {footer.label}
          <span className={styles.arrow} aria-hidden="true">
            →
          </span>
        </Link>
      )}
    </section>
  );
}
