import { useState } from 'react';
import type { Grade } from '../../api/types';
import { useAssignFromQueue, useBankQueue } from '../../features/bank/queries';
import { QueueTable } from '../../features/bank/QueueTable';
import { useProductMap, useProducts } from '../../features/products/useProducts';
import { ClientHeader } from '../../features/session/ClientHeader';
import { useMe } from '../../features/session/useMe';
import { useNow } from '../../features/useNow';
import { BANK, HOME, type QueueGroup } from '../../i18n/ru';
import { AppShell, EmptyState, ErrorBanner, FilterChips, Hero, InlineAlert, MetaNote, Panel, SkeletonCard } from '../../ui';
import styles from './QueuePage.module.css';

const GROUPS: QueueGroup[] = ['all', 'review', 'pipeline', 'client', 'closed'];
const GRADES: Grade[] = ['A', 'B', 'C', 'D', 'E'];
const ANY = 'any';

/** B2 — очередь заявок банка. */
export function QueuePage() {
  const Q = BANK.queue;
  const me = useMe().data;
  const now = useNow(30_000);
  const products = useProductMap();
  const productList = useProducts().data ?? [];
  const [group, setGroup] = useState<QueueGroup>('all');
  const [grade, setGrade] = useState<string>(ANY);
  const [productId, setProductId] = useState<string>(ANY);

  const all = useBankQueue({ statuses: [], grade: null, productId: null });
  const queue = useBankQueue({
    statuses: Q.groupStatuses[group],
    grade: grade === ANY ? null : (grade as Grade),
    productId: productId === ANY ? null : productId,
  });
  const take = useAssignFromQueue();

  const stats = all.data
    ? [
        { label: Q.stats.review, value: String(all.data.filter((r) => r.status === 'MANUAL_REVIEW').length), accent: true },
        { label: Q.stats.mine, value: String(all.data.filter((r) => r.status === 'MANUAL_REVIEW' && r.assignee?.id === me?.id).length) },
        { label: Q.stats.total, value: String(all.data.length) },
      ]
    : null;

  const filters = (
    <div className={styles.filters}>
      <FilterChips label={Q.filters.group} value={group} onChange={setGroup} options={GROUPS.map((g) => ({ value: g, label: Q.group[g] }))} />
      <FilterChips
        label={Q.filters.grade}
        value={grade}
        onChange={setGrade}
        options={[{ value: ANY, label: Q.any }, ...GRADES.map((g) => ({ value: g, label: g }))]}
      />
      <FilterChips
        label={Q.filters.product}
        value={productId}
        onChange={setProductId}
        options={[{ value: ANY, label: Q.any }, ...productList.map((p) => ({ value: p.id, label: p.name }))]}
      />
    </div>
  );

  return (
    <AppShell
      header={<ClientHeader />}
      hero={<Hero eyebrow={BANK.eyebrow} title={Q.title} subtitle={Q.subtitle} stats={stats} action={filters} />}
    >
      {queue.isError && !queue.data ? (
        <ErrorBanner
          message={Q.loadError}
          detail={queue.error.message}
          retryLabel={HOME.retry}
          onRetry={() => queue.refetch()}
          retrying={queue.isFetching}
        />
      ) : !queue.data ? (
        <SkeletonCard label={HOME.loading} />
      ) : queue.data.length === 0 ? (
        <EmptyState title={Q.empty.title} text={Q.empty.text} />
      ) : (
        <Panel>
          {take.isError && <InlineAlert>{take.error.message}</InlineAlert>}
          <QueueTable
            rows={queue.data}
            products={products}
            meId={me?.id}
            now={now}
            takingId={take.isPending ? (take.variables ?? null) : null}
            onTake={(id) => take.mutate(id)}
          />
          <MetaNote>{Q.live}</MetaNote>
        </Panel>
      )}
    </AppShell>
  );
}
