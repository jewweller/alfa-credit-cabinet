import type { CSSProperties } from 'react';
import styles from './StageProgress.module.css';

export interface StageProgressProps {
  labels: string[];
  /** Индекс текущего этапа. */
  current: number;
  /** complete — всё зелёное, failed — текущий этап красный. */
  state: 'active' | 'complete' | 'failed';
}

type StepState = 'done' | 'current' | 'failed' | 'todo';

function stepState(index: number, { current, state }: StageProgressProps): StepState {
  if (state === 'complete' || index < current) return 'done';
  if (index > current) return 'todo';
  return state === 'failed' ? 'failed' : 'current';
}

const STEP_SR: Record<StepState, string> = {
  done: 'пройден',
  current: 'текущий этап',
  failed: 'остановлено',
  todo: 'впереди',
};

export function StageProgress(props: StageProgressProps) {
  return (
    <ol className={`${styles.progress} ${props.state === 'complete' ? styles.complete : ''}`}>
      {props.labels.map((label, i) => {
        const s = stepState(i, props);
        return (
          <li key={label} className={`${styles.step} ${styles[s]}`} style={{ '--i': i } as CSSProperties}>
            <span className={styles.dot} aria-hidden="true" />
            <span className={styles.label}>
              {label}
              <span className={styles.srOnly}> — {STEP_SR[s]}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
