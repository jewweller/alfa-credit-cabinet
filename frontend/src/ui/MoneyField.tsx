import { TextField, type TextFieldProps } from './TextField';

const grouped = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 });

/** "3000000.00" → «3 000 000». */
function display(value: string | null): string {
  if (value === null || value === '') return '';
  return grouped.format(Math.trunc(Number(value)));
}

/** Ввод → "3000000.00"; пусто → null. Копейки в анкете не нужны — только рубли. */
function parse(text: string): string | null {
  const digits = text.replace(/\D/g, '').replace(/^0+(?=\d)/, '').slice(0, 12);
  return digits ? `${digits}.00` : null;
}

export interface MoneyFieldProps extends Omit<TextFieldProps, 'value' | 'onChange' | 'suffix' | 'inputMode'> {
  /** Сумма как в контракте: строкой "3000000.00" или null. */
  value: string | null;
  onChange: (value: string | null) => void;
}

/** Сумма в рублях с разбивкой на разряды при вводе. */
export function MoneyField({ value, onChange, ...rest }: MoneyFieldProps) {
  return (
    <TextField
      {...rest}
      inputMode="numeric"
      autoComplete="off"
      suffix="₽"
      value={display(value)}
      onChange={(e) => onChange(parse(e.target.value))}
    />
  );
}
