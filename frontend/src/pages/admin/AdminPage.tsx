import { useState } from 'react';
import { AuditPanel } from '../../features/audit/AuditPanel';
import { useAudit, useDemoReset } from '../../features/audit/queries';
import { ROUTES } from '../../features/routes';
import { ClientHeader } from '../../features/session/ClientHeader';
import { ADMIN, type AuditGroup } from '../../i18n/ru';
import { AppShell, ButtonLink, ConfirmButton, FilterBar, FilterChips, Hero, InlineAlert, Panel, SplitLayout } from '../../ui';

const GROUPS: AuditGroup[] = ['all', 'auth', 'client', 'documents', 'bank', 'system'];

const timeFmt = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

/** Сброс демо-данных перед показом. */
function ResetPanel() {
  const R = ADMIN.reset;
  const reset = useDemoReset();
  return (
    <Panel tone="highlight" eyebrow={R.eyebrow} title={R.title}>
      <p>{R.text}</p>
      <div>
        <ConfirmButton
          variant="primary"
          label={reset.isPending ? R.busy : R.button}
          question={R.question}
          confirmLabel={R.confirm}
          cancelLabel={R.cancel}
          busy={reset.isPending}
          onConfirm={() => reset.mutate()}
        />
      </div>
      {reset.isSuccess && (
        <InlineAlert tone="info">{R.done(reset.data.applications_deleted, timeFmt.format(new Date(reset.data.reset_at)))}</InlineAlert>
      )}
      {reset.isError && <InlineAlert>{`${R.error}: ${reset.error.message}`}</InlineAlert>}
    </Panel>
  );
}

/** Экран администратора: сброс демо и журнал действий всех пользователей. */
export function AdminPage() {
  const A = ADMIN.audit;
  const [group, setGroup] = useState<AuditGroup>('all');
  const recent = useAudit();
  const today = new Date().toDateString();
  const todayRows = recent.data?.filter((r) => new Date(r.created_at).toDateString() === today);
  // Загружена только первая страница: если вся она за сегодня, записей может быть больше.
  const more = recent.hasNextPage && todayRows?.length === recent.data?.length ? '+' : '';
  const stats = todayRows
    ? [
        { label: ADMIN.stats.today, value: `${todayRows.length}${more}` },
        { label: ADMIN.stats.logins, value: String(todayRows.filter((r) => r.action === 'auth.login').length) },
        { label: ADMIN.stats.decisions, value: String(todayRows.filter((r) => r.action === 'bank.decision').length), accent: true },
      ]
    : null;

  return (
    <AppShell
      header={<ClientHeader />}
      hero={
        <Hero
          eyebrow={ADMIN.eyebrow}
          title={ADMIN.title}
          subtitle={ADMIN.subtitle}
          stats={stats}
          top={
            <div>
              <ButtonLink to={ROUTES.bank} variant="nightGhost" arrow>
                {ADMIN.toQueue}
              </ButtonLink>
            </div>
          }
          action={
            <FilterBar>
              <FilterChips label={A.filter} value={group} onChange={setGroup} options={GROUPS.map((g) => ({ value: g, label: A.group[g] }))} />
            </FilterBar>
          }
        />
      }
    >
      <SplitLayout
        stickyAside={false}
        asideFirst
        main={<AuditPanel title={A.title} filter={{ actions: A.groupActions[group] }} />}
        aside={<ResetPanel />}
      />
    </AppShell>
  );
}
