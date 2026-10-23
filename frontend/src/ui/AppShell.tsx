import type { ReactNode } from 'react';
import styles from './AppShell.module.css';

/**
 * Каркас страницы: неподвижный тёмный красный фон со свечением,
 * шапка, необязательный блок приветствия и основной контент.
 */
export function AppShell({ header, hero, children }: { header: ReactNode; hero?: ReactNode; children: ReactNode }) {
  return (
    <div className={styles.shell}>
      <div className={styles.backdrop} aria-hidden="true">
        <div className={styles.glow} />
        <div className={styles.dots} />
      </div>
      {header}
      {hero}
      <main className={`${styles.main} ${hero ? styles.withHero : ''}`}>{children}</main>
    </div>
  );
}
