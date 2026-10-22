import type { ApplicationDetail, Offer, Product } from '../../api/types';
import { APPLICATION } from '../../i18n/ru';
import {
  Button,
  ConfirmButton,
  InlineAlert,
  KeyValueList,
  MetaNote,
  OfferCompare,
  Panel,
  ScheduleTable,
  Skeleton,
} from '../../ui';
import { formatDate, formatMoney, formatMoneyExact, formatRate, formatTerm } from '../format';
import { useApplicationActions, usePaymentSchedule } from './queries';

const T = APPLICATION.offer;

interface Props {
  app: ApplicationDetail;
  offer: Offer;
  products: Map<string, Product>;
  /** Кнопки «Принять / Отказаться» — только пока оффер действует. */
  actionable: boolean;
}

/** Предложение банка: условия, сравнение «просили / предлагаем», график, решение клиента. */
export function OfferBlock({ app, offer, products, actionable }: Props) {
  const actions = useApplicationActions(app.id);
  const productName = (id: string | null) => (id && products.get(id)?.name) || T.unknown;
  const isCounter = app.status === 'COUNTER_OFFER' || app.decision?.outcome === 'counter_offer';
  const busy = actions.accept.isPending || actions.decline.isPending;
  const error = actions.accept.error ?? actions.decline.error;

  return (
    <>
      <Panel
        tone="highlight"
        eyebrow={T.eyebrow}
        title={isCounter ? T.counterTitle : T.approvedTitle}
        footer={
          actionable ? (
            <>
              <Button size="lg" arrow onClick={() => actions.accept.mutate(offer.id)} disabled={busy}>
                {T.accept}
              </Button>
              <ConfirmButton
                label={T.decline}
                question={T.declineQuestion}
                confirmLabel={T.declineConfirm}
                cancelLabel={T.keep}
                busy={busy}
                onConfirm={() => actions.decline.mutate(offer.id)}
              />
            </>
          ) : undefined
        }
      >
        <KeyValueList
          columns={3}
          items={[
            { label: T.payment, value: formatMoneyExact(offer.monthly_payment), emphasis: true },
            { label: T.amount, value: formatMoney(offer.amount), emphasis: true },
            { label: T.rate, value: formatRate(offer.rate), emphasis: true },
          ]}
        />

        {isCounter && (
          <OfferCompare
            requestedLabel={T.requested}
            offeredLabel={T.offered}
            rows={[
              { label: T.product, requested: productName(app.product_id), offered: productName(offer.product_id) },
              { label: T.amount, requested: formatMoney(app.amount), offered: formatMoney(offer.amount) },
              { label: T.term, requested: formatTerm(app.term_months), offered: formatTerm(offer.term_months) },
            ]}
          />
        )}

        {app.decision && (
          <MetaNote>{T.decidedBy(app.decision.decided_by, formatDate(app.decision.decided_at))}</MetaNote>
        )}
        {error && <InlineAlert>{error.message || APPLICATION.actionError}</InlineAlert>}
      </Panel>

      <ScheduleBlock applicationId={app.id} offerId={offer.id} index={1} />
    </>
  );
}

function ScheduleBlock({ applicationId, offerId, index }: { applicationId: string; offerId: string; index: number }) {
  const schedule = usePaymentSchedule(applicationId, offerId);
  const S = APPLICATION.schedule;

  return (
    <Panel eyebrow={formatTerm(schedule.data?.term_months)} title={S.title} index={index}>
      {schedule.isPending && <Skeleton height="120px" />}
      {schedule.isError && <InlineAlert>{S.loadError}</InlineAlert>}
      {schedule.data && (
        <>
          <KeyValueList
            columns={3}
            items={[
              { label: T.payment, value: formatMoneyExact(schedule.data.monthly_payment) },
              { label: T.overpayment, value: formatMoneyExact(schedule.data.overpayment) },
              { label: T.total, value: formatMoneyExact(schedule.data.total_payment) },
            ]}
          />
          <ScheduleTable
            columns={S.columns}
            rows={schedule.data.items.map((item) => ({
              number: item.number,
              date: formatDate(item.due_date),
              payment: formatMoneyExact(item.payment),
              principal: formatMoneyExact(item.principal),
              interest: formatMoneyExact(item.interest),
              balance: formatMoneyExact(item.balance),
            }))}
            showAllLabel={S.showAll}
            collapseLabel={S.collapse}
          />
        </>
      )}
    </Panel>
  );
}
