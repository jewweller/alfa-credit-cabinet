import type { CSSProperties, ReactNode } from 'react';
import styles from './Card.module.css';

export interface CardProps {
  children: ReactNode;
  /** Порядковый номер для каскадного появления. */
  index?: number;
  interactive?: boolean;
}

export function Card({ children, index = 0, interactive = false }: CardProps) {
  return (
    <div
      className={`${styles.card} ${interactive ? styles.interactive : ''}`}
      style={{ '--i': index } as CSSProperties}
    >
      {children}
    </div>
  );
}
