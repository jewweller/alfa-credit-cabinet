import type { FormEvent, ReactNode } from 'react';
import styles from './Form.module.css';

/**
 * Форма без собственной вёрстки браузера: проверка полей — наша (noValidate).
 * stack — поля столбиком; inline — поле и кнопка в строку (на узком переносятся);
 * contents — форма не влияет на раскладку родителя (поля встают в его сетку).
 */
export function Form({
  layout = 'stack',
  onSubmit,
  children,
}: {
  layout?: 'stack' | 'inline' | 'contents';
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  children: ReactNode;
}) {
  return (
    <form className={styles[layout]} onSubmit={onSubmit} noValidate>
      {children}
    </form>
  );
}
