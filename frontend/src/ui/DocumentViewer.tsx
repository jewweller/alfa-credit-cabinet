import { useEffect, useRef, type ReactNode } from 'react';
import styles from './DocumentViewer.module.css';
import { PdfView } from './PdfView';

export type DocumentViewerKind = 'pdf' | 'image' | 'other';

interface DocumentViewerProps {
  open: boolean;
  title: string;
  meta: string;
  kind: DocumentViewerKind;
  /** Ссылка на файл; null — ещё грузится или не получилось. */
  src: string | null;
  /** Что показать вместо файла: загрузка, ошибка, неподдерживаемый формат. */
  placeholder: ReactNode;
  /** PDF не удалось показать на странице. */
  pdfError: ReactNode;
  /** Подпись страницы PDF для чтения с экрана. */
  pageLabel: (page: number, total: number) => string;
  actions: ReactNode;
  closeLabel: string;
  onClose: () => void;
}

/**
 * Просмотр файла во всплывающем окне: PDF — страницами через pdf.js, картинка — как есть.
 * Нативный <dialog>: фокус внутри окна, Esc и клик по фону закрывают.
 */
export function DocumentViewer({ open, title, meta, kind, src, placeholder, pdfError, pageLabel, actions, closeLabel, onClose }: DocumentViewerProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={styles.dialog}
      aria-label={title}
      onClose={onClose}
      onClick={(event) => event.target === ref.current && onClose()}
    >
      {open && (
        <div className={styles.frame}>
          <header className={styles.head}>
            <span className={styles.titles}>
              <span className={styles.title}>{title}</span>
              <span className={styles.meta}>{meta}</span>
            </span>
            <span className={styles.actions}>
              {actions}
              <button type="button" className={styles.close} onClick={onClose} aria-label={closeLabel}>
                ×
              </button>
            </span>
          </header>
          <div className={styles.body}>
            {src && kind === 'pdf' && <PdfView src={src} loading={placeholder} error={pdfError} pageLabel={pageLabel} />}
            {src && kind === 'image' && <img className={styles.image} src={src} alt={title} />}
            {(!src || kind === 'other') && <div className={styles.placeholder}>{placeholder}</div>}
          </div>
        </div>
      )}
    </dialog>
  );
}
