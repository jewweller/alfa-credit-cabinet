import { usePaymentSchedule } from './queries';
import { formatDate, formatMoneyExact, formatTerm } from '../format';
import { APPLICATION } from '../../i18n/ru';
import { InlineAlert, KeyValueList, Panel, ScheduleTable, Skeleton } from '../../ui';

/** График платежей по офферу — общий блок для карточки (C5) и экрана выдачи (C7). */
export function SchedulePanel({
  applicationId,
  offerId,
  index = 0,
}: {
  applicationId: string;
  offerId: string;
  index?: number;
}) {
  const schedule = usePaymentSchedule(applicationId, offerId);
  const S = APPLICATION.schedule;
  const T = APPLICATION.offer;

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
