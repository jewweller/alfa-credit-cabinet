"""Кредитное решение R1–R10 (план, раздел 7). Порядок фиксирован, срабатывает первое правило.

Решение учитывает стоп-факторы, продукт, сумму, срок и нагрузку; балл и грейд берутся из
ScoringResult. Все пороги, надбавки, округление и коды причин — из scoring/config.yaml.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.domain.loan_math import max_principal, round_money
from app.schemas.decisions import RejectReason
from app.scoring.config import EngineConfig, Outcome, RequestItem, load_config
from app.scoring.engine import ScoringResult
from app.scoring.finance import (
    debt_load_pct,
    existing_payments,
    latest_fns_revenue,
    monthly_payment,
    monthly_revenue,
)
from app.scoring.inputs import ApplicantSources, LoanRequest, ProductTerms, SourceState

_SOURCE_LABELS = {
    "egrul": "ЕГРЮЛ",
    "egrip": "ЕГРИП",
    "fns_tb": "ФНС «Прозрачный бизнес»",
    "bki": "БКИ",
}


def _rub(value: Decimal) -> str:
    """Сумма для текста правил на экране B3: «24 000 000 ₽»."""
    return f"{value:,.0f} ₽".replace(",", " ")


@dataclass(frozen=True)
class Offer:
    product: ProductTerms
    amount: Decimal
    term_months: int
    rate: Decimal
    monthly_payment: Decimal
    debt_load_pct: Decimal


@dataclass(frozen=True)
class RuleCheck:
    rule: str
    fired: bool
    detail: str


@dataclass(frozen=True)
class Decision:
    config_version: str
    outcome: Outcome
    rule: str
    reason_code: str
    client_reason: RejectReason | None
    client_message: str
    client_next_step: str
    staff_message: str
    offer: Offer | None
    info_request_items: tuple[RequestItem, ...]
    checks: tuple[RuleCheck, ...]


class _Fired(Exception):
    def __init__(
        self,
        reason_code: str,
        detail: str,
        offer: Offer | None = None,
        items: tuple[RequestItem, ...] = (),
        **placeholders: str,
    ) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.detail = detail
        self.offer = offer
        self.items = items
        self.placeholders = placeholders


class _Engine:
    def __init__(
        self,
        config: EngineConfig,
        request: LoanRequest,
        sources: ApplicantSources,
        scoring: ScoringResult,
        products: Sequence[ProductTerms],
        proof_document_uploaded: bool,
    ) -> None:
        self.config = config
        self.request = request
        self.sources = sources
        self.scoring = scoring
        self.products = products
        self.proof_uploaded = proof_document_uploaded
        self.checks: list[RuleCheck] = []
        self.max_load = config.calculation.debt_load.max_pct

    # ── расчёты ──────────────────────────────────────────────────────────────

    def _rate(self, product: ProductTerms) -> Decimal:
        return (
            product.base_rate
            + self.config.calculation.pricing.grade_surcharge_pp[self.scoring.grade]
        )

    def _offer(self, product: ProductTerms, amount: Decimal, term: int) -> Offer | None:
        """Оффер, если нагрузка по нему не выше порога; иначе None."""
        rate = self._rate(product)
        payment = monthly_payment(self.config, amount, rate, term)
        load = debt_load_pct(self.config, self.request, self.sources, payment)
        if load is None or load > self.max_load:
            return None
        return Offer(product, amount, term, rate, payment, load)

    def _max_affordable_amount(
        self, product: ProductTerms, term: int, cap: Decimal
    ) -> Offer | None:
        """Наибольшая сумма ≤ cap (вниз до шага), при которой нагрузка не выше порога."""
        budget = monthly_revenue(
            self.config, self.request, self.sources
        ) * self.max_load / 100 - existing_payments(self.config, self.request, self.sources)
        if budget <= 0:
            return None
        rule = self.config.calculation.rounding["amount"]
        amount = round_money(
            min(cap, product.max_amount, max_principal(budget, self._rate(product), term)),
            rule.mode,
            rule.step_rub,
        )
        # Округление платежа вверх может перевалить через порог: шаг вниз, пока не влезет.
        while amount >= product.min_amount:
            offer = self._offer(product, amount, term)
            if offer is not None:
                return offer
            amount -= rule.step_rub
        return None

    def _fit_terms(self, product: ProductTerms, amount: Decimal, start_term: int) -> Offer | None:
        """R10, шаг 1: срок длиннее с шагом term_step_months до максимума продукта."""
        r10 = self.config.rules.R10
        terms = list(
            range(start_term + r10.term_step_months, product.max_term + 1, r10.term_step_months)
        )
        if (
            r10.include_max_term_as_last_candidate
            and product.max_term > start_term
            and product.max_term not in terms
        ):
            terms.append(product.max_term)
        for term in terms:
            offer = self._offer(product, amount, term)
            if offer is not None:
                return offer
        return None

    # ── правила ──────────────────────────────────────────────────────────────

    def _check(self, rule: str, fired: bool, detail: str) -> None:
        self.checks.append(RuleCheck(rule, fired, detail))

    def r1(self) -> None:
        registry = self.sources.registry
        label = _SOURCE_LABELS[self.sources.registry_source]
        if registry.state == SourceState.NOT_FOUND:
            self._check("R1", True, f"{label}: 404")
            raise _Fired("R1_NOT_FOUND", f"{label}: 404", registry=label)
        if registry.state != SourceState.OK or registry.data is None:
            self._check("R1", False, f"{label} недоступен — проверит R3")
            return
        status = registry.data.status
        if status in self.config.rules.R1["allowed_registry_statuses"]:
            self._check("R1", False, f"{label}: {status}")
            return
        self._check("R1", True, f"{label}: {status}")
        code = "R1_LIQUIDATING" if status == "LIQUIDATING" else "R1_LIQUIDATED"
        raise _Fired(code, f"{label}: {status}", registry=label)

    def r2(self) -> None:
        bki = self.sources.bki.data
        if self.sources.bki.state != SourceState.OK or bki is None:
            self._check("R2", False, "БКИ недоступно — проверит R3")
            return
        if bki.bankruptcy:
            self._check("R2", True, "bankruptcy = true")
            raise _Fired("R2_BANKRUPTCY", "bankruptcy = true")
        limit = self.config.rules.R2["overdue_days_gt"]
        worst = max((loan.current_overdue_days for loan in bki.loans), default=0)
        if worst > limit:
            self._check("R2", True, f"текущая просрочка {worst} дн. > {limit}")
            raise _Fired("R2_OVERDUE", f"текущая просрочка {worst} дн.")
        self._check("R2", False, f"текущая просрочка {worst} дн.")

    def r3(self) -> None:
        required = self.config.integrations.required_sources[self.sources.company_kind]
        down = [s for s in required if self.sources.state_of(s) == SourceState.UNAVAILABLE]
        if down:
            names = ", ".join(_SOURCE_LABELS[s] for s in down)
            self._check("R3", True, f"недоступны: {names}")
            raise _Fired("R3_SOURCE_UNAVAILABLE", f"недоступны: {names}", source=names)
        self._check("R3", False, "все обязательные источники ответили")

    def r4(self) -> None:
        r4 = self.config.rules.R4
        fns = latest_fns_revenue(self.sources)
        if fns is None:
            self._check("R4", False, "нет выручки ФНС за последний год")
            return
        declared = self.request.revenue_12m
        # ФНС ≤ 0 при ненулевой выручке в анкете — расхождение заведомо больше порога (TBD).
        mismatch = abs(declared - fns) / fns * 100 if fns > 0 else None
        detail = f"анкета {_rub(declared)}, ФНС {_rub(fns)}, расхождение " + (
            f"{mismatch:.1f}%" if mismatch is not None else "не определено (ФНС ≤ 0)"
        )
        if mismatch is not None and mismatch <= r4.mismatch_pct_gt:
            self._check("R4", False, detail)
            return
        if mismatch is None and declared <= 0:
            self._check("R4", False, detail)
            return
        self._check("R4", True, detail)
        if self.proof_uploaded:
            raise _Fired("R4_REVENUE_MISMATCH_REVIEW", detail)
        raise _Fired("R4_REVENUE_PROOF_REQUIRED", detail, items=r4.request_items)

    def r5(self) -> None:
        limit = self.config.rules.R5["amount_rub_gt"]
        fired = self.request.amount > limit
        self._check("R5", fired, f"сумма {_rub(self.request.amount)}, порог {_rub(limit)}")
        if fired:
            raise _Fired("R5_LARGE_AMOUNT", f"сумма {_rub(self.request.amount)}")

    def _grade_rule(self, rule: str, grades: Sequence[str], code: str) -> None:
        fired = self.scoring.grade in grades
        self._check(rule, fired, f"грейд {self.scoring.grade}")
        if fired:
            raise _Fired(code, f"грейд {self.scoring.grade}")

    def r6(self) -> None:
        self._grade_rule("R6", self.config.rules.R6["grades"], "R6_GRADE_E")

    def r7(self) -> None:
        self._grade_rule("R7", self.config.rules.R7["grades"], "R7_GRADE_D")

    def r8(self) -> None:
        r8 = self.config.rules.R8
        if self.scoring.grade not in r8.grades:
            self._check("R8", False, f"грейд {self.scoring.grade}")
            return
        share = self.request.amount * r8.amount_share_pct / 100
        offer = self._max_affordable_amount(self.request.product, self.request.term_months, share)
        if offer is None:
            self._check("R8", True, "грейд C, предложение сформировать нельзя")
            raise _Fired("R8_NO_OFFER", "предложение сформировать нельзя")
        detail = f"грейд C, {_rub(offer.amount)} на {offer.term_months} мес под {offer.rate}%"
        self._check("R8", True, detail)
        raise _Fired("R8_COUNTER_OFFER", detail, offer=offer)

    def r9(self) -> None:
        if self.scoring.grade not in self.config.rules.R9["grades"]:
            self._check("R9", False, f"грейд {self.scoring.grade}")
            return
        product = self.request.product
        offer = self._offer(product, self.request.amount, self.request.term_months)
        if offer is None:
            self._check(
                "R9", False, f"нагрузка по ставке {self._rate(product)}% выше {self.max_load}%"
            )
            return
        detail = f"нагрузка {offer.debt_load_pct:.1f}% по ставке {offer.rate}%"
        self._check("R9", True, detail)
        raise _Fired("R9_APPROVED", detail, offer=offer)

    def r10(self) -> None:
        r10 = self.config.rules.R10
        if self.scoring.grade not in r10.grades:
            self._check("R10", False, f"грейд {self.scoring.grade}")
            return
        request, product = self.request, self.request.product
        # Шаг 1 — срок, шаг 2 — сумма на максимальном сроке продукта.
        offer = self._fit_terms(product, request.amount, request.term_months)
        offer = offer or self._max_affordable_amount(product, product.max_term, request.amount)
        # Шаг 3 — другие продукты той же цели. Порядок перебора в требованиях не задан:
        # по возрастанию базовой ставки, затем по коду (TBD).
        if offer is None and r10.search_other_products:
            others = sorted(
                (
                    p
                    for p in self.products
                    if p.code != product.code and request.purpose in p.purposes
                ),
                key=lambda p: (p.base_rate, p.code),
            )
            for other in others:
                amount = min(request.amount, other.max_amount)
                term = min(max(request.term_months, other.min_term), other.max_term)
                if amount < other.min_amount:
                    continue
                offer = (
                    self._offer(other, amount, term)
                    or self._fit_terms(other, amount, term)
                    or self._max_affordable_amount(other, other.max_term, amount)
                )
                if offer is not None:
                    break
        if offer is None:
            self._check("R10", True, "ни срок, ни сумма, ни другой продукт не подошли")
            raise _Fired("R10_NO_OFFER", "условий с нагрузкой до порога нет")
        detail = (
            f"{offer.product.code}: {_rub(offer.amount)} на {offer.term_months} мес "
            f"под {offer.rate}%, нагрузка {offer.debt_load_pct:.1f}%"
        )
        self._check("R10", True, detail)
        raise _Fired("R10_COUNTER_OFFER", detail, offer=offer)

    def run(self) -> Decision:
        rules: tuple[Callable[[], None], ...] = (
            self.r1, self.r2, self.r3, self.r4, self.r5,
            self.r6, self.r7, self.r8, self.r9, self.r10,
        )  # fmt: skip
        try:
            for rule in rules:
                rule()
        except _Fired as fired:
            return self._decision(fired)
        # R9 и R10 вместе покрывают A/B, R6–R8 — C/D/E: сюда попасть нельзя.
        raise AssertionError("ни одно правило R1–R10 не сработало")

    def _decision(self, fired: _Fired) -> Decision:
        reason = self.config.reason_codes[fired.reason_code]
        fill = {"registry": "", "source": "", **fired.placeholders}
        return Decision(
            config_version=self.config.config_version,
            outcome=self.config.outcome_of(fired.reason_code),
            rule=reason.rule,
            reason_code=fired.reason_code,
            client_reason=reason.client_reason,
            client_message=reason.client_message.format(**fill),
            client_next_step=reason.client_next_step.format(**fill),
            staff_message=reason.staff_message.format(**fill),
            offer=fired.offer,
            info_request_items=fired.items,
            checks=tuple(self.checks),
        )


def decide(
    request: LoanRequest,
    sources: ApplicantSources,
    scoring: ScoringResult,
    products: Sequence[ProductTerms],
    proof_document_uploaded: bool = False,
    config: EngineConfig | None = None,
) -> Decision:
    config = config or load_config()
    if scoring.config_version != config.config_version:
        raise ValueError(
            f"скоринг посчитан по конфигу {scoring.config_version}, "
            f"а решение — по {config.config_version}"
        )
    return _Engine(config, request, sources, scoring, products, proof_document_uploaded).run()
