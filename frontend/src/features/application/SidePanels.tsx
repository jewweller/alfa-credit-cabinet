import type { ApplicationDetail, Product, StatusHistoryEntry } from '../../api/types';
import { APPLICATION, MONEY } from '../../i18n/ru';
import { KeyValueList, Panel, Skeleton, Timeline, type TimelineEntry } from '../../ui';
import { formatDateTime, formatMoney, formatTerm, timeAgo } from '../format';

export function DetailsPanel({ app, products }: { app: ApplicationDetail; products: Map<string, Product> }) {
  const D = APPLICATION.details;
  const product = (app.product_id && products.get(app.product_id)?.name) || MONEY.noProduct;
  const items = [
    { label: D.product, value: product },
    { label: D.amount, value: formatMoney(app.amount) },
    { label: D.term, value: formatTerm(app.term_months) },
    ...(app.purpose ? [{ label: D.purpose, value: APPLICATION.purpose[app.purpose] }] : []),
    ...(app.revenue_12m ? [{ label: D.revenue, value: formatMoney(app.revenue_12m) }] : []),
    ...(app.submitted_at ? [{ label: D.submitted, value: formatDateTime(app.submitted_at) }] : []),
  ];
  return (
    <Panel title={D.title} index={1}>
      <KeyValueList items={items} />
    </Panel>
  );
}

const FINAL_OK = new Set(['ISSUED']);
const FINAL_FAIL = new Set(['REJECTED']);

/** История статусов, свежие сверху; последний шаг подсвечен. */
export function HistoryPanel({
  history,
  loading,
  now,
}: {
  history: StatusHistoryEntry[] | undefined;
  loading: boolean;
  now: number;
}) {
  const H = APPLICATION.history;
  const entries: TimelineEntry[] = [...(history ?? [])].reverse().map((entry, i) => ({
    key: `${entry.to_status}-${entry.created_at}`,
    title: H.status[entry.to_status],
    meta: H.actor[entry.actor_type],
    time: timeAgo(entry.created_at, now),
    state:
      i > 0
        ? 'past'
        : FINAL_OK.has(entry.to_status)
          ? 'complete'
          : FINAL_FAIL.has(entry.to_status)
            ? 'failed'
            : 'current',
  }));
  return (
    <Panel title={H.title} index={2}>
      {loading && !history ? <Skeleton height="160px" /> : <Timeline entries={entries} />}
    </Panel>
  );
}
