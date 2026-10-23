import { Card } from './Card';
import styles from './Skeleton.module.css';

export function Skeleton({
  width = '100%',
  height = '14px',
  tone = 'light',
}: {
  width?: string;
  height?: string;
  /** night — для тёмной зоны. */
  tone?: 'light' | 'night';
}) {
  return (
    <span
      className={`${styles.skeleton} ${tone === 'night' ? styles.night : ''}`}
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

/** Заглушка карточки заявки на время загрузки. */
export function SkeletonCard({ label, index = 0 }: { label: string; index?: number }) {
  return (
    <Card index={index}>
      <div className={styles.card} role="status" aria-label={label}>
        <div className={styles.row}>
          <div className={styles.col}>
            <Skeleton width="90px" height="10px" />
            <Skeleton width="200px" height="18px" />
          </div>
          <Skeleton width="110px" height="26px" />
        </div>
        <Skeleton width="180px" height="28px" />
        <Skeleton height="30px" />
        <div className={styles.row}>
          <Skeleton width="55%" />
          <Skeleton width="130px" height="40px" />
        </div>
      </div>
    </Card>
  );
}

/** Заглушка элемента ленты. */
export function SkeletonLine() {
  return (
    <div className={styles.line}>
      <Skeleton width="40%" height="10px" />
      <Skeleton width="85%" />
      <Skeleton width="60%" height="12px" />
    </div>
  );
}
