import type { ReactNode } from 'react';
import styles from './KeyValueList.module.css';

export interface KeyValue {
  label: string;
  value: ReactNode;
  /** Крупная цифра — главный показатель. */
  emphasis?: boolean;
}

export function KeyValueList({ items, columns = 1 }: { items: KeyValue[]; columns?: 1 | 2 | 3 }) {
  return (
    <dl className={`${styles.list} ${styles[`cols${columns}`]}`}>
      {items.map((item) => (
        <div key={item.label} className={`${styles.row} ${item.emphasis ? styles.emphasis : ''}`}>
          <dt className={styles.label}>{item.label}</dt>
          <dd className={styles.value}>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
