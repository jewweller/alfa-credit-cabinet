import styles from './PlainList.module.css';

/** Короткий список строк с тире — например, какие документы запрошены. */
export function PlainList({ items }: { items: string[] }) {
  return (
    <ul className={styles.list}>
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}
