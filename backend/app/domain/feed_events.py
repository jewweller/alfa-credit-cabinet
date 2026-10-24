"""Тексты событий ленты о смене статуса заявки — как в моках фронта (frontend/src/mocks/db.ts,
EVENT_TEXT). Статусы без текста (черновик, промежуточные шаги конвейера, «подписано»,
отказ клиента) событий не создают.
"""

from collections.abc import Callable, Mapping

from app.domain.state_machine import ApplicationStatus

S = ApplicationStatus

EVENT_TEXT: Mapping[ApplicationStatus, Callable[[str], tuple[str, str]]] = {
    S.SUBMITTED: lambda n: (
        f"Заявка №{n} отправлена",
        "Проверяем данные о компании. Ничего делать не нужно.",
    ),
    S.INFO_REQUESTED: lambda n: (
        f"По заявке №{n} нужны документы",
        "Загрузите их в карточке заявки — и мы продолжим рассмотрение.",
    ),
    S.MANUAL_REVIEW: lambda n: (
        f"Заявку №{n} смотрит специалист",
        "Обычно это занимает до одного рабочего дня.",
    ),
    S.APPROVED: lambda n: (
        f"Заявка №{n} одобрена",
        "Посмотрите предложение и график платежей.",
    ),
    S.COUNTER_OFFER: lambda n: (
        f"По заявке №{n} — другие условия",
        "Сравните их с запрошенными.",
    ),
    S.REJECTED: lambda n: (
        f"По заявке №{n} — отказ",
        "Мы объясним причину и что можно сделать.",
    ),
    S.SIGNING: lambda n: (
        f"Предложение по заявке №{n} принято",
        "Осталось подписать документы.",
    ),
    S.ISSUED: lambda n: (
        f"По заявке №{n} деньги зачислены",
        "Средства у вас на счёте. График платежей всегда под рукой.",
    ),
    S.CANCELLED: lambda n: (
        f"Заявка №{n} отозвана",
        "Её можно подать заново в любой момент.",
    ),
}


def event_text(status: ApplicationStatus, number: str) -> tuple[str, str] | None:
    """Заголовок и текст события; None — для этого статуса событие не создаётся."""
    text = EVENT_TEXT.get(status)
    return text(number) if text else None
