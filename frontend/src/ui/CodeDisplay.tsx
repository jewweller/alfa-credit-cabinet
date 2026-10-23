import styles from './CodeDisplay.module.css';

/** Крупный код в рамке: подпись сверху, срок действия снизу (симуляция ПЭП, экран C6). */
export function CodeDisplay({ label, code, note }: { label: string; code: string; note?: string }) {
  return (
    <div className={styles.box}>
      <span className={styles.label}>{label}</span>
      <span className={styles.code}>{code}</span>
      {note && <span className={styles.note}>{note}</span>}
    </div>
  );
}
