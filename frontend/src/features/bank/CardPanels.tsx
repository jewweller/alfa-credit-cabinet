import type {
  ApplicationDetail,
  BankDecision,
  EnrichmentResult,
  Product,
  RuleCheck,
  ScoringResult,
} from '../../api/types';
import { APPLICATION, BANK, MONEY } from '../../i18n/ru';
import { Button, Collapsible, KeyValueList, Meter, MetaNote, Panel, StatusBadge, type KeyValue } from '../../ui';
import { downloadDocument } from '../application/download';
import { formatBytes, formatDate, formatDateTime, formatMoney, formatPercent, formatRate, formatTerm } from '../format';
import { GRADE_TONE } from './format';
import styles from './CardPanels.module.css';

const SAFE_LOAD = 0.35;

/** Скоринг: грейд, нагрузка и факторы F1–F6 с баллами. */
export function ScoringPanel({ scoring, index = 0 }: { scoring: ScoringResult | null; index?: number }) {
  const S = BANK.scoring;
  if (!scoring) {
    return (
      <Panel eyebrow={S.eyebrow} index={index}>
        <MetaNote>{S.pending}</MetaNote>
      </Panel>
    );
  }
  return (
    <Panel
      eyebrow={S.eyebrow}
      title={S.title(scoring.grade, scoring.total_score)}
      aside={<StatusBadge label={scoring.grade} tone={GRADE_TONE[scoring.grade]} />}
      index={index}
    >
      <Meter
        label={S.load}
        valueLabel={formatPercent(scoring.debt_load)}
        value={scoring.debt_load}
        threshold={SAFE_LOAD}
        thresholdLabel={S.threshold}
        note={S.loadNote}
      />
      <ul className={styles.factors}>
        {scoring.factors.map((factor) => (
          <li key={factor.code} className={styles.factor}>
            <span className={styles.code}>{factor.code}</span>
            <span className={styles.factorText}>
              <span className={styles.factorTitle}>{factor.title}</span>
              <span className={styles.factorValue}>{factor.value}</span>
            </span>
            <span className={styles.points}>
              <span className={styles.pointsValue}>
                {factor.points}
                <span className={styles.pointsMax}>/{factor.max_points}</span>
              </span>
              <span className={styles.bar} aria-hidden="true">
                <span className={styles.barFill} style={{ width: `${(factor.points / factor.max_points) * 100}%` }} />
              </span>
            </span>
          </li>
        ))}
      </ul>
      <MetaNote>{S.model(scoring.model_version)}</MetaNote>
    </Panel>
  );
}

/** Правила R1–R10 по порядку до сработавшего. */
export function RulesPanel({ rules, index = 0 }: { rules: RuleCheck[]; index?: number }) {
  const R = BANK.rules;
  if (rules.length === 0) return null;
  return (
    <Panel eyebrow={R.eyebrow} title={R.title} index={index}>
      <ol className={styles.rules}>
        {rules.map((rule) => (
          <li key={rule.code} className={`${styles.rule} ${rule.fired ? styles.fired : ''}`}>
            <span className={styles.code}>{rule.code}</span>
            <span className={styles.ruleText}>
              <span className={styles.ruleTitle}>{rule.title}</span>
              {rule.detail && <span className={styles.ruleDetail}>{rule.detail}</span>}
            </span>
            <span className={styles.ruleState}>{rule.fired ? R.fired : R.passed}</span>
          </li>
        ))}
      </ol>
      <MetaNote>{R.note}</MetaNote>
    </Panel>
  );
}

type Raw = Record<string, unknown>;
const num = (value: unknown) => (typeof value === 'number' ? value : 0);

/** Главное из ответа источника — понятными словами; всё остальное — в сыром JSON. */
function sourceFacts(result: EnrichmentResult): KeyValue[] {
  const F = BANK.sources.fields;
  const S = BANK.sources;
  const raw = (result.response ?? {}) as Raw;
  if (!result.response) return [];
  switch (result.source) {
    case 'egrul':
    case 'egrip': {
      const director = (raw.director as Raw | undefined)?.fio;
      return [
        { label: F.status, value: String(raw.status ?? '—') },
        { label: F.registered, value: raw.registered_at ? formatDate(String(raw.registered_at)) : '—' },
        { label: F.okved, value: String(raw.okved_main ?? '—') },
        ...(director ? [{ label: F.director, value: String(director) }] : []),
      ];
    }
    case 'fns_tb': {
      const revenue = (raw.revenue ?? {}) as Record<string, number>;
      const flags = Object.entries((raw.flags ?? {}) as Record<string, boolean>).filter(([, on]) => on).length;
      return [
        ...Object.keys(revenue)
          .sort()
          .map((year) => ({ label: F.revenue(year), value: formatMoney(revenue[year]) })),
        { label: F.taxDebt, value: num(raw.tax_debt_rub) ? formatMoney(num(raw.tax_debt_rub)) : S.no },
        { label: F.employees, value: String(raw.employees ?? '—') },
        { label: F.flags, value: flags ? String(flags) : S.no },
      ];
    }
    case 'bki': {
      const loans = (raw.loans ?? []) as Raw[];
      return [
        { label: F.history, value: raw.has_history ? S.yes : S.no },
        { label: F.loans, value: String(loans.length) },
        { label: F.payments, value: formatMoney(loans.reduce((sum, l) => sum + num(l.monthly_payment), 0)) },
        { label: F.overdue, value: S.days(Math.max(0, ...loans.map((l) => num(l.max_overdue_days_24m)))) },
        { label: F.inquiries, value: String(raw.inquiries_30d ?? 0) },
      ];
    }
  }
}

const SOURCE_TONE = { ok: 'success', not_found: 'neutral', error: 'danger' } as const;

/** Ответы ЕГРЮЛ/ЕГРИП, ФНС и БКИ: главное и сырой JSON. */
export function SourcesPanel({ enrichment, index = 0 }: { enrichment: EnrichmentResult[]; index?: number }) {
  const S = BANK.sources;
  return (
    <Panel eyebrow={S.eyebrow} title={S.title} index={index}>
      {enrichment.length === 0 && <MetaNote>{S.pending}</MetaNote>}
      {enrichment.map((result) => (
        <section key={result.source} className={styles.source}>
          <div className={styles.sourceHead}>
            <h3 className={styles.sourceName}>{S.names[result.source]}</h3>
            <StatusBadge label={S.status[result.status]} tone={SOURCE_TONE[result.status]} />
          </div>
          <MetaNote>{`${formatDateTime(result.fetched_at)} · ${S.attempts(result.attempts)}`}</MetaNote>
          {result.response && (
            <>
              <KeyValueList columns={2} items={sourceFacts(result)} />
              <Collapsible title={S.raw} onSurface>
                <pre className={styles.json}>{JSON.stringify(result.response, null, 2)}</pre>
              </Collapsible>
            </>
          )}
        </section>
      ))}
    </Panel>
  );
}

/** Анкета клиента, как он её отправил. */
export function FactsPanel({ app, products, index = 0 }: { app: ApplicationDetail; products: Map<string, Product>; index?: number }) {
  const F = BANK.facts;
  const items: KeyValue[] = [
    { label: F.product, value: (app.product_id && products.get(app.product_id)?.name) || MONEY.noProduct },
    { label: F.amount, value: formatMoney(app.amount) },
    { label: F.term, value: formatTerm(app.term_months) },
    { label: F.purpose, value: app.purpose ? APPLICATION.purpose[app.purpose] : '—' },
    { label: F.revenue, value: formatMoney(app.revenue_12m) },
    { label: F.payments, value: formatMoney(app.existing_payments_monthly) },
    { label: F.consent, value: app.bki_consent ? F.yes : F.no },
    ...(app.submitted_at ? [{ label: F.submitted, value: formatDateTime(app.submitted_at) }] : []),
  ];
  return (
    <Panel title={F.title} index={index}>
      <KeyValueList items={items} />
    </Panel>
  );
}

/** Файлы, которые загрузил клиент. */
export function DocumentsPanel({ app, index = 0 }: { app: ApplicationDetail; index?: number }) {
  const D = BANK.documents;
  return (
    <Panel title={D.title} index={index}>
      {app.documents.length === 0 ? (
        <MetaNote>{D.empty}</MetaNote>
      ) : (
        <ul className={styles.docs}>
          {app.documents.map((doc) => (
            <li key={doc.id} className={styles.doc}>
              <span className={styles.docText}>
                <span className={styles.docName}>{doc.filename}</span>
                <span className={styles.docMeta}>
                  {`${APPLICATION.documentKind[doc.kind]} · ${formatBytes(doc.size_bytes)}`}
                </span>
              </span>
              <Button variant="ghost" onClick={() => void downloadDocument(doc.id, doc.filename)}>
                {D.download}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/** Принятое решение: кто, когда, условия или причина, комментарий специалиста. */
export function DecisionResultPanel({
  decision,
  app,
  products,
  index = 0,
}: {
  decision: BankDecision;
  app: ApplicationDetail;
  products: Map<string, Product>;
  index?: number;
}) {
  const R = BANK.result;
  const offer = app.active_offer;
  const who = decision.underwriter?.full_name ?? R.system;
  const tone = decision.outcome === 'rejected' ? 'danger' : decision.outcome === 'manual_review' ? 'default' : 'success';
  const items: KeyValue[] = [];
  if ((decision.outcome === 'approved' || decision.outcome === 'counter_offer') && offer) {
    items.push(
      { label: BANK.decision.product, value: products.get(offer.product_id)?.name ?? MONEY.noProduct },
      { label: BANK.decision.amount, value: formatMoney(offer.amount) },
      { label: BANK.decision.term, value: formatTerm(offer.term_months) },
      { label: BANK.decision.rate, value: formatRate(offer.rate) },
      { label: BANK.decision.payment, value: formatMoney(offer.monthly_payment) },
    );
  }
  if (decision.outcome === 'rejected' && decision.reason_code) {
    items.push({ label: R.reason, value: BANK.decision.reasons[decision.reason_code].title });
  }
  return (
    <Panel tone={tone} eyebrow={R.eyebrow} title={R.outcomes[decision.outcome]} index={index}>
      <MetaNote>{R.by(who, formatDateTime(decision.decided_at))}</MetaNote>
      {items.length > 0 && <KeyValueList items={items} />}
      {decision.outcome === 'info_requested' && app.info_request && (
        <>
          <ul className={styles.requested}>
            {app.info_request.items.map((item) => (
              <li key={item.kind}>{item.title}</li>
            ))}
          </ul>
          {app.info_request.message && <p className={styles.quote}>{app.info_request.message}</p>}
        </>
      )}
      {decision.comment && <KeyValueList items={[{ label: R.comment, value: decision.comment }]} />}
    </Panel>
  );
}
