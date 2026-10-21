import type { CSSProperties } from 'react';
import styles from './SegmentedControl.module.css';

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  /** Цвет кружка-образца рядом с подписью (CSS-значение). */
  swatch?: string;
}

export interface SegmentedControlProps<T extends string> {
  label: string;
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
}

/** Переключатель из нескольких вариантов с ползунком. Для тёмной зоны. */
export function SegmentedControl<T extends string>({ label, options, value, onChange }: SegmentedControlProps<T>) {
  const index = Math.max(0, options.findIndex((o) => o.value === value));
  return (
    <div
      className={styles.control}
      role="radiogroup"
      aria-label={label}
      style={{ '--count': options.length, '--index': index } as CSSProperties}
    >
      <span className={styles.thumb} aria-hidden="true" />
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={option.value === value}
          title={option.label}
          className={`${styles.option} ${option.value === value ? styles.active : ''}`}
          onClick={() => onChange(option.value)}
        >
          {option.swatch && (
            <span className={styles.swatch} style={{ background: option.swatch }} aria-hidden="true" />
          )}
          <span className={styles.label}>{option.label}</span>
        </button>
      ))}
    </div>
  );
}
