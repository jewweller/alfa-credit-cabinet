import styles from './CodeBlock.module.css';

/** Моноширинный текст как есть (например, сырой JSON) с прокруткой внутри. */
export function CodeBlock({ children }: { children: string }) {
  return <pre className={styles.code}>{children}</pre>;
}
