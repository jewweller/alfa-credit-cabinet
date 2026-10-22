import { useId, type CSSProperties, type KeyboardEvent, type ReactNode } from 'react';
import styles from './ChoiceCards.module.css';

export interface Choice<T extends string> {
  value: T;
  title: string;
  description?: string;
  /** Справа сверху: ставка, лимиты — моноширинной «телеметрией». */
  meta?: ReactNode;
}

export interface ChoiceCardsProps<T extends string> {
  label: string;
  options: Choice<T>[];
  value: T | null;
  onChange: (value: T) => void;
  columns?: 1 | 2 | 3;
  error?: string | null;
}

/** Выбор одного варианта карточками (radiogroup): цель кредита, продукт. */
export function ChoiceCards<T extends string>({
  label,
  options,
  value,
  onChange,
  columns = 3,
  error,
}: ChoiceCardsProps<T>) {
  const labelId = useId();
  const selectedIndex = options.findIndex((o) => o.value === value);

  // Стрелки двигают выбор, как у обычной группы радиокнопок.
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const step = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = (index + step + options.length) % options.length;
    onChange(options[next].value);
    const group = event.currentTarget.parentElement;
    (group?.children[next] as HTMLElement | undefined)?.focus();
  };

  return (
    <div className={styles.wrap}>
      <p id={labelId} className={styles.label}>
        {label}
      </p>
      <div
        role="radiogroup"
        aria-labelledby={labelId}
        aria-invalid={error ? true : undefined}
        className={`${styles.grid} ${styles[`cols${columns}`]} ${error ? styles.invalid : ''}`}
      >
        {options.map((option, i) => {
          const selected = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={selected}
              tabIndex={selected || (selectedIndex === -1 && i === 0) ? 0 : -1}
              className={`${styles.card} ${selected ? styles.selected : ''}`}
              style={{ '--i': i } as CSSProperties}
              onClick={() => onChange(option.value)}
              onKeyDown={(e) => onKeyDown(e, i)}
            >
              <span className={styles.head}>
                <span className={styles.radio} aria-hidden="true" />
                {option.meta && <span className={styles.meta}>{option.meta}</span>}
              </span>
              <span className={styles.title}>{option.title}</span>
              {option.description && <span className={styles.description}>{option.description}</span>}
            </button>
          );
        })}
      </div>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
