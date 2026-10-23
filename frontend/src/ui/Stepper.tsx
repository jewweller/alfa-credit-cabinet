import type { CSSProperties } from 'react';
import styles from './Stepper.module.css';

export interface StepperProps {
  labels: string[];
  current: number;
  /** До какого шага клиент уже дошёл: на них можно вернуться. */
  reached: number;
  onSelect: (index: number) => void;
}

const pad = (n: number) => String(n).padStart(2, '0');

/** Шаги мастера на тёмном фоне: пройденные — кликабельны. */
export function Stepper({ labels, current, reached, onSelect }: StepperProps) {
  return (
    <ol className={styles.stepper} style={{ '--count': labels.length } as CSSProperties}>
      {labels.map((label, i) => {
        const state = i === current ? styles.current : i <= reached ? styles.done : styles.todo;
        return (
          <li key={label} className={styles.item} style={{ '--i': i } as CSSProperties}>
            <button
              type="button"
              className={`${styles.step} ${state}`}
              disabled={i > reached}
              aria-current={i === current ? 'step' : undefined}
              onClick={() => onSelect(i)}
            >
              <span className={styles.number}>{pad(i + 1)}</span>
              <span className={styles.label}>{label}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
