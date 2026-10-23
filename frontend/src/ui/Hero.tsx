import type { CSSProperties, ReactNode } from 'react';
import { Skeleton } from './Skeleton';
import styles from './Hero.module.css';

export interface HeroStat {
  value: string;
  label: string;
  accent?: boolean;
}

export interface HeroProps {
  /** Над всем остальным: например, ссылка «← Все заявки». */
  top?: ReactNode;
  eyebrow?: string;
  title: string;
  subtitle?: string | null;
  /** null — данные ещё грузятся. */
  stats?: HeroStat[] | null;
  action?: ReactNode;
}

/** Приветствие и сводка прямо на тёмном фоне страницы. */
export function Hero({ top, eyebrow, title, subtitle, stats, action }: HeroProps) {
  return (
    <section className={styles.hero}>
      <div className={styles.inner}>
        <div className={styles.text}>
          {top}
          {eyebrow && <p className={styles.eyebrow}>{eyebrow}</p>}
          <h1 className={styles.title}>{title}</h1>
          {subtitle !== undefined &&
            (subtitle === null ? (
              <Skeleton width="280px" height="18px" tone="night" />
            ) : (
              <p className={styles.subtitle}>{subtitle}</p>
            ))}
          {action && <div className={styles.action}>{action}</div>}
        </div>

        {stats !== undefined && (
          <dl className={styles.stats}>
            {(stats ?? [null, null, null]).map((stat, i) => (
              <div
                key={stat?.label ?? i}
                className={`${styles.stat} ${stat?.accent ? styles.statAccent : ''}`}
                style={{ '--i': i } as CSSProperties}
              >
                {stat ? (
                  <>
                    <dt className={styles.statLabel}>{stat.label}</dt>
                    <dd className={styles.statValue}>{stat.value}</dd>
                  </>
                ) : (
                  <>
                    <Skeleton width="70%" height="11px" tone="night" />
                    <Skeleton width="40%" height="28px" tone="night" />
                  </>
                )}
              </div>
            ))}
          </dl>
        )}
      </div>
    </section>
  );
}
