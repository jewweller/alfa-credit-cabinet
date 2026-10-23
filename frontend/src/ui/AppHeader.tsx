import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { Button } from './Button';
import { Skeleton } from './Skeleton';
import styles from './AppHeader.module.css';

export interface AppHeaderProps {
  productName: string;
  homeHref: string;
  /** null — данные ещё грузятся. */
  company: { name: string; innLabel: string } | null;
  userName: string | null;
  logoutLabel: string;
  onLogout: () => void;
  /** Элементы слева от пользователя, например переключатель оформления. */
  tools?: ReactNode;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0] ?? '')
    .join('')
    .toUpperCase();
}

function Brand({ productName, homeHref }: { productName: string; homeHref: string }) {
  return (
    <Link to={homeHref} className={styles.brand}>
      <span className={styles.logo} aria-hidden="true">
        <svg viewBox="0 0 24 24" width="16" height="16">
          <path d="M12 3 21 20H3Z" fill="currentColor" />
        </svg>
      </span>
      <span className={styles.product}>{productName}</span>
    </Link>
  );
}

/** Шапка до входа: только название продукта и, например, переключатель оформления. */
export function PublicHeader({ productName, homeHref, tools }: Pick<AppHeaderProps, 'productName' | 'homeHref' | 'tools'>) {
  return (
    <header className={styles.header}>
      <div className={`${styles.inner} ${styles.public}`}>
        <Brand productName={productName} homeHref={homeHref} />
        {tools && <div className={styles.tools}>{tools}</div>}
      </div>
    </header>
  );
}

export function AppHeader(props: AppHeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Brand productName={props.productName} homeHref={props.homeHref} />

        <div className={styles.company}>
          {props.company ? (
            <>
              <span className={styles.companyName}>{props.company.name}</span>
              <span className={styles.inn}>{props.company.innLabel}</span>
            </>
          ) : (
            <Skeleton width="220px" height="14px" tone="night" />
          )}
        </div>

        <div className={styles.user}>
          {props.tools && <div className={styles.tools}>{props.tools}</div>}
          {props.userName ? (
            <span className={styles.userChip}>
              <span className={styles.avatar} aria-hidden="true">
                {initials(props.userName)}
              </span>
              <span className={styles.userName}>{props.userName}</span>
            </span>
          ) : (
            <Skeleton width="120px" height="14px" tone="night" />
          )}
          <Button variant="nightGhost" onClick={props.onLogout}>
            {props.logoutLabel}
          </Button>
        </div>
      </div>
    </header>
  );
}
