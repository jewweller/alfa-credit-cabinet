import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router';
import { ApiError, apiPost, newIdempotencyKey } from '../../api/client';
import type { ApplicationDetail, Product } from '../../api/types';
import { applicationKey, useApplication, useApplicationActions } from '../../features/application/queries';
import { CompanyStep, DraftSummary, FinanceStep, ParamsStep, ReviewStep } from '../../features/draft/steps';
import { useDraftForm, type SaveState } from '../../features/draft/useDraftForm';
import {
  firstIncompleteStep,
  pickDraft,
  stepOfField,
  validateStep,
  WIZARD_STEPS,
  type DraftField,
  type DraftValues,
  type FieldErrors,
} from '../../features/draft/validation';
import { timeAgo } from '../../features/format';
import { useProducts } from '../../features/products/useProducts';
import { ROUTES } from '../../features/routes';
import { ClientHeader } from '../../features/session/ClientHeader';
import { useMe } from '../../features/session/useMe';
import { useNow } from '../../features/useNow';
import { APPLICATION, HOME, WIZARD, type WizardStep } from '../../i18n/ru';
import {
  AppShell,
  BackLink,
  Button,
  ButtonLink,
  ConfirmButton,
  EmptyState,
  ErrorBanner,
  Hero,
  SkeletonCard,
  SplitLayout,
  Stepper,
} from '../../ui';

function saveNote(state: SaveState, savedAt: string | null, now: number): string | null {
  switch (state) {
    case 'saving':
      return WIZARD.save.saving;
    case 'saved':
      return savedAt ? WIZARD.save.saved(timeAgo(savedAt, now)) : null;
    case 'error':
      return WIZARD.save.error;
    case 'conflict':
      return WIZARD.save.conflict;
    default:
      return null;
  }
}

/** Мастер по загруженному черновику: шаги, автосохранение, отправка. */
function DraftWizard({ app, products }: { app: ApplicationDetail; products: Product[] }) {
  const now = useNow();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: me } = useMe();
  const form = useDraftForm(app);
  const { values } = form;
  const product = products.find((p) => p.id === values.product_id);

  const [params, setParams] = useSearchParams();
  const [visited, setVisited] = useState(() =>
    firstIncompleteStep(pickDraft(app), products.find((p) => p.id === app.product_id)),
  );
  // Дальше первого незаполненного шага не пускаем: стёрли сумму — «Финансы» и «Проверка» закрыты.
  const reached = Math.min(visited, firstIncompleteStep(values, product));
  const requested = WIZARD_STEPS.indexOf(params.get('step') as WizardStep);
  const index = requested >= 0 ? Math.min(requested, reached) : 0;
  const step = WIZARD_STEPS[index];

  // Ошибки показываем после попытки пройти шаг; ошибку сервера — пока поле не изменили.
  const [attempted, setAttempted] = useState<ReadonlySet<WizardStep>>(new Set());
  const [serverError, setServerError] = useState<{ field: DraftField; message: string } | null>(null);
  // На проверке незаполненное видно сразу; согласие — только после попытки отправить.
  const stepErrors = validateStep(step, values, product);
  const shownErrors: FieldErrors =
    step === 'review'
      ? Object.fromEntries(
          Object.entries(stepErrors).filter(([field]) => field !== 'bki_consent' || attempted.has('review')),
        )
      : attempted.has(step)
        ? stepErrors
        : {};
  const errors: FieldErrors = {
    ...shownErrors,
    ...(serverError ? { [serverError.field]: serverError.message } : {}),
  };

  const change = (patch: Partial<DraftValues>) => {
    if (serverError && serverError.field in patch) setServerError(null);
    form.change(patch);
  };

  const goTo = (target: number) => {
    void form.flush();
    setVisited((r) => Math.max(r, target));
    setParams({ step: WIZARD_STEPS[target] }, { replace: true });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  /** Дальше — только если шаг заполнен; иначе подсвечиваем поля. */
  const next = () => {
    if (Object.keys(validateStep(step, values, product)).length > 0) {
      setAttempted((s) => new Set(s).add(step));
      return;
    }
    goTo(index + 1);
  };

  const submit = useMutation({
    mutationFn: async (idempotencyKey: string) => {
      if (!(await form.flush())) throw new Error(WIZARD.save.error);
      return apiPost<ApplicationDetail>(`/applications/${app.id}/submit`, { idempotencyKey });
    },
    onSuccess: (detail) => {
      queryClient.setQueryData(applicationKey(app.id), detail);
      void queryClient.invalidateQueries({ queryKey: ['applications'] });
      void queryClient.invalidateQueries({ queryKey: ['feed'] });
      navigate(ROUTES.application(app.id), { replace: true });
    },
    onError: (error) => {
      // 422 с полем — ведём на шаг с этим полем и показываем текст сервера у поля.
      const field = error instanceof ApiError ? error.body?.field : null;
      if (field && field in values) {
        setServerError({ field: field as DraftField, message: error.message });
        const target = WIZARD_STEPS.indexOf(stepOfField(field));
        if (target !== index) goTo(target);
      }
    },
  });

  /** Ошибки показываем здесь же, у полей проверки, — на другой шаг не перебрасываем. */
  const onSubmit = () => {
    const fields = Object.keys(validateStep('review', values, product));
    if (fields.length > 0) {
      setAttempted((s) => new Set(s).add('review'));
      // Общее сообщение о незаполненных полях — вверху панели; если не хватает только согласия, оно рядом с кнопкой.
      if (fields.some((field) => field !== 'bki_consent')) window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    submit.mutate(newIdempotencyKey());
  };

  const { cancel } = useApplicationActions(app.id);
  const busy = submit.isPending || cancel.isPending;

  const back = index > 0 && (
    <Button variant="secondary" onClick={() => goTo(index - 1)} disabled={busy}>
      {WIZARD.prevStep}
    </Button>
  );
  const stepFooter = (
    <>
      {back}
      <Button arrow onClick={next}>
        {WIZARD.nextStep}
      </Button>
    </>
  );
  const reviewFooter = (
    <>
      <Button size="lg" arrow onClick={onSubmit} disabled={busy}>
        {submit.isPending ? WIZARD.review.submitting : WIZARD.review.submit}
      </Button>
      {back}
      <ConfirmButton
        label={WIZARD.review.cancel}
        question={WIZARD.review.cancelQuestion}
        confirmLabel={WIZARD.review.cancelConfirm}
        cancelLabel={WIZARD.review.keep}
        busy={busy}
        onConfirm={() => cancel.mutate(undefined, { onSuccess: () => navigate(ROUTES.home) })}
      />
    </>
  );

  const submitError =
    submit.isError && !serverError
      ? submit.error instanceof ApiError
        ? submit.error.message
        : WIZARD.review.submitError
      : cancel.isError
        ? APPLICATION.actionError
        : null;

  const stepContent = {
    company: <CompanyStep inn={me?.company?.inn} footer={stepFooter} />,
    params: (
      <ParamsStep
        values={values}
        errors={errors}
        products={products}
        product={product}
        onChange={change}
        footer={stepFooter}
      />
    ),
    finance: <FinanceStep values={values} errors={errors} product={product} onChange={change} footer={stepFooter} />,
    review: (
      <ReviewStep
        values={values}
        errors={errors}
        product={product}
        companyName={me?.company?.name}
        onChange={change}
        onEdit={(target) => goTo(WIZARD_STEPS.indexOf(target))}
        footer={reviewFooter}
        submitError={submitError}
      />
    ),
  } satisfies Record<WizardStep, unknown>;

  return (
    <AppShell
      header={<ClientHeader />}
      hero={
        <Hero
          top={<BackLink to={ROUTES.home} label={WIZARD.back} />}
          eyebrow={`${WIZARD.eyebrow(app.number)} · ${WIZARD.stepLabel(index + 1, WIZARD_STEPS.length)}`}
          title={WIZARD.title}
          subtitle={WIZARD.subtitle[step]}
        />
      }
    >
      <SplitLayout
        main={
          <>
            <Stepper
              labels={WIZARD_STEPS.map((s) => WIZARD.steps[s])}
              current={index}
              reached={reached}
              onSelect={goTo}
            />
            <div key={step}>{stepContent[step]}</div>
          </>
        }
        aside={<DraftSummary values={values} product={product} saveNote={saveNote(form.saveState, form.savedAt, now)} />}
      />
    </AppShell>
  );
}

/** C4 — мастер заявки. Работает только с черновиком; отправленную заявку показывает карточка (C5). */
export function ApplicationEditPage() {
  const { id = '' } = useParams();
  const application = useApplication(id);
  const app = application.data;
  // Без каталога не понять, заполнены ли условия, — а от этого зависит, на какой шаг можно вернуться.
  const products = useProducts();
  const back = <BackLink to={ROUTES.home} label={WIZARD.back} />;

  if (products.isError) {
    return (
      <AppShell header={<ClientHeader />} hero={<Hero top={back} title={WIZARD.title} />}>
        <ErrorBanner
          message={APPLICATION.loadError}
          detail={products.error.message}
          retryLabel={HOME.retry}
          onRetry={() => products.refetch()}
          retrying={products.isFetching}
        />
      </AppShell>
    );
  }

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

  if (!app || !products.data) {
    return (
      <AppShell header={<ClientHeader />} hero={<Hero top={back} title={WIZARD.title} subtitle={null} />}>
        <SplitLayout
          main={<SkeletonCard label={HOME.loading} />}
          aside={<SkeletonCard label={HOME.loading} index={1} />}
        />
      </AppShell>
    );
  }

  if (app.status !== 'DRAFT') return <Navigate to={ROUTES.application(app.id)} replace />;

  return <DraftWizard key={app.id} app={app} products={products.data} />;
}
