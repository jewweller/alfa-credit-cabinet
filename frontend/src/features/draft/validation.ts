import type { ApplicationDetail, LoanPurpose, Product } from '../../api/types';
import { WIZARD, type WizardStep } from '../../i18n/ru';
import { formatMoney } from '../format';

export const WIZARD_STEPS: WizardStep[] = ['company', 'params', 'finance', 'review'];

/** Поля черновика, которые клиент заполняет в мастере. */
export interface DraftValues {
  product_id: string | null;
  purpose: LoanPurpose | null;
  amount: string | null;
  term_months: number | null;
  revenue_12m: string | null;
  existing_payments_monthly: string | null;
  bki_consent: boolean;
}

export type DraftField = keyof DraftValues;
export type FieldErrors = Partial<Record<DraftField, string>>;

export const DRAFT_FIELDS: DraftField[] = [
  'product_id',
  'purpose',
  'amount',
  'term_months',
  'revenue_12m',
  'existing_payments_monthly',
  'bki_consent',
];

export function pickDraft(app: ApplicationDetail): DraftValues {
  return {
    product_id: app.product_id,
    purpose: app.purpose,
    amount: app.amount,
    term_months: app.term_months,
    revenue_12m: app.revenue_12m,
    existing_payments_monthly: app.existing_payments_monthly,
    bki_consent: app.bki_consent,
  };
}

/** На каком шаге поле — туда ведём при ошибке сервера (`field` в ответе 422). */
export function stepOfField(field: string | null | undefined): WizardStep {
  switch (field) {
    case 'product_id':
    case 'purpose':
    case 'amount':
    case 'term_months':
      return 'params';
    case 'revenue_12m':
    case 'existing_payments_monthly':
      return 'finance';
    case 'bki_consent':
      return 'review';
    default:
      return 'company';
  }
}

const V = WIZARD.validation;

function paramsErrors(values: DraftValues, product: Product | undefined): FieldErrors {
  const errors: FieldErrors = {};
  if (!product) errors.product_id = V.product;
  if (!values.purpose) errors.purpose = V.purpose;
  if (!values.amount) errors.amount = V.amount;
  else if (
    product &&
    (Number(values.amount) < Number(product.min_amount) || Number(values.amount) > Number(product.max_amount))
  ) {
    errors.amount = V.amountRange(formatMoney(product.min_amount), formatMoney(product.max_amount));
  }
  if (!values.term_months) errors.term_months = V.term;
  else if (product && (values.term_months < product.min_term || values.term_months > product.max_term)) {
    errors.term_months = V.termRange(product.min_term, product.max_term);
  }
  return errors;
}

function financeErrors(values: DraftValues): FieldErrors {
  const errors: FieldErrors = {};
  if (!values.revenue_12m || Number(values.revenue_12m) <= 0) errors.revenue_12m = V.revenue;
  if (values.existing_payments_monthly === null) errors.existing_payments_monthly = V.payments;
  return errors;
}

/** Ошибки шага; на проверке — всё сразу, как при отправке на сервере. */
export function validateStep(step: WizardStep, values: DraftValues, product: Product | undefined): FieldErrors {
  switch (step) {
    case 'company':
      return {};
    case 'params':
      return paramsErrors(values, product);
    case 'finance':
      return financeErrors(values);
    case 'review':
      return {
        ...paramsErrors(values, product),
        ...financeErrors(values),
        ...(values.bki_consent ? {} : { bki_consent: V.consent }),
      };
  }
}

/** Докуда клиент может дойти сразу: первый шаг с ошибками (для вернувшегося к черновику). */
export function firstIncompleteStep(values: DraftValues, product: Product | undefined): number {
  if (Object.keys(paramsErrors(values, product)).length > 0) return WIZARD_STEPS.indexOf('params');
  if (Object.keys(financeErrors(values)).length > 0) return WIZARD_STEPS.indexOf('finance');
  return WIZARD_STEPS.indexOf('review');
}
