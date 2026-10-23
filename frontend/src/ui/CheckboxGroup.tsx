import type { ReactNode } from 'react';
import { InlineAlert } from './InlineAlert';
import styles from './CheckboxGroup.module.css';

/** Группа чекбоксов с общей подписью (fieldset + legend) и ошибкой под ней. */
export function CheckboxGroup({ legend, error, children }: { legend: string; error?: string | null; children: ReactNode }) {
  return (
    <fieldset className={styles.group}>
      <legend className={styles.legend}>{legend}</legend>
      {children}
      {error && <InlineAlert>{error}</InlineAlert>}
    </fieldset>
  );
}
