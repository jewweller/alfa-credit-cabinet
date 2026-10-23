import type { ReactNode } from 'react';
import styles from './FormGrid.module.css';

/** Поля формы в две колонки; на узком экране — в одну. */
export function FormGrid({ children }: { children: ReactNode }) {
  return <div className={styles.grid}>{children}</div>;
}
