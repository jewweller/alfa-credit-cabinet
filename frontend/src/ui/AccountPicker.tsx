import type { CSSProperties } from 'react';
import styles from './AccountPicker.module.css';

export interface PickableAccount {
  email: string;
  name: string;
  note: string;
}

/** Список демо-учёток: нажатие подставляет учётку в форму входа. */
export function AccountPicker({
  accounts,
  selected,
  onPick,
}: {
  accounts: PickableAccount[];
  selected: string;
  onPick: (email: string) => void;
}) {
  return (
    <ul className={styles.list}>
      {accounts.map((account, i) => (
        <li key={account.email} style={{ '--i': i } as CSSProperties} className={styles.item}>
          <button
            type="button"
            className={`${styles.account} ${account.email === selected ? styles.selected : ''}`}
            aria-pressed={account.email === selected}
            onClick={() => onPick(account.email)}
          >
            <span className={styles.name}>{account.name}</span>
            <span className={styles.note}>{account.note}</span>
            <span className={styles.email}>{account.email}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
