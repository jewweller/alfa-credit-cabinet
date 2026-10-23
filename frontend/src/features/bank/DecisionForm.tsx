import { useState, type FormEvent } from 'react';
import { ApiError } from '../../api/client';
import type {
  BankApplicationDetail,
  DocumentKind,
  Grade,
  Product,
  RejectReason,
  UnderwriterDecisionRequest,
  UnderwriterOutcome,
} from '../../api/types';
import { BANK } from '../../i18n/ru';
import { Button, Checkbox, ChoiceCards, FormGrid, InlineAlert, KeyValueList, MoneyField, TextField } from '../../ui';
import { formatMoney, formatPercent, formatRate } from '../format';
import { monthlyPayment } from '../loanMath';
import styles from './DecisionForm.module.css';

const OUTCOMES: UnderwriterOutcome[] = ['approved', 'counter_offer', 'info_requested', 'rejected'];
const DOCUMENTS: DocumentKind[] = ['tax_return', 'bank_statement', 'financial_statements', 'contract', 'other'];
const REASONS: RejectReason[] = ['underwriter_decision', 'no_suitable_terms', 'low_score', 'bankruptcy_or_overdue', 'company_inactive'];
/** Надбавка к базовой ставке по грейду, п.п. — как в движке (A/B — R9, C — R8); D/E — оценка специалиста. */
const RATE_DELTA: Record<Grade, number> = { A: 0, B: 2, C: 4, D: 6, E: 8 };
const SAFE_LOAD = 0.35;

type Errors = Partial<Record<'outcome' | 'rate' | 'product_id' | 'amount' | 'term_months' | 'info_items' | 'comment' | 'reason_code', string>>;

/** «18,5» → "18.50"; не число — null. */
function parseRate(text: string): string | null {
  const value = Number(text.replace(',', '.').trim());
  return text.trim() && Number.isFinite(value) && value > 0 ? value.toFixed(2) : null;
}

/** B4 — решение специалиста по заявке на ручном рассмотрении. */
export function DecisionForm({
  card,
  products,
  busy,
  error,
  onSubmit,
}: {
  card: BankApplicationDetail;
  products: Product[];
  busy: boolean;
  error: Error | null;
  onSubmit: (body: UnderwriterDecisionRequest) => void;
}) {
  const D = BANK.decision;
  const app = card.application;
  const requested = products.find((p) => p.id === app.product_id) ?? products[0];
  const grade = card.scoring?.grade ?? 'C';
  const suggestedRate = (product: Product) => (Number(product.base_rate) + RATE_DELTA[grade]).toFixed(2);

  const [outcome, setOutcome] = useState<UnderwriterOutcome | null>(null);
  const [productId, setProductId] = useState(requested.id);
  const [amount, setAmount] = useState<string | null>(app.amount);
  const [term, setTerm] = useState(String(app.term_months ?? ''));
  const [rate, setRate] = useState(suggestedRate(requested).replace('.', ','));
  const [documents, setDocuments] = useState<Set<DocumentKind>>(new Set(['tax_return']));
  const [message, setMessage] = useState('');
  const [reason, setReason] = useState<RejectReason | null>(null);
  const [comment, setComment] = useState('');
  const [errors, setErrors] = useState<Errors>({});

  const product = products.find((p) => p.id === productId) ?? requested;
  const isCounter = outcome === 'counter_offer';
  const offerProduct = isCounter ? product : requested;
  const offerAmount = isCounter ? amount : app.amount;
  const offerTerm = isCounter ? Number(term) : (app.term_months ?? 0);
  const offerRate = parseRate(rate);

  /** Поле поправили — его ошибка больше не актуальна. */
  const touched = (field: keyof Errors) =>
    setErrors((current) => {
      const { [field]: _, ...rest } = current;
      return rest;
    });

  // Сервер вернул ошибку поля — показываем её у поля.
  const serverField = error instanceof ApiError ? error.body?.field : undefined;
  const fieldError = (field: keyof Errors) =>
    errors[field] ?? (serverField === field && error ? error.message : undefined) ?? null;

  const validate = (): Errors => {
    const e: Errors = {};
    if (!outcome) e.outcome = D.errors.outcome;
    if ((outcome === 'approved' || isCounter) && !offerRate) e.rate = D.errors.rate;
    if (isCounter) {
      const value = Number(amount ?? 0);
      if (value < Number(product.min_amount) || value > Number(product.max_amount)) {
        e.amount = D.errors.amount(formatMoney(product.min_amount), formatMoney(product.max_amount));
      }
      if (!(offerTerm >= product.min_term && offerTerm <= product.max_term)) {
        e.term_months = D.errors.term(product.min_term, product.max_term);
      }
    }
    if (outcome === 'info_requested') {
      if (documents.size === 0) e.info_items = D.errors.documents;
      if (!message.trim()) e.comment = D.errors.message;
    }
    if (outcome === 'rejected' && !reason) e.reason_code = D.errors.reason;
    return e;
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0 || !outcome) return;
    const note = comment.trim() || null;
    switch (outcome) {
      case 'approved':
        return onSubmit({ outcome, rate: offerRate, comment: note });
      case 'counter_offer':
        return onSubmit({ outcome, product_id: product.id, amount, term_months: offerTerm, rate: offerRate, comment: note });
      case 'info_requested':
        return onSubmit({
          outcome,
          info_items: DOCUMENTS.filter((kind) => documents.has(kind)).map((kind) => ({
            kind,
            title: D.documentTitles[kind],
            required: kind !== 'other',
          })),
          comment: message.trim(),
        });
      case 'rejected':
        return onSubmit({ outcome, reason_code: reason, comment: note });
    }
  };

  // Что получит клиент: платёж и нагрузка по анкете и по выручке ФНС.
  const fnsRevenue = (card.enrichment.find((e) => e.source === 'fns_tb')?.response?.revenue as Record<string, number> | undefined)?.['2025'];
  const showPreview = (outcome === 'approved' || isCounter) && offerRate && Number(offerAmount) > 0 && offerTerm > 0;
  const payment = showPreview ? Number(monthlyPayment(offerAmount!, offerRate!, offerTerm)) : 0;
  const loadOf = (revenue: number) => (Number(app.existing_payments_monthly ?? 0) + payment) / (revenue / 12);
  const loadItem = (label: string, revenue: number) => {
    const load = loadOf(revenue);
    return { label, value: formatPercent(load), error: load > SAFE_LOAD ? D.loadHigh : null };
  };

  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <ChoiceCards
        label={D.outcomeLabel}
        columns={2}
        value={outcome}
        onChange={(value) => {
          setOutcome(value);
          setErrors({});
        }}
        options={OUTCOMES.map((value) => ({ value, title: D.outcomes[value].title, description: D.outcomes[value].text }))}
        error={errors.outcome}
      />

      {isCounter && (
        <>
          <ChoiceCards
            label={D.product}
            columns={3}
            value={productId}
            onChange={(id) => {
              setProductId(id);
              touched('product_id');
              setRate(suggestedRate(products.find((p) => p.id === id)!).replace('.', ','));
            }}
            options={products.map((p) => ({ value: p.id, title: p.name, description: formatRate(p.base_rate) }))}
            error={fieldError('product_id')}
          />
          <FormGrid>
            <MoneyField
              label={D.amount}
              value={amount}
              onChange={(value) => {
                setAmount(value);
                touched('amount');
              }}
              error={fieldError('amount')}
            />
            <TextField
              label={D.term}
              inputMode="numeric"
              suffix="мес"
              value={term}
              onChange={(e) => {
                setTerm(e.target.value.replace(/\D/g, '').slice(0, 3));
                touched('term_months');
              }}
              hint={D.termHint(product.min_term, product.max_term)}
              error={fieldError('term_months')}
            />
          </FormGrid>
        </>
      )}

      {(outcome === 'approved' || isCounter) && (
        <FormGrid>
          <TextField
            label={D.rate}
            inputMode="decimal"
            suffix="%"
            value={rate}
            onChange={(e) => {
              setRate(e.target.value.replace(/[^\d.,]/g, '').slice(0, 6));
              touched('rate');
            }}
            hint={D.rateHint(formatRate(suggestedRate(offerProduct)))}
            error={fieldError('rate')}
          />
        </FormGrid>
      )}

      {showPreview && (
        <div className={styles.preview}>
          <span className={styles.previewLabel}>{D.preview}</span>
          <KeyValueList
            columns={3}
            items={[
              { label: D.payment, value: formatMoney(payment), emphasis: true },
              loadItem(D.loadByForm, Number(app.revenue_12m)),
              ...(fnsRevenue ? [loadItem(D.loadByFns, fnsRevenue)] : []),
            ]}
          />
        </div>
      )}

      {outcome === 'info_requested' && (
        <>
          <fieldset className={styles.fieldset}>
            <legend className={styles.legend}>{D.documents}</legend>
            {DOCUMENTS.map((kind) => (
              <Checkbox
                key={kind}
                checked={documents.has(kind)}
                onChange={(on) => {
                  const next = new Set(documents);
                  if (on) next.add(kind);
                  else next.delete(kind);
                  setDocuments(next);
                  touched('info_items');
                }}
                label={D.documentTitles[kind]}
              />
            ))}
            {fieldError('info_items') && <InlineAlert>{fieldError('info_items')!}</InlineAlert>}
          </fieldset>
          <TextField
            label={D.message}
            value={message}
            onChange={(e) => {
              setMessage(e.target.value.slice(0, 1000));
              touched('comment');
            }}
            hint={D.messageHint}
            error={fieldError('comment')}
          />
        </>
      )}

      {outcome === 'rejected' && (
        <ChoiceCards
          label={D.reason}
          columns={1}
          value={reason}
          onChange={(value) => {
            setReason(value);
            touched('reason_code');
          }}
          options={REASONS.map((value) => ({ value, title: D.reasons[value].title, description: D.reasons[value].text }))}
          error={fieldError('reason_code')}
        />
      )}

      {outcome && outcome !== 'info_requested' && (
        <TextField label={D.comment} value={comment} onChange={(e) => setComment(e.target.value.slice(0, 1000))} hint={D.commentHint} />
      )}

      {error && !serverField && <InlineAlert>{D.error}</InlineAlert>}

      <div className={styles.actions}>
        <Button type="submit" size="lg" arrow disabled={busy || !outcome}>
          {D.submit}
        </Button>
      </div>
    </form>
  );
}
