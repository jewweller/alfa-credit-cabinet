import styles from './ClauseList.module.css';

/** Нумерованные пункты документа: заголовок пункта жирным, дальше текст (например, договор на C6). */
export function ClauseList({ items }: { items: { title: string; text: string }[] }) {
  return (
    <ol className={styles.list}>
      {items.map((item) => (
        <li key={item.title}>
          <strong>{item.title}.</strong> {item.text}
        </li>
      ))}
    </ol>
  );
}
