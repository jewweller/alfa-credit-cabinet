import { Button } from './Button';
import styles from './FileList.module.css';

export interface FileListAction {
  label: string;
  onClick: () => void;
}

export interface FileListItem {
  id: string;
  name: string;
  meta: string;
  actions: FileListAction[];
}

/** Список файлов: имя, подпись (вид и размер) и действия справа, например «Открыть» и «Скачать». */
export function FileList({ items }: { items: FileListItem[] }) {
  return (
    <ul className={styles.list}>
      {items.map((item) => (
        <li key={item.id} className={styles.item}>
          <span className={styles.text}>
            <span className={styles.name}>{item.name}</span>
            <span className={styles.meta}>{item.meta}</span>
          </span>
          <span className={styles.actions}>
            {item.actions.map((action) => (
              <Button key={action.label} variant="ghost" onClick={action.onClick}>
                {action.label}
              </Button>
            ))}
          </span>
        </li>
      ))}
    </ul>
  );
}
