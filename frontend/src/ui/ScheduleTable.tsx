import { useState } from 'react';
import styles from './ScheduleTable.module.css';

export interface ScheduleRow {
  number: number;
  date: string;
  payment: string;
  principal: string;
  interest: string;
  balance: string;
}

export interface ScheduleTableProps {
  columns: { number: string; date: string; payment: string; principal: string; interest: string; balance: string };
  rows: ScheduleRow[];
  /** Сколько строк показывать до «Показать весь график». */
  preview?: number;
  showAllLabel: (count: number) => string;
  collapseLabel: string;
}

export function ScheduleTable({ columns, rows, preview = 3, showAllLabel, collapseLabel }: ScheduleTableProps) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? rows : rows.slice(0, preview);
  return (
    <div className={styles.wrap}>
      <div className={styles.scroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">{columns.number}</th>
              <th scope="col">{columns.date}</th>
              <th scope="col" className={styles.num}>
                {columns.payment}
              </th>
              <th scope="col" className={`${styles.num} ${styles.optional}`}>
                {columns.principal}
              </th>
              <th scope="col" className={`${styles.num} ${styles.optional}`}>
                {columns.interest}
              </th>
              <th scope="col" className={`${styles.num} ${styles.secondary}`}>
                {columns.balance}
              </th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.number}>
                <td className={styles.mono}>{String(row.number).padStart(2, '0')}</td>
                <td>{row.date}</td>
                <td className={`${styles.num} ${styles.strong}`}>{row.payment}</td>
                <td className={`${styles.num} ${styles.optional}`}>{row.principal}</td>
                <td className={`${styles.num} ${styles.optional}`}>{row.interest}</td>
                <td className={`${styles.num} ${styles.muted} ${styles.secondary}`}>{row.balance}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > preview && (
        <button type="button" className={styles.toggle} onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}>
          {expanded ? collapseLabel : showAllLabel(rows.length)}
        </button>
      )}
    </div>
  );
}
