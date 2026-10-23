import type { CSSProperties } from 'react';
import { Link, useNavigate } from 'react-router';
import type { BankApplicationSummary, Product } from '../../api/types';
import { BANK, BANK_STATUS, MONEY } from '../../i18n/ru';
import { Button, StatusBadge } from '../../ui';
import { formatMoney } from '../format';
import { ROUTES } from '../routes';
import { GRADE_TONE, waitingFor } from './format';
import styles from './QueueTable.module.css';

/** Таблица очереди (B2). Строка ведёт в карточку; «Взять в работу» — прямо отсюда. */
export function QueueTable({
  rows,
  products,
  meId,
  now,
  takingId,
  onTake,
}: {
  rows: BankApplicationSummary[];
  products: Map<string, Product>;
  meId: string | undefined;
  now: number;
  takingId: string | null;
  onTake: (id: string) => void;
}) {
  const navigate = useNavigate();
  const C = BANK.queue.columns;
  return (
    <div className={styles.wrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col" className={styles.narrowHide}>
              {C.number}
            </th>
            <th scope="col">{C.company}</th>
            <th scope="col" className={styles.wide}>
              {C.product}
            </th>
            <th scope="col" className={styles.num}>
              {C.amount}
            </th>
            <th scope="col" className={styles.mid}>
              {C.grade}
            </th>
            <th scope="col" className={styles.narrowHide}>
              {C.status}
            </th>
            <th scope="col" className={`${styles.num} ${styles.mid}`}>
              {C.waiting}
            </th>
            <th scope="col" className={styles.wide}>
              {C.assignee}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const status = BANK_STATUS[row.status];
            const canTake = row.status === 'MANUAL_REVIEW' && !row.assignee;
            const url = ROUTES.bankApplication(row.id);
            return (
              <tr
                key={row.id}
                className={`${styles.row} ${row.status === 'MANUAL_REVIEW' ? styles.waiting : ''}`}
                style={{ '--i': Math.min(i, 12) } as CSSProperties}
                onClick={() => navigate(url)}
              >
                <td className={`${styles.mono} ${styles.narrowHide}`}>{row.number}</td>
                <td>
                  <Link to={url} className={styles.company} onClick={(e) => e.stopPropagation()}>
                    {row.company.name}
                  </Link>
                  <span className={styles.inn}>ИНН {row.company.inn}</span>
                  {/* На узкой таблице статус — под названием, вместо своей колонки. */}
                  <span className={styles.inlineStatus}>
                    <StatusBadge label={status.label} tone={status.tone} />
                  </span>
                </td>
                <td className={`${styles.muted} ${styles.wide}`}>
                  {(row.product_id && products.get(row.product_id)?.name) || MONEY.noProduct}
                </td>
                <td className={`${styles.num} ${styles.strong}`}>{formatMoney(row.amount)}</td>
                <td className={styles.mid}>
                  {row.grade ? <StatusBadge label={`${row.grade} · ${row.score}`} tone={GRADE_TONE[row.grade]} /> : '—'}
                </td>
                <td className={styles.narrowHide}>
                  <StatusBadge label={status.label} tone={status.tone} />
                </td>
                <td className={`${styles.num} ${styles.mono} ${styles.mid}`}>{waitingFor(row.status_changed_at, now)}</td>
                <td className={styles.wide} onClick={(e) => e.stopPropagation()}>
                  {canTake ? (
                    <Button size="md" variant="secondary" disabled={takingId !== null} onClick={() => onTake(row.id)}>
                      {takingId === row.id ? BANK.queue.taking : BANK.queue.take}
                    </Button>
                  ) : row.assignee ? (
                    <span className={styles.muted}>{row.assignee.id === meId ? BANK.queue.you : row.assignee.full_name}</span>
                  ) : (
                    <span className={styles.faint}>{BANK.queue.nobody}</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
