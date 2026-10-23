import type { CSSProperties, ReactNode } from 'react';
import styles from './AuthLayout.module.css';

export interface AuthLayoutProps {
  eyebrow: string;
  title: string;
  subtitle: string;
  points: string[];
  /** Правая колонка: форма входа и подсказки. */
  children: ReactNode;
}

/** Экран входа: слева обещание продукта на тёмном фоне, справа рабочая поверхность с формой. */
export function AuthLayout({ eyebrow, title, subtitle, points, children }: AuthLayoutProps) {
  return (
    <div className={styles.layout}>
      <section className={styles.intro}>
        <p className={styles.eyebrow}>{eyebrow}</p>
        <h1 className={styles.title}>{title}</h1>
        <p className={styles.subtitle}>{subtitle}</p>
        <ul className={styles.points}>
          {points.map((point, i) => (
            <li key={point} className={styles.point} style={{ '--i': i } as CSSProperties}>
              <span className={styles.index}>{String(i + 1).padStart(2, '0')}</span>
              {point}
            </li>
          ))}
        </ul>
      </section>
      <div className={styles.side}>{children}</div>
    </div>
  );
}
