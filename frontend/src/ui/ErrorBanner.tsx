import { Button } from './Button';
import styles from './ErrorBanner.module.css';

export function ErrorBanner({
  message,
  detail,
  retryLabel,
  onRetry,
  retrying = false,
}: {
  message: string;
  detail?: string;
  retryLabel: string;
  onRetry: () => void;
  retrying?: boolean;
}) {
  return (
    <div className={styles.banner} role="alert">
      <span className={styles.icon} aria-hidden="true">
        !
      </span>
      <div className={styles.text}>
        <p className={styles.message}>{message}</p>
        {detail && <p className={styles.detail}>{detail}</p>}
      </div>
      <Button variant="secondary" onClick={onRetry} disabled={retrying}>
        {retryLabel}
      </Button>
    </div>
  );
}
