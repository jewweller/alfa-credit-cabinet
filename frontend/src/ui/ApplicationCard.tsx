import { ButtonLink, type ButtonVariant } from './Button';
import { Card } from './Card';
import { StageProgress, type StageProgressProps } from './StageProgress';
import { StatusBadge, type BadgeTone } from './StatusBadge';
import styles from './ApplicationCard.module.css';

export interface ApplicationCardProps {
  /** Номер заявки, моноширинной подписью над заголовком. */
  eyebrow: string;
  title: string;
  amount: string;
  term: string;
  badge: { label: string; tone: BadgeTone };
  progress: StageProgressProps | null;
  nextLabel: string;
  next: string;
  hint: string | null;
  updated: string;
  action: { label: string; to: string; variant: ButtonVariant };
  index?: number;
}

export function ApplicationCard(props: ApplicationCardProps) {
  return (
    <Card index={props.index} interactive>
      <article className={styles.card}>
        <header className={styles.head}>
          <div className={styles.titles}>
            <p className={styles.eyebrow}>{props.eyebrow}</p>
            <h3 className={styles.title}>{props.title}</h3>
          </div>
          <StatusBadge key={props.badge.label} label={props.badge.label} tone={props.badge.tone} />
        </header>

        <p className={styles.money}>
          <span className={styles.amount}>{props.amount}</span>
          <span className={styles.term}>{props.term}</span>
        </p>

        {props.progress && <StageProgress {...props.progress} />}

        <footer className={styles.foot}>
          <div className={styles.next}>
            <p className={styles.nextLabel}>{props.nextLabel}</p>
            <p className={styles.nextText}>{props.next}</p>
            {props.hint && <p className={styles.hint}>{props.hint}</p>}
          </div>
          <ButtonLink to={props.action.to} variant={props.action.variant} arrow>
            {props.action.label}
          </ButtonLink>
        </footer>

        <p className={styles.updated}>{props.updated}</p>
      </article>
    </Card>
  );
}
