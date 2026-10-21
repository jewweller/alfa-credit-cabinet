import type { ApplicationSummary, Product } from '../../api/types';
import { HOME, MONEY, STAGE_LABELS, STAGES, STATUS_UI } from '../../i18n/ru';
import type { ApplicationCardProps } from '../../ui/ApplicationCard';
import { formatMoney, formatTerm, timeAgo } from '../format';
import { screenPath } from '../routes';

/** Заявка → пропсы карточки. Вся логика по статусам живёт в STATUS_UI. */
export function toCardView(
  app: ApplicationSummary,
  now: number,
  products: Map<string, Product>,
  index = 0,
): ApplicationCardProps {
  const ui = STATUS_UI[app.status];
  return {
    eyebrow: HOME.cardEyebrow(app.number),
    title: (app.product_id && products.get(app.product_id)?.name) || MONEY.noProduct,
    amount: formatMoney(app.amount),
    term: formatTerm(app.term_months),
    badge: { label: ui.badge, tone: ui.tone },
    progress: ui.stage
      ? {
          labels: STAGES.map((s) => STAGE_LABELS[s]),
          current: STAGES.indexOf(ui.stage),
          state: ui.stageState,
        }
      : null,
    nextLabel: HOME.nextLabel,
    next: ui.next(app),
    hint: ui.block === 'bank' ? HOME.bankHint : null,
    updated: HOME.statusChanged(timeAgo(app.status_changed_at, now)),
    action: {
      label: ui.cta.label,
      to: screenPath(ui.cta.screen, app.id),
      variant: ui.block === 'action' ? 'primary' : 'secondary',
    },
    index,
  };
}
