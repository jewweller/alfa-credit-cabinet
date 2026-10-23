import styles from './Quote.module.css';

/** Чужие слова с линией слева — например, сообщение банка клиенту. */
export function Quote({ children }: { children: string }) {
  return <p className={styles.quote}>{children}</p>;
}
