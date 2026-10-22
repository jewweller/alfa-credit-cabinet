import type { ReactNode } from 'react';
import { Button } from './Button';
import styles from './ReviewGroup.module.css';

/** Блок на шаге проверки: заголовок, «Изменить» и данные шага. */
export function ReviewGroup({
  title,
  editLabel,
  onEdit,
  children,
}: {
  title: string;
  editLabel?: string;
  onEdit?: () => void;
  children: ReactNode;
}) {
  return (
    <section className={styles.group}>
      <header className={styles.head}>
        <h3 className={styles.title}>{title}</h3>
        {onEdit && editLabel && (
          <Button variant="ghost" onClick={onEdit}>
            {editLabel}
          </Button>
        )}
      </header>
      {children}
    </section>
  );
}
