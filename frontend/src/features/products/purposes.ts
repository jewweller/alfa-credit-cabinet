import type { LoanPurpose } from '../../api/types';
import { APPLICATION, PICK } from '../../i18n/ru';
import type { Choice } from '../../ui';

const PURPOSES: LoanPurpose[] = ['working_capital', 'equipment', 'cash_gap'];

/** Цели кредита карточками — на подборе (C3) и в мастере (C4). */
export const PURPOSE_CHOICES: Choice<LoanPurpose>[] = PURPOSES.map((p) => ({
  value: p,
  title: APPLICATION.purpose[p],
  description: PICK.purposeHint[p],
}));
