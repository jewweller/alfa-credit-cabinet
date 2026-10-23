import { useState } from 'react';
import type { ApplicationDetail, DocumentKind, InfoRequest } from '../../api/types';
import { ApiError } from '../../api/client';
import { APPLICATION } from '../../i18n/ru';
import { Button, ConfirmButton, DocumentItem, FileDrop, InlineAlert, Panel } from '../../ui';
import { formatBytes, formatDateTime } from '../format';
import { downloadDocument } from './download';
import { useApplicationActions } from './queries';

const T = APPLICATION.documents;
const ACCEPT = '.pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png';
const MAX_BYTES = 10 * 1024 * 1024;
const MIME = ['application/pdf', 'image/jpeg', 'image/png'];

/** Проверка до отправки: сразу понятная ошибка, без ожидания сервера. Сервер проверит ещё раз. */
function validate(file: File): string | null {
  if (file.size > MAX_BYTES) return T.tooLarge;
  if (!MIME.includes(file.type)) return T.wrongType;
  return null;
}

function uploadErrorText(error: Error): string {
  if (error instanceof ApiError) {
    if (error.body?.code === 'file_too_large') return T.tooLarge;
    if (error.body?.code === 'unsupported_media_type') return T.wrongType;
  }
  return error.message || APPLICATION.actionError;
}

/** «Банку нужны документы»: по пункту на документ, загрузка, повторная отправка. */
export function InfoRequestBlock({ app, request }: { app: ApplicationDetail; request: InfoRequest }) {
  const actions = useApplicationActions(app.id);
  const [uploadingKind, setUploadingKind] = useState<DocumentKind | null>(null);
  const [errors, setErrors] = useState<Partial<Record<DocumentKind, string>>>({});

  const filesFor = (kind: DocumentKind) =>
    app.documents.filter((doc) => doc.kind === kind && doc.info_request_id === request.id);
  const missingRequired = request.items.some((item) => item.required && filesFor(item.kind).length === 0);
  const busy = actions.resubmit.isPending || actions.cancel.isPending;
  const actionError = actions.resubmit.error ?? actions.cancel.error;

  const upload = (kind: DocumentKind, file: File) => {
    const problem = validate(file);
    setErrors((prev) => ({ ...prev, [kind]: problem ?? undefined }));
    if (problem) return;
    setUploadingKind(kind);
    actions.upload.mutate(
      { file, kind, infoRequestId: request.id },
      {
        onError: (error) => setErrors((prev) => ({ ...prev, [kind]: uploadErrorText(error) })),
        onSettled: () => setUploadingKind(null),
      },
    );
  };

  return (
    <Panel
      tone="highlight"
      eyebrow={`${T.eyebrow} · ${formatDateTime(request.created_at)}`}
      title={T.title}
      footer={
        <>
          <Button size="lg" arrow onClick={() => actions.resubmit.mutate()} disabled={missingRequired || busy}>
            {T.send}
          </Button>
          <ConfirmButton
            label={T.cancel}
            question={T.cancelQuestion}
            confirmLabel={T.cancelConfirm}
            cancelLabel={T.keep}
            busy={busy}
            onConfirm={() => actions.cancel.mutate()}
          />
        </>
      }
    >
      {request.message && <InlineAlert tone="info">{request.message}</InlineAlert>}

      {request.items.map((item, i) => {
        const files = filesFor(item.kind);
        return (
          <DocumentItem
            key={item.kind}
            index={i}
            title={item.title}
            tag={item.required ? T.required : T.optional}
            required={item.required}
            done={files.length > 0}
            doneLabel={T.uploaded}
            files={files.map((doc) => ({
              id: doc.id,
              name: doc.filename,
              meta: formatBytes(doc.size_bytes),
              onDownload: () => void downloadDocument(doc.id, doc.filename),
            }))}
          >
            <FileDrop
              label={T.drop}
              hint={T.hint}
              accept={ACCEPT}
              busy={uploadingKind === item.kind}
              busyLabel={T.uploading}
              error={errors[item.kind]}
              onFile={(file) => upload(item.kind, file)}
            />
          </DocumentItem>
        );
      })}

      {missingRequired && <InlineAlert tone="info">{T.sendHint}</InlineAlert>}
      {actionError && <InlineAlert>{actionError.message || APPLICATION.actionError}</InlineAlert>}
    </Panel>
  );
}
