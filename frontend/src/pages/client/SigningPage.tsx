import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router';
import { ApiError } from '../../api/client';
import type { ApplicationDetail, Product } from '../../api/types';
import { useApplication, useConfirmSigning, useSigningCode } from '../../features/application/queries';
import { formatMoney, formatRate, formatTerm } from '../../features/format';
import { useProductMap } from '../../features/products/useProducts';
import { ROUTES } from '../../features/routes';
import { ClientHeader } from '../../features/session/ClientHeader';
import { useMe } from '../../features/session/useMe';
import { APPLICATION, HOME, MONEY, RESULT, SIGNING } from '../../i18n/ru';
import {
  AppShell,
  BackLink,
  Button,
  ButtonLink,
  ClauseList,
  CodeDisplay,
  EmptyState,
  ErrorBanner,
  Form,
  Hero,
  InlineAlert,
  KeyValueList,
  MetaNote,
  Panel,
  SkeletonCard,
  SplitLayout,
  TextField,
} from '../../ui';

const timeFmt = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' });

/** Договор и подписание кодом. */
function SignForm({ app }: { app: ApplicationDetail }) {
  const navigate = useNavigate();
  const codeMutation = useSigningCode(app.id);
  const confirm = useConfirmSigning(app.id);
  const [code, setCode] = useState('');

  const issued = codeMutation.data;
  const S = SIGNING.sign;

  // Новый код заменяет прежний: поле и ошибку сбрасываем.
  const getCode = () =>
    codeMutation.mutate(undefined, {
      onSuccess: () => {
        setCode('');
        confirm.reset();
      },
    });

  const onConfirm = (e: FormEvent) => {
    e.preventDefault();
    if (!issued || code.length < 6 || confirm.isPending) return;
    confirm.mutate(code, { onSuccess: () => navigate(ROUTES.result(app.id)) });
  };

  const wrongCode = confirm.error instanceof ApiError && confirm.error.body?.code === 'invalid_code';
  const error = confirm.isError ? (wrongCode ? S.wrong : S.error) : codeMutation.isError ? S.error : null;

  return (
    <Panel tone="highlight" eyebrow={S.eyebrow} title={S.title}>
      {!issued ? (
        <>
          <MetaNote>{S.hint}</MetaNote>
          <Button size="lg" onClick={getCode} disabled={codeMutation.isPending}>
            {codeMutation.isPending ? S.getting : S.get}
          </Button>
        </>
      ) : (
        <>
          <p>{S.codeShown}</p>
          <CodeDisplay label={S.codeLabel} code={issued.code} note={S.expires(timeFmt.format(new Date(issued.expires_at)))} />
          <Form layout="inline" onSubmit={onConfirm}>
            <TextField
              label={S.input}
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              error={wrongCode ? S.wrong : null}
            />
            <Button type="submit" size="lg" arrow disabled={confirm.isPending || code.length < 6}>
              {confirm.isPending ? S.confirming : S.confirm}
            </Button>
          </Form>
          <div>
            <Button variant="ghost" onClick={getCode} disabled={codeMutation.isPending || confirm.isPending}>
              {codeMutation.isPending ? S.getting : S.again}
            </Button>
          </div>
        </>
      )}
      {error && !wrongCode && <InlineAlert>{error}</InlineAlert>}
    </Panel>
  );
}

/** Договор из шаблона с данными предложения (план, раздел 11, C6). */
function ContractPanel({ app, products }: { app: ApplicationDetail; products: Map<string, Product> }) {
  const C = SIGNING.contract;
  const offer = app.active_offer;
  const productName = (offer?.product_id && products.get(offer.product_id)?.name) || MONEY.noProduct;
  const purpose = app.purpose ? APPLICATION.purpose[app.purpose] : '—';
  const me = useMe().data;
  return (
    <Panel eyebrow={C.eyebrow(app.number)} title={C.title}>
      <p>{C.parties(me?.company?.name ?? '—', me?.company?.inn ?? '—', me?.full_name ?? '—')}</p>
      {offer && (
        <>
          <KeyValueList
            columns={3}
            items={[
              { label: C.amount, value: formatMoney(offer.amount), emphasis: true },
              { label: C.term, value: formatTerm(offer.term_months) },
              { label: C.rate, value: formatRate(offer.rate) },
              { label: C.payment, value: formatMoney(offer.monthly_payment) },
              { label: C.product, value: productName },
              { label: C.purpose, value: purpose },
            ]}
          />
          <ClauseList
            items={C.clauses({
              amount: formatMoney(offer.amount),
              term: formatTerm(offer.term_months),
              purpose,
              rate: formatRate(offer.rate),
              payment: formatMoney(offer.monthly_payment),
              account: RESULT.issued.accountNumber,
            })}
          />
        </>
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
      {/* Сначала условия, потом подпись: на узком экране форма уходит под договор. */}
      <SplitLayout
        main={<ContractPanel app={app} products={products} />}
        aside={<SignForm app={app} />}
      />
    </AppShell>
  );
}
