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
export type UserRole = Schemas['UserRole'];
export type LoginRequest = Schemas['LoginRequest'];
export type TokenResponse = Schemas['TokenResponse'];
export type CompanyLookup = Schemas['CompanyLookupResponse'];
export type CompanyRegistryStatus = Schemas['CompanyRegistryStatus'];
export type ProductRecommendRequest = Schemas['ProductRecommendRequest'];
export type ProductRecommendation = Schemas['ProductRecommendation'];
export type RecommendationAdjustment = Schemas['RecommendationAdjustment'];
export type ApplicationCreate = Schemas['ApplicationCreate'];
export type ApplicationUpdate = Schemas['ApplicationUpdate'];
export type SigningCode = Schemas['SigningCodeResponse'];
export type SigningConfirmRequest = Schemas['SigningConfirmRequest'];
export type Grade = Schemas['Grade'];
export type Employee = Schemas['Employee'];
export type BankApplicationSummary = Schemas['BankApplicationSummary'];
export type BankApplicationDetail = Schemas['BankApplicationDetail'];
export type BankDecision = Schemas['BankDecision'];
export type EnrichmentResult = Schemas['EnrichmentResult'];
export type EnrichmentSource = Schemas['EnrichmentSource'];
export type ScoringResult = Schemas['ScoringResult'];
export type ScoringFactor = Schemas['ScoringFactor'];
export type RuleCheck = Schemas['RuleCheck'];
export type UnderwriterOutcome = Schemas['UnderwriterOutcome'];
export type UnderwriterDecisionRequest = Schemas['UnderwriterDecisionRequest'];
export type CompanyBrief = Schemas['CompanyBrief'];
export type AuditEntry = Schemas['AuditEntry'];
export type AuditAction = Schemas['AuditAction'];
export type AuditActorRole = Schemas['AuditActorRole'];
export type DemoResetResult = Schemas['DemoResetResult'];
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
