import { Button } from './Button';
import styles from './FileList.module.css';

export interface FileListItem {
  id: string;
  name: string;
  meta: string;
  onAction: () => void;
}

/** Список файлов: имя, подпись (вид и размер) и действие справа, например «Скачать». */
export function FileList({ items, actionLabel }: { items: FileListItem[]; actionLabel: string }) {
  return (
    <ul className={styles.list}>
      {items.map((item) => (
        <li key={item.id} className={styles.item}>
          <span className={styles.text}>
            <span className={styles.name}>{item.name}</span>
            <span className={styles.meta}>{item.meta}</span>
          </span>
          <Button variant="ghost" onClick={item.onAction}>
            {actionLabel}
          </Button>
        </li>
      ))}
    </ul>
  );
}
