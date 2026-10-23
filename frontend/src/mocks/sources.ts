// Ответы внешних источников по тестовым ИНН (план, раздел 8) — то, что бэк получил бы от
// сервиса моков на этапе обогащения. Идут в скоринг и показываются андеррайтеру как есть.
import type { CompanyLookup } from '../api/types';
import { registry } from './data';

/** ФНС «Прозрачный бизнес»: `GET /fns-tb/v1/profile/{inn}`. */
export interface FnsProfile {
  revenue: Record<string, number>;
  tax_debt_rub: number;
  msp_category: 'micro' | 'small';
  employees: number;
  flags: { mass_address: boolean; unreliable_address: boolean; unreliable_director: boolean };
}

export interface BkiLoan {
  type: 'loan' | 'credit_card' | 'leasing';
  balance: number;
  monthly_payment: number;
  max_overdue_days_24m: number;
  current_overdue_days: number;
}

/** БКИ: `POST /bki/v1/reports`. */
export interface BkiReport {
  report_id: string;
  has_history: boolean;
  bankruptcy: boolean;
  loans: BkiLoan[];
  inquiries_30d: number;
}

export interface Sources {
  registry: CompanyLookup | null;
  fns: FnsProfile;
  /** null — БКИ не ответило после 2 повторов (R3). */
  bki: BkiReport | null;
}

const CLEAN = { mass_address: false, unreliable_address: false, unreliable_director: false };
const NO_HISTORY: BkiReport = { report_id: 'bki-none', has_history: false, bankruptcy: false, loans: [], inquiries_30d: 0 };

const FIXTURES: Record<string, { fns: FnsProfile; bki: BkiReport | null }> = {
  // ООО «Пекарня Север»: всё чисто, выручка +12% к прошлому году.
  '7701000019': {
    fns: { revenue: { '2024': 21_428_571, '2025': 24_000_000 }, tax_debt_rub: 0, msp_category: 'small', employees: 38, flags: CLEAN },
    bki: {
      report_id: 'bki-7701000019',
      has_history: true,
      bankruptcy: false,
      loans: [{ type: 'loan', balance: 1_800_000, monthly_payment: 150_000, max_overdue_days_24m: 0, current_overdue_days: 0 }],
      inquiries_30d: 1,
    },
  },
  // ИП Ковалёв: одна просрочка до 30 дней, выручка +5%.
  '500100001072': {
    fns: { revenue: { '2024': 5_714_286, '2025': 6_000_000 }, tax_debt_rub: 0, msp_category: 'micro', employees: 4, flags: CLEAN },
    bki: {
      report_id: 'bki-500100001072',
      has_history: true,
      bankruptcy: false,
      loans: [{ type: 'credit_card', balance: 640_000, monthly_payment: 60_000, max_overdue_days_24m: 12, current_overdue_days: 0 }],
      inquiries_30d: 2,
    },
  },
  // ИП Мельникова: работает с 2024 года — выручки за прошлый год нет; кредитной истории нет.
  '500100002020': {
    fns: { revenue: { '2025': 7_000_000 }, tax_debt_rub: 0, msp_category: 'micro', employees: 2, flags: CLEAN },
    bki: NO_HISTORY,
  },
  // ООО «СтройРесурс»: ликвидирована (R1), выручка упала, есть долг по налогам.
  '7701000026': {
    fns: {
      revenue: { '2024': 31_000_000, '2025': 9_000_000 },
      tax_debt_rub: 1_240_000,
      msp_category: 'small',
      employees: 0,
      flags: { mass_address: true, unreliable_address: false, unreliable_director: false },
    },
    bki: {
      report_id: 'bki-7701000026',
      has_history: true,
      bankruptcy: false,
      loans: [{ type: 'loan', balance: 4_200_000, monthly_payment: 310_000, max_overdue_days_24m: 45, current_overdue_days: 0 }],
      inquiries_30d: 3,
    },
  },
  // ООО «Вектор»: текущая просрочка 120 дней (R2).
  '7701000033': {
    fns: { revenue: { '2024': 15_000_000, '2025': 16_000_000 }, tax_debt_rub: 0, msp_category: 'small', employees: 21, flags: CLEAN },
    bki: {
      report_id: 'bki-7701000033',
      has_history: true,
      bankruptcy: false,
      loans: [{ type: 'loan', balance: 2_100_000, monthly_payment: 95_000, max_overdue_days_24m: 120, current_overdue_days: 120 }],
      inquiries_30d: 4,
    },
  },
  // ООО «Мираж»: 2 флага ФНС, долг 250 тыс ₽, выручка −25%, просрочка 30–90 дней → грейд D (R7).
  '7701000058': {
    fns: {
      revenue: { '2024': 12_000_000, '2025': 9_000_000 },
      tax_debt_rub: 250_000,
      msp_category: 'small',
      employees: 15,
      flags: { mass_address: true, unreliable_address: false, unreliable_director: true },
    },
    bki: {
      report_id: 'bki-7701000058',
      has_history: true,
      bankruptcy: false,
      loans: [{ type: 'loan', balance: 1_400_000, monthly_payment: 120_000, max_overdue_days_24m: 52, current_overdue_days: 0 }],
      inquiries_30d: 5,
    },
  },
  // ООО «Сбой-Тест»: БКИ всегда отвечает 503 (R3).
  '7701000065': {
    fns: { revenue: { '2024': 16_000_000, '2025': 17_000_000 }, tax_debt_rub: 0, msp_category: 'small', employees: 12, flags: CLEAN },
    bki: null,
  },
};

export function sourcesFor(inn: string): Sources {
  const fixture = FIXTURES[inn];
  return {
    registry: registry.find((r) => r.inn === inn) ?? null,
    fns: fixture?.fns ?? { revenue: {}, tax_debt_rub: 0, msp_category: 'micro', employees: 0, flags: CLEAN },
    bki: fixture ? fixture.bki : NO_HISTORY,
  };
}

/** Ответ ЕГРЮЛ или ЕГРИП в формате источника (план, раздел 8), а не в едином виде lookup. */
export function rawRegistry(company: CompanyLookup): Record<string, unknown> {
  if (company.kind === 'IE') {
    const { inn, ogrn, name, status, registered_at, okved_main, region } = company;
    return { inn, ogrnip: ogrn, fio: name, status, registered_at, okved_main, region };
  }
  const { inn, ogrn, name, status, registered_at, okved_main, okved_extra, address, region, director_fio } = company;
  return { inn, ogrn, name, status, registered_at, okved_main, okved_extra, director: { fio: director_fio }, address, region };
}
