import type { ReactNode } from 'react';
import styles from './KeyValueList.module.css';

export interface KeyValue {
  label: string;
  value: ReactNode;
  /** Крупная цифра — главный показатель. */
  emphasis?: boolean;
  /** Что не так со значением: показываем под ним красным (проверка заявки). */
  error?: string | null;
}

export function KeyValueList({
  items,
  columns = 1,
  valueFirst = false,
}: {
  items: KeyValue[];
  columns?: 1 | 2 | 3;
  /** В одну колонку: значение слева, подпись справа — взгляд сначала падает на данные клиента. */
  valueFirst?: boolean;
}) {
  return (
    <dl className={`${styles.list} ${styles[`cols${columns}`]} ${valueFirst ? styles.valueFirst : ''}`}>
      {items.map((item) => (
        <div
          key={item.label}
          className={`${styles.row} ${item.emphasis ? styles.emphasis : ''} ${item.error ? styles.invalid : ''}`}
        >
          <dt className={styles.label}>{item.label}</dt>
          <dd className={styles.value}>
            {item.value}
            {item.error && <span className={styles.error}>{item.error}</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}
