import type { ReactNode } from 'react';
import styles from './SplitLayout.module.css';

/**
 * Основная колонка + правая; на узком экране правая уходит вниз.
 * stickyAside — правая колонка залипает при прокрутке (подходит, если она ниже экрана).
 */
export function SplitLayout({
  main,
  aside,
  stickyAside = true,
}: {
  main: ReactNode;
  aside: ReactNode;
  stickyAside?: boolean;
}) {
  return (
    <div className={styles.split}>
      <div className={styles.main}>{main}</div>
      <aside className={`${styles.aside} ${stickyAside ? styles.sticky : ''}`}>{aside}</aside>
    </div>
  );
}
