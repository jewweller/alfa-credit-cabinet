"""SQLAlchemy-модели (план, раздел 6).

Есть: вход, черновик заявки и история (0001); обогащение, скоринг, решение, оффер и запрос
документов (0002); документы (0003); подпись и выдача (0004); исполнитель заявки в банке
(0005); события ленты (0006). Аудит и очередь воркера — отдельными миграциями вместе с их
функциональностью.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# purpose_tags[] — массив в PostgreSQL; в SQLite (unit-тесты) хранится как JSON.
TAG_LIST = ARRAY(String(32)).with_variant(JSON(), "sqlite")
# Сырые ответы источников, баллы и трасса правил — jsonb в PostgreSQL (план, раздел 6).
DOCUMENT = JSON().with_variant(JSONB(), "postgresql")
MONEY = Numeric(14, 2)
RATE = Numeric(5, 2)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    inn: Mapped[str] = mapped_column(String(12), unique=True)
    ogrn: Mapped[str] = mapped_column(String(15))
    kind: Mapped[str] = mapped_column(String(3))
    name: Mapped[str] = mapped_column(String(255))
    okved_main: Mapped[str] = mapped_column(String(16))
    region: Mapped[str] = mapped_column(String(128))
    registered_at: Mapped[date] = mapped_column(Date)
    segment: Mapped[str] = mapped_column(String(8))


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16))
    full_name: Mapped[str] = mapped_column(String(255))
    company_id: Mapped[UUID | None] = mapped_column(ForeignKey("companies.id"))

    company: Mapped[Company | None] = relationship(lazy="joined")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    purpose_tags: Mapped[list[str]] = mapped_column(TAG_LIST)
    min_amount: Mapped[Decimal] = mapped_column(MONEY)
    max_amount: Mapped[Decimal] = mapped_column(MONEY)
    min_term: Mapped[int] = mapped_column(Integer)
    max_term: Mapped[int] = mapped_column(Integer)
    base_rate: Mapped[Decimal] = mapped_column(RATE)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    number: Mapped[str] = mapped_column(String(16), unique=True)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    applicant_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    product_id: Mapped[UUID | None] = mapped_column(ForeignKey("products.id"))
    amount: Mapped[Decimal | None] = mapped_column(MONEY)
    term_months: Mapped[int | None] = mapped_column(Integer)
    purpose: Mapped[str | None] = mapped_column(String(32))
    revenue_12m: Mapped[Decimal | None] = mapped_column(MONEY)
    existing_payments_monthly: Mapped[Decimal | None] = mapped_column(MONEY)
    bki_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32))
    status_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Сотрудник банка, который взял заявку в работу (экран B2, «взять в работу»).
    assignee_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    company: Mapped[Company] = relationship(lazy="joined")
    product: Mapped[Product | None] = relationship(lazy="joined")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy="joined")

    # Оптимистическая блокировка (план, раздел 9): SQLAlchemy сам увеличивает version
    # и бросает StaleDataError, если запись успели изменить параллельно.
    __mapper_args__ = {"version_id_col": version}


class ApplicationStatusHistory(Base):
    __tablename__ = "application_status_history"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[UUID | None] = mapped_column(Uuid)
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EnrichmentResult(Base):
    """Ответ одного источника по заявке: что пришло, сколько было попыток."""

    __tablename__ = "enrichment_results"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    source: Mapped[str] = mapped_column(String(16))  # egrul | egrip | fns_tb | bki
    status: Mapped[str] = mapped_column(String(16))  # ok | not_found | unavailable
    response: Mapped[dict | None] = mapped_column(DOCUMENT)
    attempts: Mapped[int] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String(255))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ScoringResultRow(Base):
    __tablename__ = "scoring_results"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    model_version: Mapped[str] = mapped_column(String(32))  # config_version из config.yaml
    total_score: Mapped[int] = mapped_column(Integer)
    grade: Mapped[str] = mapped_column(String(1))
    factors: Mapped[dict] = mapped_column(DOCUMENT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DecisionRow(Base):
    """Кредитное решение. Внутреннее: трасса правил и коды — для сотрудников, не для клиента."""

    __tablename__ = "decisions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    scoring_result_id: Mapped[UUID | None] = mapped_column(ForeignKey("scoring_results.id"))
    outcome: Mapped[str] = mapped_column(String(32))
    reason_code: Mapped[str] = mapped_column(String(64))  # код из config.yaml, например R9_APPROVED
    client_reason: Mapped[str | None] = mapped_column(String(32))  # RejectReason контракта
    rules_fired: Mapped[dict] = mapped_column(DOCUMENT)  # config_version + трасса R1–R10
    decided_by: Mapped[str] = mapped_column(String(16))  # system | underwriter
    underwriter_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OfferRow(Base):
    __tablename__ = "offers"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    decision_id: Mapped[UUID] = mapped_column(ForeignKey("decisions.id"))
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    term_months: Mapped[int] = mapped_column(Integer)
    rate: Mapped[Decimal] = mapped_column(RATE)
    monthly_payment: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(String(16))  # active | accepted | declined
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InfoRequestRow(Base):
    __tablename__ = "info_requests"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    decision_id: Mapped[UUID] = mapped_column(ForeignKey("decisions.id"))
    items: Mapped[list] = mapped_column(DOCUMENT)
    message: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(16))  # open | answered
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DocumentRow(Base):
    """Файл клиента в заявке (план, разделы 6 и 9). Содержимое — в Storage, имя на диске — UUID."""

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    info_request_id: Mapped[UUID | None] = mapped_column(ForeignKey("info_requests.id"))
    kind: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(255))  # как загрузил клиент
    mime: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(String(64))  # ключ в Storage (UUID)
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SignatureRow(Base):
    """Симуляция ПЭП (план, раздел 6): одноразовый код подписи по принятому офферу.

    Хранится только HMAC кода. Новый запрос кода заменяет прежний; `signed_at` — код подтверждён.
    """

    __tablename__ = "signatures"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    offer_id: Mapped[UUID] = mapped_column(ForeignKey("offers.id"))
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DisbursementRow(Base):
    """Симуляция выдачи (план, раздел 6): одна выдача на заявку."""

    __tablename__ = "disbursements"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), unique=True)
    offer_id: Mapped[UUID] = mapped_column(ForeignKey("offers.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    account_mask: Mapped[str] = mapped_column(String(16))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeedEventRow(Base):
    """Событие ленты клиента о смене статуса заявки (план, разделы 4 и 6: `feed_events`).

    Это «уведомления» внутри продукта вместо email/SMS. Текст фиксируется при создании.
    """

    __tablename__ = "feed_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)  # заявитель
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    status: Mapped[str] = mapped_column(String(32))  # куда перешла заявка
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(String(1000))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
