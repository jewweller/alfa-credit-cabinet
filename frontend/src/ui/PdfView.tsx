import { useEffect, useRef, useState, type ReactNode } from 'react';
import styles from './PdfView.module.css';

type Pdfjs = typeof import('pdfjs-dist/legacy/build/pdf.mjs');

let pdfjs: Promise<Pdfjs> | null = null;

/** pdf.js грузим только при первом просмотре: клиентам он не нужен. Legacy-сборка — для Safari постарше. */
function loadPdfjs(): Promise<Pdfjs> {
  pdfjs ??= Promise.all([
    import('pdfjs-dist/legacy/build/pdf.mjs'),
    import('pdfjs-dist/legacy/build/pdf.worker.min.mjs?worker'),
  ]).then(([lib, { default: PdfWorker }]) => {
    lib.GlobalWorkerOptions.workerPort = new PdfWorker();
    return lib;
  });
  pdfjs.catch(() => (pdfjs = null));
  return pdfjs;
}

interface PdfViewProps {
  /** Ссылка на PDF (blob:). */
  src: string;
  loading: ReactNode;
  error: ReactNode;
  pageLabel: (page: number, total: number) => string;
}

/**
 * PDF страницами на canvas через pdf.js. Встроенный просмотрщик браузера в iframe есть не везде:
 * в Safari на iPhone и iPad и при выключенном просмотре PDF окно оставалось пустым.
 */
export function PdfView({ src, loading, error, pageLabel }: PdfViewProps) {
  const pagesRef = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  // Подпись страниц не должна перерисовывать документ: карточка банка обновляется каждые 3 секунды.
  const labelRef = useRef(pageLabel);
  labelRef.current = pageLabel;

  useEffect(() => {
    const box = pagesRef.current;
    if (!box) return;
    let cancelled = false;
    let destroy: (() => void) | undefined;
    setState('loading');

    (async () => {
      const lib = await loadPdfjs();
      if (cancelled) return;
      const task = lib.getDocument({ url: src });
      destroy = () => void task.destroy();
      const pdf = await task.promise;
      const ratio = window.devicePixelRatio || 1;
      for (let n = 1; n <= pdf.numPages && !cancelled; n++) {
        const page = await pdf.getPage(n);
        const width = Math.max(box.clientWidth, 280);
        const viewport = page.getViewport({ scale: width / page.getViewport({ scale: 1 }).width });
        const canvas = document.createElement('canvas');
        canvas.className = styles.page;
        canvas.width = Math.floor(viewport.width * ratio);
        canvas.height = Math.floor(viewport.height * ratio);
        canvas.setAttribute('role', 'img');
        canvas.setAttribute('aria-label', labelRef.current(n, pdf.numPages));
        box.append(canvas);
        await page.render({ canvas, viewport, transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0] }).promise;
        if (n === 1 && !cancelled) setState('ready');
      }
    })().catch(() => !cancelled && setState('error'));

    return () => {
      cancelled = true;
      destroy?.();
      box.replaceChildren();
    };
  }, [src]);

  return (
    <div className={styles.scroll}>
      {state !== 'ready' && <div className={styles.status}>{state === 'error' ? error : loading}</div>}
      <div ref={pagesRef} className={styles.pages} hidden={state === 'error'} />
    </div>
  );
}
