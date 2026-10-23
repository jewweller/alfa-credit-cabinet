import { Link } from 'react-router';
import styles from './BackLink.module.css';

/** «← Все заявки» над заголовком страницы, на тёмном фоне. */
export function BackLink({ to, label }: { to: string; label: string }) {
  return (
    <Link to={to} className={styles.link}>
      <span className={styles.arrow} aria-hidden="true">
        ←
      </span>
      {label}
    </Link>
  );
}
