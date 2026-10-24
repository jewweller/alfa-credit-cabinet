import type { CSSProperties, ReactNode } from 'react';
import { Link } from 'react-router';
import styles from './DataTable.module.css';

export interface DataColumn<T> {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  align?: 'start' | 'end';
  /** Ниже какой ширины самой таблицы колонку прятать: medium — 940px, small — 600px. */
  hideBelow?: 'medium' | 'small';
  tone?: 'mono' | 'muted' | 'strong';
  /** В ячейке свои кнопки — клик по ней не открывает строку. */
  interactive?: boolean;
}

const HIDE = { medium: styles.hideMedium, small: styles.hideSmall } as const;

/**
 * Таблица с кликабельными строками. Колонки прячутся по ширине самой таблицы (container queries),
 * поэтому она не прокручивается вбок ни в широкой, ни в узкой колонке страницы.
 */
export function DataTable<T>({
  rows,
  rowKey,
  columns,
  onRowClick,
  accent,
}: {
  rows: T[];
  rowKey: (row: T) => string;
  columns: DataColumn<T>[];
  onRowClick?: (row: T) => void;
  /** Строка, которая требует внимания: метка акцентом у первой ячейки. */
  accent?: (row: T) => boolean;
}) {
  const cls = (column: DataColumn<T>) =>
    [column.align === 'end' && styles.end, column.hideBelow && HIDE[column.hideBelow], column.tone && styles[column.tone]]
      .filter(Boolean)
      .join(' ');

  return (
    <div className={styles.wrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col" className={cls(column)}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={rowKey(row)}
              className={`${onRowClick ? styles.clickable : ''} ${accent?.(row) ? styles.accent : ''}`}
              style={{ '--i': Math.min(i, 12) } as CSSProperties}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cls(column)}
                  onClick={column.interactive ? (e) => e.stopPropagation() : undefined}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Главная ячейка строки: ссылка (или текст, если вести некуда), подпись под ней и то, что на узкой таблице заменяет спрятанные колонки. */
export function DataTableTitle({ to, title, meta, narrow }: { to?: string; title: string; meta?: string; narrow?: ReactNode }) {
  return (
    <>
      {to ? (
        <Link to={to} className={styles.title} onClick={(e) => e.stopPropagation()}>
          {title}
        </Link>
      ) : (
        <span className={styles.title}>{title}</span>
      )}
      {meta && <span className={styles.meta}>{meta}</span>}
      {narrow && <span className={styles.narrowOnly}>{narrow}</span>}
    </>
  );
}
