"""Файлы клиента в заявке: загрузка в ответ на запрос банка и скачивание (план, разделы 4, 9).

Проверки: заявка в INFO_REQUESTED, до 10 МБ, PDF / JPG / PNG — и по заявленному типу,
и по сигнатуре содержимого; имя на диске — UUID, хранится sha256.
"""

import hashlib
from pathlib import PurePosixPath, PureWindowsPath
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.db.models import Application, DocumentRow, InfoRequestRow, User
from app.domain.state_machine import ApplicationStatus
from app.schemas.auth import BANK_ROLES, UserRole
from app.schemas.common import ErrorCode
from app.schemas.documents import ALLOWED_UPLOAD_MIME_TYPES, MAX_UPLOAD_BYTES
from app.services.applications import get_visible
from app.storage import Storage

# Сигнатуры начала файла: заявленный тип должен совпадать с содержимым.
_SIGNATURES = {
    "application/pdf": (b"%PDF-",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}


def _safe_filename(name: str | None) -> str:
    base = PureWindowsPath(PurePosixPath(name or "").name).name.strip()
    return base[:255] or "document"


def upload(
    session: Session,
    user: User,
    application_id: UUID,
    file: UploadFile,
    kind: str,
    info_request_id: UUID | None,
    storage: Storage,
) -> DocumentRow:
    application = get_visible(session, user, application_id)
    if application.status != ApplicationStatus.INFO_REQUESTED:
        # TBD (контракт): загрузка в DRAFT. Пока — только в ответ на запрос документов.
        raise ApiError(409, ErrorCode.CONFLICT, "Документы загружаются только по запросу банка")
    if info_request_id is not None:
        request = session.get(InfoRequestRow, info_request_id)
        if request is None or request.application_id != application.id:
            raise ApiError(
                422, ErrorCode.VALIDATION_ERROR, "Такого запроса в заявке нет", "info_request_id"
            )

    mime = (file.content_type or "").lower()
    if mime not in ALLOWED_UPLOAD_MIME_TYPES:
        raise ApiError(415, ErrorCode.UNSUPPORTED_MEDIA_TYPE, "Можно загрузить PDF, JPG или PNG")
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise ApiError(413, ErrorCode.FILE_TOO_LARGE, "Файл больше 10 МБ")
    if not content:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "Файл пустой", "file")
    if not content.startswith(_SIGNATURES[mime]):
        raise ApiError(
            415, ErrorCode.UNSUPPORTED_MEDIA_TYPE, "Содержимое файла не совпадает с его типом"
        )

    document = DocumentRow(
        application_id=application.id,
        info_request_id=info_request_id,
        kind=kind,
        filename=_safe_filename(file.filename),
        mime=mime,
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        storage_path=storage.save(content),
        uploaded_by=user.id,
    )
    session.add(document)
    session.commit()
    return document


def download(
    session: Session, user: User, document_id: UUID, storage: Storage
) -> tuple[DocumentRow, bytes]:
    document = session.get(DocumentRow, document_id)
    if document is None:
        raise ApiError(404, ErrorCode.NOT_FOUND, "Файл не найден")
    application = session.get(Application, document.application_id)
    own = user.role == UserRole.CLIENT and application.company_id == user.company_id
    if not (own or user.role in BANK_ROLES):
        raise ApiError(403, ErrorCode.FORBIDDEN, "Нет доступа к файлу")  # контракт: 403
    content = storage.load(document.storage_path)
    if content is None:
        raise ApiError(404, ErrorCode.NOT_FOUND, "Файл не найден")
    return document, content
