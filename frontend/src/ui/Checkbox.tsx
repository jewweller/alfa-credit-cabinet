import { useId, type ReactNode } from 'react';
import styles from './Checkbox.module.css';

export function Checkbox({
  checked,
  onChange,
  label,
  hint,
  error,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: ReactNode;
  hint?: string;
  error?: string | null;
}) {
  const id = useId();
  return (
    <div className={`${styles.wrap} ${error ? styles.invalid : ''}`}>
      <label className={styles.row} htmlFor={id}>
        <input
          id={id}
          type="checkbox"
          className={styles.input}
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          aria-invalid={error ? true : undefined}
        />
        <span className={styles.box} aria-hidden="true">
          <svg viewBox="0 0 16 16" width="12" height="12">
            <path d="m3.5 8.5 3 3 6-7" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <span className={styles.text}>
          <span className={styles.label}>{label}</span>
          {hint && <span className={styles.hint}>{hint}</span>}
        </span>
      </label>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
