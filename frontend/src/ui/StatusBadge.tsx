import styles from './StatusBadge.module.css';

export type BadgeTone = 'action' | 'progress' | 'success' | 'danger' | 'neutral';

export function StatusBadge({ label, tone }: { label: string; tone: BadgeTone }) {
  return <span className={`${styles.badge} ${styles[tone]}`}>{label}</span>;
}
