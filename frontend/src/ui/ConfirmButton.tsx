import { useState } from 'react';
import { Button, type ButtonVariant } from './Button';
import styles from './ConfirmButton.module.css';

export interface ConfirmButtonProps {
  label: string;
  question: string;
  confirmLabel: string;
  cancelLabel: string;
  busy?: boolean;
  variant?: ButtonVariant;
  onConfirm: () => void;
}

/** Необратимое действие в два шага: кнопка → «Точно?» → подтвердить. Без модалок. */
export function ConfirmButton({
  label,
  question,
  confirmLabel,
  cancelLabel,
  busy = false,
  variant = 'ghost',
  onConfirm,
}: ConfirmButtonProps) {
  const [asking, setAsking] = useState(false);

  if (!asking) {
    return (
      <Button variant={variant} onClick={() => setAsking(true)} disabled={busy}>
        {label}
      </Button>
    );
  }

  return (
    <div className={styles.confirm} role="group" aria-label={question}>
      <span className={styles.question}>{question}</span>
      <Button variant="secondary" onClick={onConfirm} disabled={busy}>
        {confirmLabel}
      </Button>
      <Button variant="ghost" onClick={() => setAsking(false)} disabled={busy}>
        {cancelLabel}
      </Button>
    </div>
  );
}
