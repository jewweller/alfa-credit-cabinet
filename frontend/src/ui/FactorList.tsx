import type { CSSProperties } from 'react';
import styles from './FactorList.module.css';

export interface Factor {
  code: string;
  title: string;
  value: string;
  points: number;
  max: number;
}

/** Факторы с баллами: код, название, значение и полоска «набрано из максимума». */
export function FactorList({ items }: { items: Factor[] }) {
  return (
    <ul className={styles.list}>
      {items.map((item) => (
        <li key={item.code} className={styles.item}>
          <span className={styles.code}>{item.code}</span>
          <span className={styles.text}>
            <span className={styles.title}>{item.title}</span>
            <span className={styles.value}>{item.value}</span>
          </span>
          <span className={styles.points}>
            <span className={styles.score}>
              {item.points}
              <span className={styles.max}>/{item.max}</span>
            </span>
            <span className={styles.bar} aria-hidden="true">
              <span className={styles.fill} style={{ '--share': item.points / item.max } as CSSProperties} />
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}
