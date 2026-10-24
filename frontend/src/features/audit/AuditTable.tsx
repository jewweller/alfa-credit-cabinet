import { useNavigate } from 'react-router';
import type { ApplicationStatus, AuditEntry } from '../../api/types';
import { ADMIN, BANK_STATUS } from '../../i18n/ru';
import { DataTable, DataTableTitle, type DataColumn } from '../../ui';
import { ROUTES } from '../routes';

const timeFmt = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
});

/** Коды статусов в строке сервера («SCORING → APPROVED») — словами, как в очереди. */
function humanSummary(summary: string): string {
  return summary.replace(/\b[A-Z][A-Z_]+\b/g, (code) => BANK_STATUS[code as ApplicationStatus]?.label ?? code);
}

/** Журнал действий: строка с заявкой ведёт в её карточку. Без колонки заявки — для вкладки в B3. */
export function AuditTable({ rows, showApplication = true }: { rows: AuditEntry[]; showApplication?: boolean }) {
  const navigate = useNavigate();
  const A = ADMIN.audit;
  const actor = (row: AuditEntry) => row.actor_name ?? A.unknown;

  const who = (row: AuditEntry) => (row.actor_role === 'system' ? A.system : `${actor(row)} · ${A.role[row.actor_role]}`);
  const link = (row: AuditEntry) => (showApplication && row.application_id ? ROUTES.bankApplication(row.application_id) : undefined);

  // Кто и номер заявки — подписью под действием: отдельные колонки не помещаются в основную колонку страницы.
  // На узкой таблице время и что изменилось тоже уходят в эту ячейку.
  const columns: DataColumn<AuditEntry>[] = [
    { key: 'time', header: A.columns.time, tone: 'mono', hideBelow: 'small', cell: (row) => timeFmt.format(new Date(row.created_at)) },
    {
      key: 'action',
      header: A.columns.action,
      cell: (row) => (
        <DataTableTitle
          to={link(row)}
          title={A.action[row.action]}
          meta={showApplication && row.application_number ? `№${row.application_number} · ${who(row)}` : who(row)}
          narrow={`${timeFmt.format(new Date(row.created_at))} · ${humanSummary(row.summary)}`}
        />
      ),
    },
    { key: 'summary', header: A.columns.summary, tone: 'muted', hideBelow: 'small', cell: (row) => humanSummary(row.summary) },
  ];

  return (
    <DataTable
      rows={rows}
      rowKey={(row) => row.id}
      columns={columns}
      accent={(row) => row.action === 'auth.login_failed' || row.action === 'demo.reset'}
      onRowClick={
        showApplication
          ? (row) => {
              if (row.application_id) navigate(ROUTES.bankApplication(row.application_id));
            }
          : undefined
      }
    />
  );
}
