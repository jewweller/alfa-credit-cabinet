import styles from './InlineAlert.module.css';

/** Короткое сообщение внутри панели: ошибка действия или подсказка. */
export function InlineAlert({ tone = 'danger', children }: { tone?: 'danger' | 'info'; children: string }) {
  return (
    <p className={`${styles.alert} ${styles[tone]}`} role={tone === 'danger' ? 'alert' : 'status'}>
      {children}
    </p>
  );
}
