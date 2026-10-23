import { useState } from 'react';
import { ApiError } from '../../api/client';
import type { LoanPurpose, ProductRecommendation } from '../../api/types';
import { useCreateDraft } from '../../features/draft/queries';
import { formatMoney, formatRate, formatTerm } from '../../features/format';
import { PURPOSE_CHOICES } from '../../features/products/purposes';
import { useRecommendations } from '../../features/products/useRecommendations';
import { ROUTES } from '../../features/routes';
import { ClientHeader } from '../../features/session/ClientHeader';
import { useDebounced } from '../../features/useDebounced';
import { APPLICATION, HOME, PICK } from '../../i18n/ru';
import {
  AppShell,
  BackLink,
  Button,
  ChoiceCards,
  EmptyState,
  ErrorBanner,
  FormGrid,
  Hero,
  InlineAlert,
  KeyValueList,
  MetaNote,
  MoneyField,
  Panel,
  Section,
  SkeletonCard,
  SplitLayout,
  StatusBadge,
  StepList,
  TextField,
} from '../../ui';

/** «Почему подходит»: цель продукта и попадание в лимиты — или что пришлось изменить. */
function reasons(rec: ProductRecommendation, purpose: LoanPurpose): string[] {
  const { product } = rec;
  return [
    PICK.why.purpose(APPLICATION.purpose[purpose]),
    rec.adjusted.includes('amount')
      ? PICK.adjusted.amount(formatMoney(rec.amount))
      : PICK.why.amountFits(formatMoney(product.min_amount), formatMoney(product.max_amount)),
    rec.adjusted.includes('term_months')
      ? PICK.adjusted.term_months(rec.term_months)
      : PICK.why.termFits(product.min_term, product.max_term),
  ];
}

function RecommendationCard({
  rec,
  purpose,
  index,
  creating,
  onApply,
}: {
  rec: ProductRecommendation;
  purpose: LoanPurpose;
  index: number;
  creating: boolean;
  onApply: () => void;
}) {
  const best = index === 0 && rec.adjusted.length === 0;
  const badge = best
    ? { label: PICK.bestBadge, tone: 'success' as const }
    : rec.adjusted.length === 0
      ? { label: PICK.fitsBadge, tone: 'progress' as const }
      : { label: PICK.adjustedBadge, tone: 'action' as const };
  return (
    <Panel
      tone={best ? 'highlight' : 'default'}
      eyebrow={rec.product.code}
      title={rec.product.name}
      aside={<StatusBadge label={badge.label} tone={badge.tone} />}
      index={index}
      footer={
        <Button arrow onClick={onApply} disabled={creating}>
          {creating ? PICK.creating : PICK.apply}
        </Button>
      }
    >
      <KeyValueList
        columns={3}
        items={[
          { label: PICK.perMonth, value: `≈ ${formatMoney(rec.monthly_payment)}`, emphasis: true },
          { label: APPLICATION.details.amount, value: formatMoney(rec.amount) },
          { label: APPLICATION.details.term, value: formatTerm(rec.term_months) },
          { label: APPLICATION.offer.rate, value: PICK.rateFrom(formatRate(rec.rate)) },
        ]}
      />
      <StepList items={reasons(rec, purpose).map((title) => ({ title, state: 'note' }))} />
    </Panel>
  );
}

/** C3 — подбор продукта по цели, сумме и сроку. */
export function ProductsPage() {
  const [purpose, setPurpose] = useState<LoanPurpose | null>(null);
  const [amount, setAmount] = useState<string | null>('1000000.00');
  const [term, setTerm] = useState('12');

  const termMonths = Number(term) || null;
  // Сумму и срок ждём, пока клиент допечатает; цель применяем сразу.
  const debouncedAmount = useDebounced(amount);
  const debouncedTerm = useDebounced(termMonths);
  const recommendations = useRecommendations({
    purpose: purpose ?? undefined,
    amount: debouncedAmount ?? undefined,
    term_months: debouncedTerm ?? undefined,
  });
  const create = useCreateDraft();
  const [applying, setApplying] = useState<string | null>(null);

  const apply = (rec: ProductRecommendation) => {
    if (!purpose) return;
    setApplying(rec.product.id);
    create.mutate({
      product_id: rec.product.id,
      purpose,
      amount: rec.amount,
      term_months: rec.term_months,
    });
  };

  const renderResults = () => {
    if (!purpose || !amount || !termMonths) return null;
    if (recommendations.isPending) {
      return (
        <>
          <SkeletonCard label={PICK.loading} />
          <SkeletonCard label={PICK.loading} index={1} />
        </>
      );
    }
    if (recommendations.isError) {
      return (
        <ErrorBanner
          message={PICK.loadError}
          detail={recommendations.error.message}
          retryLabel={HOME.retry}
          onRetry={() => recommendations.refetch()}
          retrying={recommendations.isFetching}
        />
      );
    }
    const items = recommendations.data;
    if (items.length === 0) return <EmptyState title={PICK.noResults} text={PICK.noResultsText} />;
    return (
      <Section title={PICK.resultsEyebrow} count={items.length}>
        {create.isError && (
          <InlineAlert>{create.error instanceof ApiError ? create.error.message : PICK.createError}</InlineAlert>
        )}
        {items.map((rec, i) => (
          <RecommendationCard
            key={rec.product.id}
            rec={rec}
            purpose={purpose}
            index={i}
            creating={create.isPending && applying === rec.product.id}
            onApply={() => apply(rec)}
          />
        ))}
      </Section>
    );
  };

  return (
    <AppShell
      header={<ClientHeader />}
      hero={
        <Hero
          top={<BackLink to={ROUTES.home} label={PICK.back} />}
          eyebrow={PICK.eyebrow}
          title={PICK.title}
          subtitle={PICK.subtitle}
        />
      }
    >
      <SplitLayout
        main={
          <>
            <Panel eyebrow={PICK.formEyebrow}>
              <ChoiceCards label={PICK.purposeLabel} options={PURPOSE_CHOICES} value={purpose} onChange={setPurpose} />
              <FormGrid>
                <MoneyField label={PICK.amount} value={amount} onChange={setAmount} large error={amount ? null : PICK.amountRequired} />
                <TextField
                  label={PICK.term}
                  suffix={PICK.termSuffix}
                  inputMode="numeric"
                  large
                  value={term}
                  onChange={(e) => setTerm(e.target.value.replace(/\D/g, '').slice(0, 3))}
                  error={termMonths ? null : PICK.termRequired}
                />
              </FormGrid>
              <MetaNote>{!purpose ? PICK.choosePurpose : !amount || !termMonths ? PICK.fillParams : PICK.resultsHint}</MetaNote>
            </Panel>
            {renderResults()}
          </>
        }
        aside={
          <Panel eyebrow={PICK.next.eyebrow} index={1}>
            <StepList items={PICK.next.steps.map((title) => ({ title, state: 'note' }))} />
          </Panel>
        }
      />
    </AppShell>
  );
}
