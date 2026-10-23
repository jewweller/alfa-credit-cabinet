import styles from './RuleList.module.css';

export interface RuleItem {
  code: string;
  title: string;
  detail: string | null;
  fired: boolean;
}

/** Правила по порядку: сработавшее подсвечено акцентом, у каждого — пояснение и состояние. */
export function RuleList({ items, firedLabel, passedLabel }: { items: RuleItem[]; firedLabel: string; passedLabel: string }) {
  return (
    <ol className={styles.list}>
      {items.map((item) => (
        <li key={item.code} className={`${styles.item} ${item.fired ? styles.fired : ''}`}>
          <span className={styles.code}>{item.code}</span>
          <span className={styles.text}>
            <span className={styles.title}>{item.title}</span>
            {item.detail && <span className={styles.detail}>{item.detail}</span>}
          </span>
          <span className={styles.state}>{item.fired ? firedLabel : passedLabel}</span>
        </li>
      ))}
    </ol>
  );
}
