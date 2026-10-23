import { useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router';
import { ApiError } from '../../api/client';
import type { ApplicationDetail, Product } from '../../api/types';
import { useApplication, useConfirmSigning, useSigningCode } from '../../features/application/queries';
import { formatMoney, formatRate, formatTerm } from '../../features/format';
import { useProductMap } from '../../features/products/useProducts';
import { ROUTES } from '../../features/routes';
import { ClientHeader } from '../../features/session/ClientHeader';
import { useMe } from '../../features/session/useMe';
import { APPLICATION, HOME, MONEY, SIGNING } from '../../i18n/ru';
import {
  AppShell,
  BackLink,
  Button,
  ButtonLink,
  EmptyState,
  ErrorBanner,
  Hero,
  InlineAlert,
  KeyValueList,
  MetaNote,
  Panel,
  SkeletonCard,
  SplitLayout,
  TextField,
} from '../../ui';
import styles from './SigningPage.module.css';

const timeFmt = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' });

/** Договор и подписание кодом. */
function SignForm({ app }: { app: ApplicationDetail }) {
  const navigate = useNavigate();
  const codeMutation = useSigningCode(app.id);
  const confirm = useConfirmSigning(app.id);
  const [code, setCode] = useState('');

  const issued = codeMutation.data;
  const S = SIGNING.sign;

  const onConfirm = () => {
    if (!issued) return;
    confirm.mutate(code, { onSuccess: () => navigate(ROUTES.result(app.id)) });
  };

  const wrongCode = confirm.error instanceof ApiError && confirm.error.body?.code === 'invalid_code';
  const error = confirm.isError ? (wrongCode ? S.wrong : S.error) : codeMutation.isError ? S.error : null;

  return (
    <Panel tone="highlight" eyebrow={S.eyebrow} title={S.title}>
      {!issued ? (
        <>
          <MetaNote>{S.hint}</MetaNote>
          <Button size="lg" onClick={() => codeMutation.mutate()} disabled={codeMutation.isPending}>
            {codeMutation.isPending ? S.getting : S.get}
          </Button>
        </>
      ) : (
        <>
          <p>{S.codeShown}</p>
          <div className={styles.codeBox}>
            <span className={styles.codeLabel}>{S.codeLabel}</span>
            <span className={styles.code}>{issued.code}</span>
            <span className={styles.expires}>{S.expires(timeFmt.format(new Date(issued.expires_at)))}</span>
          </div>
          <div className={styles.row}>
            <TextField
              label={S.input}
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              error={wrongCode ? S.wrong : null}
            />
            <Button size="lg" arrow onClick={onConfirm} disabled={confirm.isPending || code.length < 6}>
              {confirm.isPending ? S.confirming : S.confirm}
            </Button>
          </div>
        </>
      )}
      {error && !wrongCode && <InlineAlert>{error}</InlineAlert>}
    </Panel>
  );
}

function ContractPanel({ app, products }: { app: ApplicationDetail; products: Map<string, Product> }) {
  const C = SIGNING.contract;
  const offer = app.active_offer;
  const productName = (offer?.product_id && products.get(offer.product_id)?.name) || MONEY.noProduct;
  const me = useMe().data;
  return (
    <Panel eyebrow={C.eyebrow} title={C.title}>
      <p>{C.intro(me?.company?.name ?? '—')}</p>
      {offer && (
        <KeyValueList
          items={[
            { label: C.product, value: productName },
            { label: C.amount, value: formatMoney(offer.amount), emphasis: true },
            { label: C.term, value: formatTerm(offer.term_months) },
            { label: C.rate, value: formatRate(offer.rate) },
            { label: C.payment, value: formatMoney(offer.monthly_payment) },
          ]}
        />
      )}
      <MetaNote>{C.note}</MetaNote>
    </Panel>
  );
}

/** C6 — подписание договора. */
export function SigningPage() {
  const { id = '' } = useParams();
  const products = useProductMap();
  const application = useApplication(id);
  const app = application.data;
  const back = <BackLink to={ROUTES.application(id)} label={SIGNING.back} />;

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
      <AppShell header={<ClientHeader />} hero={<Hero top={back} title={SIGNING.title} subtitle={null} />}>
        <SplitLayout main={<SkeletonCard label={HOME.loading} />} aside={<SkeletonCard label={HOME.loading} index={1} />} />
      </AppShell>
    );
  }

  // Подписан или выдан — путь ведёт на итог; оффер ещё не принят — на карточку.
  if (app.status === 'SIGNED' || app.status === 'ISSUED') return <Navigate to={ROUTES.result(id)} replace />;
  if (app.status !== 'SIGNING') return <Navigate to={ROUTES.application(id)} replace />;

  return (
    <AppShell
      header={<ClientHeader />}
      hero={<Hero top={back} eyebrow={SIGNING.eyebrow(app.number)} title={SIGNING.title} subtitle={SIGNING.subtitle} />}
    >
      <SplitLayout
        main={<SignForm app={app} />}
        aside={<ContractPanel app={app} products={products} />}
      />
    </AppShell>
  );
}
