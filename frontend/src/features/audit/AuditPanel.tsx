import { ADMIN, HOME } from '../../i18n/ru';
import { Button, ErrorBanner, MetaNote, Panel, SkeletonCard } from '../../ui';
import { AuditTable } from './AuditTable';
import { useAudit, type AuditFilter } from './queries';

/** Журнал действий в панели: весь (экран администратора) или по одной заявке (вкладка в B3). */
export function AuditPanel({
  filter,
  title,
  index = 0,
}: {
  filter: AuditFilter;
  title: string;
  index?: number;
}) {
  const A = ADMIN.audit;
  const audit = useAudit(filter);
  const rows = audit.data ?? [];
  const byApplication = Boolean(filter.applicationId);

  return (
    <Panel eyebrow={A.eyebrow} title={title} index={index}>
      {audit.isPending ? (
        <SkeletonCard label={HOME.loading} />
      ) : audit.isError && rows.length === 0 ? (
        <ErrorBanner
          message={A.loadError}
          detail={audit.error.message}
          retryLabel={HOME.retry}
          onRetry={() => audit.refetch()}
          retrying={audit.isFetching}
        />
      ) : rows.length === 0 ? (
        <MetaNote>{A.empty}</MetaNote>
      ) : (
        <AuditTable rows={rows} showApplication={!byApplication} />
      )}
      {audit.hasNextPage && (
        <div>
          <Button variant="ghost" onClick={() => audit.fetchNextPage()} disabled={audit.isFetchingNextPage}>
            {audit.isFetchingNextPage ? A.loadingMore : A.more}
          </Button>
        </div>
      )}
      <MetaNote>{A.note}</MetaNote>
    </Panel>
  );
}
