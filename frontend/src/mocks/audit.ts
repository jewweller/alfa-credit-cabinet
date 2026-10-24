// Журнал действий в моках (таблица audit_log на бэке). Строки только дописываются,
// сброс демо их не трогает — как в контракте `POST /admin/demo/reset`.
import type { AuditAction, AuditActorRole, AuditEntry, Me } from '../api/types';
import { users, type MockApplication } from './data';

export interface Actor {
  role: AuditActorRole;
  id: string | null;
  name: string | null;
}

export const SYSTEM: Actor = { role: 'system', id: null, name: null };

export const staff = (user: Me): Actor => ({ role: user.role, id: user.id, name: user.full_name });

/** Клиент — владелец заявки (одна учётка на компанию). */
export function owner(app: MockApplication): Actor {
  const user = users.find((u) => u.company?.id === app.detail.company_id);
  return user ? staff(user) : { role: 'client', id: null, name: null };
}

const IP: Record<AuditActorRole, string | null> = {
  client: '172.18.0.1',
  underwriter: '172.18.0.1',
  admin: '172.18.0.1',
  system: null,
};

export function entry(
  action: AuditAction,
  actor: Actor,
  app: MockApplication | null,
  summary: string,
  details: Record<string, unknown> = {},
  at = new Date().toISOString(),
): AuditEntry {
  return {
    id: crypto.randomUUID(),
    created_at: at,
    action,
    actor_role: actor.role,
    actor_id: actor.id,
    actor_name: actor.name,
    application_id: app?.detail.id ?? null,
    application_number: app?.detail.number ?? null,
    summary,
    details,
    ip: IP[actor.role],
  };
}

/** Журнал для исходных заявок — из их истории статусов. */
export function seedAudit(apps: MockApplication[]): AuditEntry[] {
  const result: AuditEntry[] = [];
  for (const app of apps) {
    for (const h of app.history) {
      const change = { from_status: h.from_status, to_status: h.to_status };
      const summary = h.from_status ? `${h.from_status} → ${h.to_status}` : h.to_status;
      if (h.from_status === null) {
        result.push(entry('application.created', owner(app), app, summary, change, h.created_at));
      } else if (h.actor_type === 'client') {
        const action = h.to_status === 'SUBMITTED' ? 'application.submitted' : h.to_status === 'SIGNING' ? 'offer.accepted' : 'application.cancelled';
        result.push(entry(action, owner(app), app, summary, change, h.created_at));
      } else if (h.actor_type === 'underwriter') {
        const who = app.review?.underwriter;
        const actor: Actor = { role: 'underwriter', id: who?.id ?? null, name: who?.full_name ?? null };
        result.push(entry('bank.decision', actor, app, summary, change, h.created_at));
      } else {
        result.push(entry(h.to_status === 'ISSUED' ? 'loan.issued' : 'application.status_changed', SYSTEM, app, summary, change, h.created_at));
      }
    }
  }
  return newestFirst(result);
}

export const newestFirst = (entries: AuditEntry[]) => [...entries].sort((a, b) => b.created_at.localeCompare(a.created_at));

export interface AuditFilter {
  applicationId: string | null;
  actions: string[];
  actorRole: string | null;
  before: string | null;
  limit: number;
}

export function filterAudit(entries: AuditEntry[], f: AuditFilter): AuditEntry[] {
  return entries
    .filter(
      (e) =>
        (!f.applicationId || e.application_id === f.applicationId) &&
        (f.actions.length === 0 || f.actions.includes(e.action)) &&
        (!f.actorRole || e.actor_role === f.actorRole) &&
        (!f.before || e.created_at < f.before),
    )
    .slice(0, f.limit);
}
