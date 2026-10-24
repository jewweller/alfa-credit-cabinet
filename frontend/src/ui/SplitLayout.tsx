import type { ReactNode } from 'react';
import styles from './SplitLayout.module.css';

/**
 * Основная колонка + правая; на узком экране правая уходит вниз.
 * stickyAside — правая колонка залипает при прокрутке (подходит, если она ниже экрана).
 * asideFirst — на узком экране правая колонка идёт первой: короткое действие не теряется под длинным списком.
 */
export function SplitLayout({
  main,
  aside,
  stickyAside = true,
  asideFirst = false,
}: {
  main: ReactNode;
  aside: ReactNode;
  stickyAside?: boolean;
  asideFirst?: boolean;
}) {
  return (
    <div className={`${styles.split} ${asideFirst ? styles.asideFirst : ''}`}>
      <div className={styles.main}>{main}</div>
      <aside className={`${styles.aside} ${stickyAside ? styles.sticky : ''}`}>{aside}</aside>
    </div>
  );
}
