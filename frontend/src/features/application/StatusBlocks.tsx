import type { ApplicationDetail, ApplicationStatus } from '../../api/types';
import { APPLICATION } from '../../i18n/ru';
import { ButtonLink, MetaNote, Panel, StepList, type StepItem } from '../../ui';
import { formatDate } from '../format';
import { ROUTES, screenPath } from '../routes';

/** Конвейер работает: что уже сделано и что делается сейчас. */
export function WaitingBlock({ status }: { status: ApplicationStatus }) {
  const W = APPLICATION.waiting;
  // Индекс текущего шага: SUBMITTED/ENRICHMENT — сверка, SCORING — оценка.
  const current = status === 'SCORING' ? 1 : 0;
  const items: StepItem[] = W.steps.map((step, i) => ({
    title: step.title,
    state: i < current ? 'done' : i === current ? 'current' : 'todo',
  }));
  return (
    <Panel tone="highlight" eyebrow={W.eyebrow} title={APPLICATION.title[status]}>
      <StepList items={items} />
      <MetaNote>{W.hint}</MetaNote>
    </Panel>
  );
}

export function ReviewBlock() {
  const R = APPLICATION.review;
  return (
    <Panel tone="highlight" eyebrow={R.eyebrow} title={APPLICATION.title.MANUAL_REVIEW}>
      <StepList
        items={[
          { title: APPLICATION.waiting.steps[0].title, state: 'done' },
          { title: APPLICATION.waiting.steps[1].title, state: 'done' },
          { title: R.text, state: 'current' },
        ]}
      />
    </Panel>
  );
}

/** Отказ: причина простыми словами и что можно сделать. Баллы и правила не показываем. */
export function RejectionBlock({ app }: { app: ApplicationDetail }) {
  const R = APPLICATION.rejection;
  const code = app.decision?.reason_code;
  const reason = code ? R.reasons[code] : R.fallback;
  return (
    <Panel
      tone="danger"
      eyebrow={R.eyebrow}
      title={reason.title}
      footer={
        <ButtonLink to={ROUTES.products} arrow>
          {R.pick}
        </ButtonLink>
      }
    >
      <p>{reason.text}</p>
      <MetaNote>{R.whatToDo}</MetaNote>
      <StepList items={reason.steps.map((title) => ({ title, state: 'note' as const }))} />
      {app.decision && (
        <MetaNote>{APPLICATION.offer.decidedBy(app.decision.decided_by, formatDate(app.decision.decided_at))}</MetaNote>
      )}
    </Panel>
  );
}

/** Черновик, подписание, выдача, отказ клиента, отзыв — короткий блок с одной кнопкой. */
export function NextStepBlock({ app }: { app: ApplicationDetail }) {
  const F = APPLICATION.final;
  const action: Partial<Record<ApplicationStatus, { label: string; to: string; primary: boolean }>> = {
    DRAFT: { label: F.draft, to: screenPath('C4', app.id), primary: true },
    SIGNING: { label: F.sign, to: screenPath('C6', app.id), primary: true },
    ISSUED: { label: F.schedule, to: screenPath('C7', app.id), primary: false },
    DECLINED_BY_CLIENT: { label: F.pick, to: ROUTES.products, primary: false },
    CANCELLED: { label: F.pick, to: ROUTES.products, primary: false },
  };
  const next = action[app.status];
  const tone = app.status === 'ISSUED' ? 'success' : app.status === 'SIGNING' || app.status === 'DRAFT' ? 'highlight' : 'default';
  return (
    <Panel
      tone={tone}
      title={APPLICATION.title[app.status]}
      footer={
        next ? (
          <ButtonLink to={next.to} variant={next.primary ? 'primary' : 'secondary'} size="lg" arrow>
            {next.label}
          </ButtonLink>
        ) : undefined
      }
    >
      <p>{app.status === 'SIGNED' ? F.signedText : APPLICATION.subtitle[app.status]}</p>
    </Panel>
  );
}
