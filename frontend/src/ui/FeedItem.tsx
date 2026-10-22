import type { CSSProperties } from 'react';
import { Link } from 'react-router';
import styles from './FeedItem.module.css';

export interface FeedItemProps {
  kind: 'event' | 'news';
  /** Подпись типа: «Заявка» / «Новость». */
  kindLabel: string;
  title: string;
  body?: string;
  time: string;
  unread: boolean;
  unreadLabel: string;
  reason?: { label: string; text: string } | null;
  to?: string | null;
  index?: number;
}

export function FeedItem(props: FeedItemProps) {
  const title = props.to ? (
    <Link to={props.to} className={styles.link}>
      {props.title}
    </Link>
  ) : (
    props.title
  );
  return (
    <article className={`${styles.item} ${styles[props.kind]}`} style={{ '--i': props.index ?? 0 } as CSSProperties}>
      <p className={styles.meta}>
        {props.unread && (
          <span className={styles.dot}>
            <span className={styles.srOnly}>{props.unreadLabel}</span>
          </span>
        )}
        <span className={styles.kind}>{props.kindLabel}</span>
        <span aria-hidden="true">·</span>
        <span>{props.time}</span>
      </p>
      <h3 className={styles.title}>{title}</h3>
      {props.body && <p className={styles.body}>{props.body}</p>}
      {props.reason && (
        <p className={styles.reason}>
          <span className={styles.reasonLabel}>{props.reason.label}</span>
          {props.reason.text}
        </p>
      )}
    </article>
  );
}
