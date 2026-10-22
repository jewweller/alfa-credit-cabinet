import { useId, type InputHTMLAttributes, type ReactNode } from 'react';
import styles from './TextField.module.css';

export interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label: string;
  /** Подсказка под полем; ошибка её заменяет. */
  hint?: ReactNode;
  error?: string | null;
  /** Единица справа внутри поля: «₽», «мес». */
  suffix?: string;
  /** Крупный шрифт — для главных цифр (сумма). */
  large?: boolean;
}

/** Поле ввода с подписью, подсказкой и ошибкой у поля. */
export function TextField({ label, hint, error, suffix, large = false, id, className, ...input }: TextFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const noteId = `${inputId}-note`;
  const note = error || hint;
  return (
    <div className={`${styles.field} ${error ? styles.invalid : ''} ${className ?? ''}`}>
      <label className={styles.label} htmlFor={inputId}>
        {label}
      </label>
      <div className={`${styles.control} ${large ? styles.large : ''}`}>
        <input
          id={inputId}
          className={styles.input}
          aria-invalid={error ? true : undefined}
          aria-describedby={note ? noteId : undefined}
          {...input}
        />
        {suffix && (
          <span className={styles.suffix} aria-hidden="true">
            {suffix}
          </span>
        )}
      </div>
      {note && (
        <p id={noteId} className={error ? styles.error : styles.hint} role={error ? 'alert' : undefined}>
          {note}
        </p>
      )}
    </div>
  );
}
