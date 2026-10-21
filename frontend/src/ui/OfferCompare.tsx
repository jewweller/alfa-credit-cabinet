import styles from './OfferCompare.module.css';

export interface CompareRow {
  label: string;
  requested: string;
  offered: string;
}

/** «Просили / предлагаем»: изменённые условия подсвечены. */
export function OfferCompare({
  requestedLabel,
  offeredLabel,
  rows,
}: {
  requestedLabel: string;
  offeredLabel: string;
  rows: CompareRow[];
}) {
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th scope="col" className={styles.rowHead} />
          <th scope="col">{requestedLabel}</th>
          <th scope="col" className={styles.offeredHead}>
            {offeredLabel}
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const changed = row.requested !== row.offered;
          return (
            <tr key={row.label} className={changed ? styles.changed : ''}>
              <th scope="row" className={styles.rowHead}>
                {row.label}
              </th>
              <td className={styles.requested}>{row.requested}</td>
              <td className={styles.offered}>
                {row.offered}
                {changed && <span className={styles.mark} aria-hidden="true" />}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
