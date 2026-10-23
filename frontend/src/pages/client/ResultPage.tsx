import { Navigate, useParams } from 'react-router';
import { ApiError } from '../../api/client';
import type { ApplicationDetail, Product } from '../../api/types';
import { useApplication, useApplicationHistory, usePaymentSchedule } from '../../features/application/queries';
import { SchedulePanel } from '../../features/application/SchedulePanel';
import { HistoryPanel } from '../../features/application/SidePanels';
import { formatDate, formatMoney, formatRate, formatTerm } from '../../features/format';
import { useProductMap } from '../../features/products/useProducts';
import { ROUTES } from '../../features/routes';
import { ClientHeader } from '../../features/session/ClientHeader';
import { useNow } from '../../features/useNow';
import { APPLICATION, HOME, MONEY, RESULT } from '../../i18n/ru';
import {
  AppShell,
  BackLink,
  ButtonLink,
  EmptyState,
  ErrorBanner,
  Hero,
  KeyValueList,
  MetaNote,
  Panel,
  SkeletonCard,
  SplitLayout,
  StepList,
} from '../../ui';

/** Пока деньги «перечисляются»: статус SIGNED, карточка опрашивается и сама перейдёт в ISSUED. */
function IssuingBlock() {
  const W = RESULT.waiting;
  return (
    <Panel tone="highlight" eyebrow={APPLICATION.progress.eyebrow} title={W.title}>
      <StepList
        items={[
          { title: APPLICATION.history.status.SIGNED, state: 'done' },
          { title: W.title, state: 'current' },
        ]}
      />
      <MetaNote>{W.text}</MetaNote>
    </Panel>
  );
}

function IssuedBlock({ app, products }: { app: ApplicationDetail; products: Map<string, Product> }) {
  const R = RESULT.issued;
  const offer = app.active_offer;
  const schedule = usePaymentSchedule(app.id, offer?.id);
  const productName = (offer?.product_id && products.get(offer.product_id)?.name) || MONEY.noProduct;
  const firstDue = schedule.data?.items[0]?.due_date;
  return (
    <Panel
      tone="success"
      eyebrow={R.eyebrow}
      title={RESULT.title}
      footer={
        <ButtonLink to={ROUTES.home} variant="secondary">
          {R.home}
        </ButtonLink>
      }
    >
      <KeyValueList
        columns={3}
        items={[
          { label: R.account, value: R.accountNumber },
          { label: R.amount, value: formatMoney(offer?.amount), emphasis: true },
          { label: R.product, value: productName },
          { label: R.rate, value: offer ? formatRate(offer.rate) : '—' },
          { label: R.term, value: formatTerm(offer?.term_months) },
          { label: R.first, value: firstDue ? formatDate(firstDue) : '—' },
        ]}
      />
    </Panel>
  );
}

/** C7 — итог выдачи: деньги зачислены и график платежей. */
export function ResultPage() {
  const { id = '' } = useParams();
  const products = useProductMap();
  const application = useApplication(id);
  const app = application.data;
  const history = useApplicationHistory(id, app?.status_changed_at);
  const now = useNow();
  const back = <BackLink to={ROUTES.application(id)} label={RESULT.back} />;

  if (application.isError) {
    const notFound = application.error instanceof ApiError && application.error.status === 404;
    return (
      <AppShell
        header={<ClientHeader />}
        hero={<Hero top={back} title={notFound ? APPLICATION.notFound.title : APPLICATION.loadError} />}
      >
        {notFound ? (
          <EmptyState
            title={APPLICATION.notFound.title}
            text={APPLICATION.notFound.text}
            action={
              <ButtonLink to={ROUTES.home} variant="secondary">
                {APPLICATION.back}
              </ButtonLink>
            }
          />
        ) : (
          <ErrorBanner
            message={APPLICATION.loadError}
            detail={application.error.message}
            retryLabel={HOME.retry}
            onRetry={() => application.refetch()}
            retrying={application.isFetching}
          />
        )}
      </AppShell>
    );
  }

  if (!app) {
    return (
      <AppShell header={<ClientHeader />} hero={<Hero top={back} title={RESULT.title} subtitle={null} />}>
        <SplitLayout main={<SkeletonCard label={HOME.loading} />} aside={<SkeletonCard label={HOME.loading} index={1} />} />
      </AppShell>
    );
  }

  // Итог доступен только после подписания; раньше — возвращаем на карточку.
  if (app.status !== 'SIGNED' && app.status !== 'ISSUED') return <Navigate to={ROUTES.application(id)} replace />;

  const issued = app.status === 'ISSUED';
  return (
    <AppShell
      header={<ClientHeader />}
      hero={
        <Hero
          top={back}
          eyebrow={RESULT.eyebrow(app.number)}
          title={issued ? RESULT.title : RESULT.waiting.title}
          subtitle={issued ? RESULT.subtitle : RESULT.waiting.text}
        />
      }
    >
      {issued ? (
        // График — широкая таблица, ему нужна основная колонка; справа, как на карточке (C5), история.
        <SplitLayout
          stickyAside={false}
          main={
            <>
              <IssuedBlock app={app} products={products} />
              {app.active_offer && <SchedulePanel applicationId={app.id} offerId={app.active_offer.id} index={1} />}
            </>
          }
          aside={<HistoryPanel history={history.data} loading={history.isPending} now={now} />}
        />
      ) : (
        <IssuingBlock />
      )}
    </AppShell>
  );
}
