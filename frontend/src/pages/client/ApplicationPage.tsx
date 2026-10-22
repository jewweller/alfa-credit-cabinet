import { useParams } from 'react-router';
import { ApiError } from '../../api/client';
import type { ApplicationDetail, Product } from '../../api/types';
import { InfoRequestBlock } from '../../features/application/InfoRequestBlock';
import { OfferBlock } from '../../features/application/OfferBlock';
import { useApplication, useApplicationHistory } from '../../features/application/queries';
import { DetailsPanel, HistoryPanel } from '../../features/application/SidePanels';
import {
  NextStepBlock,
  RejectionBlock,
  ReviewBlock,
  WaitingBlock,
} from '../../features/application/StatusBlocks';
import { timeAgo } from '../../features/format';
import { useProductMap } from '../../features/products/useProducts';
import { ROUTES } from '../../features/routes';
import { ClientHeader } from '../../features/session/ClientHeader';
import { useNow } from '../../features/useNow';
import { APPLICATION, HOME, MONEY, STAGE_LABELS, STAGES, STATUS_UI } from '../../i18n/ru';
import {
  AppShell,
  BackLink,
  ButtonLink,
  EmptyState,
  ErrorBanner,
  Hero,
  MetaNote,
  Panel,
  SkeletonCard,
  SplitLayout,
  StageProgress,
  StatusBadge,
} from '../../ui';

/** Главный блок экрана — свой для каждого статуса. */
function StatusContent({ app, products }: { app: ApplicationDetail; products: Map<string, Product> }) {
  switch (app.status) {
    case 'SUBMITTED':
    case 'ENRICHMENT':
    case 'SCORING':
      return <WaitingBlock status={app.status} />;
    case 'MANUAL_REVIEW':
      return <ReviewBlock />;
    case 'INFO_REQUESTED':
      return app.info_request ? <InfoRequestBlock app={app} request={app.info_request} /> : <ReviewBlock />;
    case 'APPROVED':
    case 'COUNTER_OFFER':
      return app.active_offer ? (
        <OfferBlock app={app} offer={app.active_offer} products={products} actionable={app.active_offer.status === 'active'} />
      ) : (
        <NextStepBlock app={app} />
      );
    case 'REJECTED':
      return <RejectionBlock app={app} />;
    case 'SIGNING':
    case 'SIGNED':
    case 'ISSUED':
      return (
        <>
          <NextStepBlock app={app} />
          {app.active_offer && <OfferBlock app={app} offer={app.active_offer} products={products} actionable={false} />}
        </>
      );
    default:
      return <NextStepBlock app={app} />;
  }
}

/** C5 — карточка заявки. */
export function ApplicationPage() {
  const { id = '' } = useParams();
  const now = useNow();
  const products = useProductMap();
  const application = useApplication(id);
  const app = application.data;
  const history = useApplicationHistory(id, app?.status_changed_at);

  const back = <BackLink to={ROUTES.home} label={APPLICATION.back} />;

  if (application.isError) {
    const notFound = application.error instanceof ApiError && application.error.status === 404;
    return (
      <AppShell header={<ClientHeader />} hero={<Hero top={back} title={notFound ? APPLICATION.notFound.title : APPLICATION.loadError} />}>
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
      <AppShell header={<ClientHeader />} hero={<Hero top={back} title="" subtitle={null} />}>
        <SplitLayout
          main={
            <>
              <SkeletonCard label={HOME.loading} />
              <SkeletonCard label={HOME.loading} index={1} />
            </>
          }
          aside={<SkeletonCard label={HOME.loading} index={2} />}
        />
      </AppShell>
    );
  }

  const ui = STATUS_UI[app.status];
  const productName = (app.product_id && products.get(app.product_id)?.name) || MONEY.noProduct;
  const live = ui.block === 'bank';

  return (
    <AppShell
      header={<ClientHeader />}
      hero={
        <Hero
          top={back}
          eyebrow={APPLICATION.eyebrow(app.number, productName)}
          title={APPLICATION.title[app.status]}
          subtitle={APPLICATION.subtitle[app.status]}
        />
      }
    >
      <SplitLayout
        stickyAside={false}
        main={
          <>
            {ui.stage && (
              <Panel
                eyebrow={APPLICATION.progress.eyebrow}
                aside={<StatusBadge key={ui.badge} label={ui.badge} tone={ui.tone} />}
              >
                <StageProgress
                  labels={STAGES.map((s) => STAGE_LABELS[s])}
                  current={STAGES.indexOf(ui.stage)}
                  state={ui.stageState}
                />
                <MetaNote>
                  {`${HOME.statusChanged(timeAgo(app.status_changed_at, now))}${live ? ` · ${APPLICATION.progress.live}` : ''}`}
                </MetaNote>
              </Panel>
            )}
            <StatusContent key={app.status} app={app} products={products} />
          </>
        }
        aside={
          <>
            <HistoryPanel history={history.data} loading={history.isPending} now={now} />
            <DetailsPanel app={app} products={products} />
          </>
        }
      />
    </AppShell>
  );
}
