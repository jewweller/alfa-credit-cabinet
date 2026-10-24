import type { CSSProperties, ReactNode } from 'react';
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
  /** «Почему вы это видите»: самое сильное совпадение первым. */
  reasons?: { label: string; items: string[] } | null;
  to?: string | null;
  /** Переход по ссылке — например, чтобы отметить событие прочитанным. */
  onOpen?: () => void;
  /** Кнопка под записью. */
  action?: ReactNode;
  index?: number;
}

export function FeedItem(props: FeedItemProps) {
  const title = props.to ? (
    <Link to={props.to} className={styles.link} onClick={props.onOpen}>
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
      {props.reasons && props.reasons.items.length > 0 && (
        <div className={styles.reason}>
          <span className={styles.reasonLabel}>{props.reasons.label}</span>
          {props.reasons.items.map((text) => (
            <span key={text}>{text}</span>
          ))}
        </div>
      )}
      {props.action && <div className={styles.action}>{props.action}</div>}
    </article>
  );
}
