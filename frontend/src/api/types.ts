// Типы API. Всё, что есть в контракте бэка, берём из сгенерированного schema.ts
// (npm run api:types). Руками описано только то, чего в контракте пока нет.
import type { components } from './schema';

type Schemas = components['schemas'];

export type ApplicationStatus = Schemas['ApplicationStatus'];
export type ApplicationSummary = Schemas['ApplicationSummary'];
export type ApplicationDetail = Schemas['ApplicationDetail'];
export type StatusHistoryEntry = Schemas['StatusHistoryEntry'];
export type StatusActor = Schemas['StatusActor'];
export type Offer = Schemas['Offer'];
export type ClientDecision = Schemas['ClientDecision'];
export type RejectReason = Schemas['RejectReason'];
export type InfoRequest = Schemas['InfoRequest'];
export type InfoRequestItem = Schemas['InfoRequestItem'];
export type DocumentInfo = Schemas['DocumentInfo'];
export type DocumentKind = Schemas['DocumentKind'];
export type PaymentSchedule = Schemas['PaymentSchedule'];
export type PaymentScheduleItem = Schemas['PaymentScheduleItem'];
export type Product = Schemas['Product'];
export type LoanPurpose = Schemas['LoanPurpose'];
export type Me = Schemas['MeResponse'];
export type ApiErrorBody = Schemas['ErrorResponse'];
export type ErrorCode = Schemas['ErrorCode'];

/** Строкой с двумя знаками: "3000000.00". */
export type Money = string;

/** Лента пока не описана в контракте (план: день 5) — тип держим здесь. */
export interface FeedItem {
  id: string;
  kind: 'event' | 'news';
  title: string;
  body: string;
  created_at: string;
  application_id?: string | null;
  reason?: string | null;
  read: boolean;
}
