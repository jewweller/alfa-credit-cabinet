import type { ReactNode } from 'react';
import { ApiError } from '../../api/client';
import type { CompanyLookup, Product } from '../../api/types';
import { APPLICATION, HOME, WIZARD, type WizardStep } from '../../i18n/ru';
import {
  Checkbox,
  ChoiceCards,
  ErrorBanner,
  FormGrid,
  InlineAlert,
  KeyValueList,
  Meter,
  MetaNote,
  MoneyField,
  Panel,
  ReviewGroup,
  SkeletonCard,
  StatusBadge,
  TextField,
  type Choice,
  type KeyValue,
} from '../../ui';
import { formatDate, formatMoney, formatMoneyRange, formatPercent, formatRate, formatTerm } from '../format';
import { monthlyPayment } from '../loanMath';
import { PURPOSE_CHOICES } from '../products/purposes';
import { useCompanyLookup } from './queries';
import type { DraftValues, FieldErrors } from './validation';

/** Долговая нагрузка, выше которой банк обычно не одобряет запрошенные условия (план, раздел 7, R9/R10). */
const SAFE_LOAD = 0.35;

/** Примерный платёж по базовой ставке; null — не хватает данных. */
export function estimatePayment(values: DraftValues, product: Product | undefined): string | null {
  if (!product || !values.amount || !values.term_months) return null;
  return monthlyPayment(values.amount, product.base_rate, values.term_months);
}

/** Нагрузка = (текущие платежи + новый платёж) / среднемесячная выручка (план, раздел 7). */
function estimateLoad(values: DraftValues, product: Product | undefined): number | null {
  const payment = estimatePayment(values, product);
  if (!payment || !values.revenue_12m || Number(values.revenue_12m) <= 0 || values.existing_payments_monthly === null) {
    return null;
  }
  return (Number(values.existing_payments_monthly) + Number(payment)) / (Number(values.revenue_12m) / 12);
}

const C = WIZARD.company;

function companyItems(company: CompanyLookup): KeyValue[] {
  const ie = company.kind === 'IE';
  const items: KeyValue[] = [
    { label: C.inn, value: company.inn },
    { label: ie ? C.ogrnip : C.ogrn, value: company.ogrn },
    { label: ie ? C.registeredIE : C.registered, value: formatDate(company.registered_at) },
    { label: C.okved, value: company.okved_main },
    { label: C.region, value: company.region },
  ];
  if (company.address) items.push({ label: C.address, value: company.address });
  if (company.director_fio) items.push({ label: C.director, value: company.director_fio });
  return items;
}

// ── Шаг 1: компания ─────────────────────────────────────────────────────────

export function CompanyStep({ inn, footer }: { inn: string | undefined; footer: ReactNode }) {
  const lookup = useCompanyLookup(inn);

  if (lookup.isPending) return <SkeletonCard label={C.loading} />;

  if (lookup.isError) {
    const notFound = lookup.error instanceof ApiError && lookup.error.status === 404;
    return notFound ? (
      <Panel tone="danger" eyebrow={C.eyebrow} title={C.notFound} footer={footer}>
        <p>{C.notFoundText}</p>
      </Panel>
    ) : (
      <Panel eyebrow={C.eyebrow} title={C.unavailable} footer={footer}>
        <ErrorBanner
          message={C.unavailable}
          detail={C.unavailableText}
          retryLabel={HOME.retry}
          onRetry={() => lookup.refetch()}
          retrying={lookup.isFetching}
        />
      </Panel>
    );
  }

  const company = lookup.data;
  const active = company.status === 'ACTIVE';
  return (
    <Panel
      eyebrow={C.eyebrow}
      title={company.name}
      aside={<StatusBadge label={C.registryStatus[company.status]} tone={active ? 'success' : 'danger'} />}
      footer={footer}
    >
      <KeyValueList columns={2} items={companyItems(company)} />
      {!active && <InlineAlert>{C.inactive}</InlineAlert>}
      <InlineAlert tone="info">{C.readOnly}</InlineAlert>
      <MetaNote>{company.kind === 'IE' ? C.sourceIE : C.sourceLLC}</MetaNote>
    </Panel>
  );
}

// ── Шаг 2: условия ──────────────────────────────────────────────────────────

const P = WIZARD.params;

export function ParamsStep({
  values,
  errors,
  products,
  product,
  onChange,
  footer,
}: {
  values: DraftValues;
  errors: FieldErrors;
  products: Product[];
  product: Product | undefined;
  onChange: (patch: Partial<DraftValues>) => void;
  footer: ReactNode;
}) {
  const productChoices: Choice<string>[] = products.map((p) => ({
    value: p.id,
    title: p.name,
    description: `${formatMoneyRange(p.min_amount, p.max_amount)} · ${P.limitsTerm(p.min_term, p.max_term)}`,
    meta: P.productRate(formatRate(p.base_rate)),
  }));

  const selectProduct = (id: string) => {
    const next = products.find((p) => p.id === id);
    // У продукта с одним сроком (овердрафт — 12 мес) срок подставляем сами.
    const fixedTerm = next && next.min_term === next.max_term ? { term_months: next.min_term } : {};
    onChange({ product_id: id, ...fixedTerm });
  };

  const mismatch = product && values.purpose && !product.purpose_tags.includes(values.purpose);

  return (
    <Panel eyebrow={P.eyebrow} title={WIZARD.steps.params} footer={footer}>
      <ChoiceCards
        label={P.product}
        options={productChoices}
        value={values.product_id}
        onChange={selectProduct}
        error={errors.product_id}
      />
      <ChoiceCards
        label={P.purpose}
        options={PURPOSE_CHOICES}
        value={values.purpose}
        onChange={(purpose) => onChange({ purpose })}
        error={errors.purpose}
      />
      {mismatch && <InlineAlert tone="info">{P.purposeMismatch}</InlineAlert>}
      <FormGrid>
        <MoneyField
          label={P.amount}
          large
          value={values.amount}
          onChange={(amount) => onChange({ amount })}
          hint={product ? P.limitsAmount(formatMoney(product.min_amount), formatMoney(product.max_amount)) : undefined}
          error={errors.amount}
        />
        <TextField
          label={P.term}
          suffix={P.termSuffix}
          inputMode="numeric"
          large
          value={values.term_months ?? ''}
          onChange={(e) => {
            const digits = e.target.value.replace(/\D/g, '').slice(0, 3);
            onChange({ term_months: digits ? Number(digits) : null });
          }}
          hint={product ? P.limitsTerm(product.min_term, product.max_term) : undefined}
          error={errors.term_months}
        />
      </FormGrid>
    </Panel>
  );
}

// ── Шаг 3: финансы ──────────────────────────────────────────────────────────

const F = WIZARD.finance;

export function FinanceStep({
  values,
  errors,
  product,
  onChange,
  footer,
}: {
  values: DraftValues;
  errors: FieldErrors;
  product: Product | undefined;
  onChange: (patch: Partial<DraftValues>) => void;
  footer: ReactNode;
}) {
  const load = estimateLoad(values, product);
  return (
    <Panel eyebrow={F.eyebrow} title={WIZARD.steps.finance} footer={footer}>
      <FormGrid>
        <MoneyField
          label={F.revenue}
          value={values.revenue_12m}
          onChange={(revenue_12m) => onChange({ revenue_12m })}
          hint={F.revenueHint}
          error={errors.revenue_12m}
        />
        <MoneyField
          label={F.payments}
          value={values.existing_payments_monthly}
          onChange={(existing_payments_monthly) => onChange({ existing_payments_monthly })}
          hint={F.paymentsHint}
          error={errors.existing_payments_monthly}
        />
      </FormGrid>
      {load !== null && (
        <Meter
          label={F.loadTitle}
          valueLabel={formatPercent(load)}
          value={load}
          threshold={SAFE_LOAD}
          thresholdLabel={F.threshold}
          note={load > SAFE_LOAD ? F.loadHigh : F.loadOk}
        />
      )}
    </Panel>
  );
}

// ── Шаг 4: проверка ─────────────────────────────────────────────────────────

const R = WIZARD.review;

export function ReviewStep({
  values,
  errors,
  product,
  companyName,
  onChange,
  onEdit,
  footer,
  submitError,
}: {
  values: DraftValues;
  errors: FieldErrors;
  product: Product | undefined;
  companyName: string | undefined;
  onChange: (patch: Partial<DraftValues>) => void;
  onEdit: (step: WizardStep) => void;
  footer: ReactNode;
  submitError: string | null;
}) {
  const payment = estimatePayment(values, product);
  const empty = WIZARD.empty;
  const incomplete = Object.keys(errors).some((field) => field !== 'bki_consent');
  return (
    <Panel tone="highlight" eyebrow={R.eyebrow} title={WIZARD.steps.review} footer={footer}>
      {incomplete && <InlineAlert>{R.incomplete}</InlineAlert>}
      <ReviewGroup title={R.company}>
        <KeyValueList valueFirst items={[{ label: C.name, value: companyName ?? empty }]} />
      </ReviewGroup>
      <ReviewGroup title={R.params} editLabel={R.edit} onEdit={() => onEdit('params')}>
        <KeyValueList
          valueFirst
          items={[
            { label: P.product, value: product?.name ?? empty, error: errors.product_id },
            {
              label: P.purpose,
              value: values.purpose ? APPLICATION.purpose[values.purpose] : empty,
              error: errors.purpose,
            },
            { label: P.amount, value: values.amount ? formatMoney(values.amount) : empty, error: errors.amount },
            {
              label: P.term,
              value: values.term_months ? formatTerm(values.term_months) : empty,
              error: errors.term_months,
            },
            { label: P.payment, value: payment ? `≈ ${formatMoney(payment)}` : empty },
          ]}
        />
      </ReviewGroup>
      <ReviewGroup title={R.finance} editLabel={R.edit} onEdit={() => onEdit('finance')}>
        <KeyValueList
          valueFirst
          items={[
            {
              label: F.revenue,
              value: values.revenue_12m ? formatMoney(values.revenue_12m) : empty,
              error: errors.revenue_12m,
            },
            {
              label: F.payments,
              value: values.existing_payments_monthly !== null ? formatMoney(values.existing_payments_monthly) : empty,
              error: errors.existing_payments_monthly,
            },
          ]}
        />
      </ReviewGroup>
      <Checkbox
        checked={values.bki_consent}
        onChange={(bki_consent) => onChange({ bki_consent })}
        label={R.consent}
        hint={R.consentHint}
        error={errors.bki_consent}
      />
      {submitError && <InlineAlert>{submitError}</InlineAlert>}
      <MetaNote>{R.submitHint}</MetaNote>
    </Panel>
  );
}

// ── Сводка справа ───────────────────────────────────────────────────────────

export function DraftSummary({
  values,
  product,
  saveNote,
}: {
  values: DraftValues;
  product: Product | undefined;
  saveNote: string | null;
}) {
  const payment = estimatePayment(values, product);
  const empty = WIZARD.empty;
  return (
    <Panel eyebrow={APPLICATION.details.title} index={1}>
      <KeyValueList
        items={[
          { label: P.payment, value: payment ? `≈ ${formatMoney(payment)}` : empty, emphasis: true },
          { label: P.product, value: product?.name ?? empty },
          { label: P.amount, value: values.amount ? formatMoney(values.amount) : empty },
          { label: P.term, value: values.term_months ? formatTerm(values.term_months) : empty },
          { label: P.purpose, value: values.purpose ? APPLICATION.purpose[values.purpose] : empty },
        ]}
      />
      <MetaNote>{P.paymentHint}</MetaNote>
      {saveNote && <MetaNote>{saveNote}</MetaNote>}
    </Panel>
  );
}
