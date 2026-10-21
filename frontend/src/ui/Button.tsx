import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Link } from 'react-router';
import styles from './Button.module.css';

/** night и nightGhost — для тёмной зоны (шапка, приветствие). */
export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'night' | 'nightGhost';
export type ButtonSize = 'md' | 'lg';

interface CommonProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Добавляет стрелку → после текста. */
  arrow?: boolean;
  children: ReactNode;
}

function classes(variant: ButtonVariant, size: ButtonSize) {
  return [styles.button, styles[variant], styles[size]].join(' ');
}

function Content({ arrow, children }: Pick<CommonProps, 'arrow' | 'children'>) {
  return (
    <>
      {children}
      {arrow && (
        <span className={styles.arrow} aria-hidden="true">
          →
        </span>
      )}
    </>
  );
}

export function Button({
  variant = 'primary',
  size = 'md',
  arrow,
  children,
  type = 'button',
  ...rest
}: CommonProps & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type={type} className={classes(variant, size)} {...rest}>
      <Content arrow={arrow}>{children}</Content>
    </button>
  );
}

export function ButtonLink({
  variant = 'primary',
  size = 'md',
  arrow,
  children,
  to,
}: CommonProps & { to: string }) {
  return (
    <Link to={to} className={classes(variant, size)}>
      <Content arrow={arrow}>{children}</Content>
    </Link>
  );
}
