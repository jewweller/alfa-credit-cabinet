import { useParams } from 'react-router';
import { ApiError } from '../../api/client';
import type { BankApplicationDetail, Product } from '../../api/types';
import { useApplicationHistory } from '../../features/application/queries';
import { HistoryPanel } from '../../features/application/SidePanels';
import {
  DecisionResultPanel,
  DocumentsPanel,
  FactsPanel,
  RulesPanel,
  ScoringPanel,
  SourcesPanel,
} from '../../features/bank/CardPanels';
import { DecisionForm } from '../../features/bank/DecisionForm';
import { useBankActions, useBankApplication } from '../../features/bank/queries';
import { formatMoney, formatTerm } from '../../features/format';
import { useProductMap, useProducts } from '../../features/products/useProducts';
import { ROUTES } from '../../features/routes';
import { ClientHeader } from '../../features/session/ClientHeader';
import { useMe } from '../../features/session/useMe';
import { useNow } from '../../features/useNow';
import { BANK, BANK_STATUS, HOME, MONEY } from '../../i18n/ru';
import {
  AppShell,
  BackLink,
  Button,
  ButtonLink,
  EmptyState,
  ErrorBanner,
  Hero,
  InlineAlert,
  MetaNote,
  Panel,
  SkeletonCard,
  SplitLayout,
  StatusBadge,
} from '../../ui';

/** Ручное рассмотрение: взять в работу → форма решения (B4). */
function ReviewPanel({ card, productList }: { card: BankApplicationDetail; productList: Product[] }) {
  const R = BANK.review;
  const me = useMe().data;
  const { assign, decide } = useBankActions(card.application.id);
  const why = card.rules.find((rule) => rule.fired);
  const mine = card.assignee?.id === me?.id;

  return (
    <Panel tone="highlight" eyebrow={R.eyebrow} title={mine ? BANK.decision.title : R.waitTitle}>
      {why && <MetaNote>{`${R.why}: ${why.code} — ${why.detail ?? why.title}`}</MetaNote>}
      {mine ? (
        <DecisionForm
          card={card}
          products={productList}
          busy={decide.isPending}
          error={decide.error}
          onSubmit={(body) => decide.mutate(body)}
        />
      ) : card.assignee ? (
        <InlineAlert tone="info">{BANK.card.assignedToOther(card.assignee.full_name)}</InlineAlert>
      ) : (
        <>
          <p>{R.waitText}</p>
          <div>
            <Button size="lg" arrow onClick={() => assign.mutate()} disabled={assign.isPending}>
              {assign.isPending ? BANK.card.taking : BANK.card.take}
            </Button>
          </div>
          {assign.isError && <InlineAlert>{assign.error.message}</InlineAlert>}
        </>
      )}
    </Panel>
  );
}

/** B3 — карточка заявки для андеррайтера; на ручном рассмотрении — с решением (B4). */
export function BankApplicationPage() {
  const { id = '' } = useParams();
  const products = useProductMap();
  const productList = useProducts().data ?? [];
  const card = useBankApplication(id);
  const data = card.data;
  const app = data?.application;
  const history = useApplicationHistory(id, app?.status_changed_at);
  const now = useNow();
  const C = BANK.card;
  const back = <BackLink to={ROUTES.bank} label={C.back} />;

  if (card.isError) {
    const notFound = card.error instanceof ApiError && card.error.status === 404;
    return (
      <AppShell header={<ClientHeader />} hero={<Hero top={back} title={notFound ? C.notFound.title : C.loadError} />}>
        {notFound ? (
          <EmptyState
            title={C.notFound.title}
            text={C.notFound.text}
            action={
              <ButtonLink to={ROUTES.bank} variant="secondary">
                {C.back}
              </ButtonLink>
            }
          />
        ) : (
          <ErrorBanner
            message={C.loadError}
            detail={card.error.message}
            retryLabel={HOME.retry}
            onRetry={() => card.refetch()}
            retrying={card.isFetching}
          />
        )}
      </AppShell>
    );
  }

  if (!data || !app) {
    return (
      <AppShell header={<ClientHeader />} hero={<Hero top={back} title={C.back} subtitle={null} stats={null} />}>
        <SplitLayout main={<SkeletonCard label={HOME.loading} />} aside={<SkeletonCard label={HOME.loading} index={1} />} />
      </AppShell>
    );
  }

  const productName = (app.product_id && products.get(app.product_id)?.name) || MONEY.noProduct;
  const status = BANK_STATUS[app.status];
  const scoring = data.scoring;

  return (
    <AppShell
      header={<ClientHeader />}
      hero={
        <Hero
          top={back}
          eyebrow={C.eyebrow(app.number, productName)}
          title={data.company.name}
          subtitle={C.subtitle(data.company.inn, data.applicant_name)}
          longStats
          stats={[
            { label: C.stats.amount, value: formatMoney(app.amount) },
            { label: C.stats.term, value: formatTerm(app.term_months) },
            { label: C.stats.score, value: scoring ? C.scoreValue(scoring.grade, scoring.total_score) : C.notScored, accent: true },
          ]}
        />
      }
    >
      <SplitLayout
        stickyAside={false}
        main={
          <>
            {app.status === 'MANUAL_REVIEW' ? (
              <ReviewPanel card={data} productList={productList} />
            ) : data.decision ? (
              <DecisionResultPanel decision={data.decision} app={app} products={products} />
            ) : (
              <Panel eyebrow={BANK.review.eyebrow} aside={<StatusBadge label={status.label} tone={status.tone} />}>
                <MetaNote>{BANK.scoring.pending}</MetaNote>
              </Panel>
            )}
            <ScoringPanel scoring={scoring} index={1} />
            <RulesPanel rules={data.rules} index={2} />
            <SourcesPanel enrichment={data.enrichment} index={3} />
          </>
        }
        aside={
          <>
            <FactsPanel app={app} products={products} />
            <DocumentsPanel app={app} index={1} />
            <HistoryPanel history={history.data} loading={history.isPending} now={now} />
          </>
        }
      />
    </AppShell>
  );
}
