import type { ApplicationSummary } from '../../api/types';
import { STATUS_UI, type HomeBlock } from '../../i18n/ru';

export type HomeGroups = Record<HomeBlock, ApplicationSummary[]>;

const byChangedDesc = (a: ApplicationSummary, b: ApplicationSummary) =>
  b.status_changed_at.localeCompare(a.status_changed_at);

export function groupForHome(items: ApplicationSummary[]): HomeGroups {
  const groups: HomeGroups = { action: [], bank: [], done: [] };
  for (const app of items) groups[STATUS_UI[app.status].block].push(app);
  groups.action.sort(byChangedDesc);
  groups.bank.sort(byChangedDesc);
  groups.done.sort(byChangedDesc);
  return groups;
}
