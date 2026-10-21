import styles from './MetaNote.module.css';

/** Мелкая моноширинная подпись-«телеметрия»: кто и когда принял решение, источник данных. */
export function MetaNote({ children }: { children: string }) {
  return <p className={styles.note}>{children}</p>;
}
