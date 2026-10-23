import { useNavigate } from 'react-router';
import type { BankApplicationSummary, Product } from '../../api/types';
import { BANK, BANK_STATUS, MONEY } from '../../i18n/ru';
import { Button, DataTable, DataTableTitle, StatusBadge, type DataColumn } from '../../ui';
import { formatMoney } from '../format';
import { ROUTES } from '../routes';
import { GRADE_TONE, waitingFor } from './format';

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
  const badge = (row: BankApplicationSummary) => {
    const status = BANK_STATUS[row.status];
    return <StatusBadge label={status.label} tone={status.tone} />;
  };

  const columns: DataColumn<BankApplicationSummary>[] = [
    { key: 'number', header: C.number, tone: 'mono', hideBelow: 'small', cell: (row) => row.number },
    {
      key: 'company',
      header: C.company,
      // На узкой таблице статус — под названием, вместо своей колонки.
      cell: (row) => (
        <DataTableTitle to={ROUTES.bankApplication(row.id)} title={row.company.name} meta={`ИНН ${row.company.inn}`} narrow={badge(row)} />
      ),
    },
    {
      key: 'product',
      header: C.product,
      tone: 'muted',
      hideBelow: 'medium',
      cell: (row) => (row.product_id && products.get(row.product_id)?.name) || MONEY.noProduct,
    },
    { key: 'amount', header: C.amount, align: 'end', tone: 'strong', cell: (row) => formatMoney(row.amount) },
    {
      key: 'grade',
      header: C.grade,
      hideBelow: 'small',
      cell: (row) => (row.grade ? <StatusBadge label={`${row.grade} · ${row.score}`} tone={GRADE_TONE[row.grade]} /> : '—'),
    },
    { key: 'status', header: C.status, hideBelow: 'small', cell: badge },
    {
      key: 'waiting',
      header: C.waiting,
      align: 'end',
      tone: 'mono',
      hideBelow: 'small',
      cell: (row) => waitingFor(row.status_changed_at, now),
    },
    {
      key: 'assignee',
      header: C.assignee,
      tone: 'muted',
      hideBelow: 'medium',
      interactive: true,
      cell: (row) =>
        row.status === 'MANUAL_REVIEW' && !row.assignee ? (
          <Button variant="secondary" disabled={takingId !== null} onClick={() => onTake(row.id)}>
            {takingId === row.id ? BANK.queue.taking : BANK.queue.take}
          </Button>
        ) : row.assignee ? (
          row.assignee.id === meId ? BANK.queue.you : row.assignee.full_name
        ) : (
          BANK.queue.nobody
        ),
    },
  ];

  return (
    <DataTable
      rows={rows}
      rowKey={(row) => row.id}
      columns={columns}
      onRowClick={(row) => navigate(ROUTES.bankApplication(row.id))}
      accent={(row) => row.status === 'MANUAL_REVIEW'}
    />
  );
}
