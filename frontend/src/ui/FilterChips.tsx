import styles from './FilterChips.module.css';

export interface FilterChip<T extends string> {
  value: T;
  label: string;
}

/** Фильтр-«чипсы» для тёмной зоны: выбор одного варианта; не помещаются — переносятся. */
export function FilterChips<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: FilterChip<T>[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className={styles.group}>
      <span className={styles.label} id={`chips-${label}`}>
        {label}
      </span>
      <div className={styles.chips} role="radiogroup" aria-labelledby={`chips-${label}`}>
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={option.value === value}
            className={`${styles.chip} ${option.value === value ? styles.active : ''}`}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
