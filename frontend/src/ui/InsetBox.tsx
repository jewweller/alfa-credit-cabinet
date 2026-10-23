import type { ReactNode } from 'react';
import styles from './InsetBox.module.css';

/** Вложенный блок на приглушённой подложке с подписью: например, превью «что получит клиент». */
export function InsetBox({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={styles.box}>
      <span className={styles.label}>{label}</span>
      {children}
    </div>
  );
}
