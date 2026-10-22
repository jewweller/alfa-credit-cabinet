import type { CSSProperties } from 'react';
import styles from './Meter.module.css';

export interface MeterProps {
  label: string;
  /** Подпись значения: «21,3%». */
  valueLabel: string;
  /** Доля 0…1; больше 1 рисуем как полную шкалу. */
  value: number;
  /** Порог, после которого значение считается высоким (отметка на шкале). */
  threshold: number;
  thresholdLabel: string;
  note: string;
}

/** Шкала с порогом: например, долговая нагрузка против безопасных 35%. */
export function Meter({ label, valueLabel, value, threshold, thresholdLabel, note }: MeterProps) {
  const high = value > threshold;
  return (
    <div className={`${styles.meter} ${high ? styles.high : styles.ok}`}>
      <div className={styles.head}>
        <span className={styles.label}>{label}</span>
        <span className={styles.value}>{valueLabel}</span>
      </div>
      <div
        className={styles.track}
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(value * 100)}
        aria-valuetext={valueLabel}
        style={{ '--value': Math.min(1, value), '--threshold': threshold } as CSSProperties}
      >
        <span className={styles.fill} />
        <span className={styles.mark}>
          <span className={styles.markLabel}>{thresholdLabel}</span>
        </span>
      </div>
      <p className={styles.note}>{note}</p>
    </div>
  );
}
