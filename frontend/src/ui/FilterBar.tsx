import type { ReactNode } from 'react';
import styles from './FilterBar.module.css';

/** Несколько групп фильтров (FilterChips) столбиком — для тёмной зоны над таблицей. */
export function FilterBar({ children }: { children: ReactNode }) {
  return <div className={styles.bar}>{children}</div>;
}
