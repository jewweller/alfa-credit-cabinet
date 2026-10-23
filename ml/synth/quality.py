"""Auditable diagnostics. Unagreed gates are reported as pending, never as passed."""

from collections import Counter
from datetime import date

import numpy as np


def histogram(values, bins=10):
    counts, edges = np.histogram(values, bins=bins)
    return {"edges": edges.tolist(), "counts": counts.tolist()}


class Diagnostics:
    def __init__(self, config):
        self.config = config
        self.categories = {
            name: Counter()
            for name in ("kind", "status", "segment", "grade", "decision", "split", "label")
        }
        self.values = {
            name: []
            for name in (
                "age_years",
                "micro_revenue",
                "small_revenue",
                "tax_debt",
                "revenue_growth",
                "request_age",
                "overdue",
                "risk",
                "candidate_count",
            )
        }
        self.funnel = Counter()
        self.queries = Counter()

    def company(self, company, latent):
        for key in ("kind", "status", "segment"):
            self.categories[key][company[key]] += 1
        self.values["age_years"].append(
            (
                date.fromisoformat(self.config["simulation"]["end_date"])
                - date.fromisoformat(company["registered_at"])
            ).days
            / 365.25
        )
        self.values[f"{company['segment']}_revenue"].append(latent["annual_revenue"])

    def request(self, request, company, fns, bki, latent, scores, outcomes):
        self.queries["total"] += 1
        self.queries["nonempty"] += request["candidate_count"] > 0
        self.queries["positive"] += request["positive"]
        self.queries["consent"] += request["bki_consent"]
        self.queries["random"] += request["random_policy"]
        self.queries["fns_unavailable"] += not fns["available"]
        self.queries["bki_unavailable"] += not bki["available"]
        self.categories["split"][request["split"]] += 1
        self.values["tax_debt"].append(float(fns["tax_debt_rub"]))
        self.values["revenue_growth"].append(latent["growth"])
        self.values["candidate_count"].append(request["candidate_count"])
        age = (
            date.fromisoformat(request["created_at"][:10])
            - date.fromisoformat(company["registered_at"])
        ).days / 365.25
        self.values["request_age"].append(age)
        self.values["overdue"].append(int(bki["max_overdue_days_24m"] > 0))
        self.values["risk"].append(latent["latent_risk"])
        self.funnel["shown"] += request["shown_count"]
        for score in scores:
            self.categories["grade"][score.grade or "UNKNOWN"] += 1
        for outcome in outcomes:
            self.categories["decision"][outcome["decision_outcome"]] += 1
            self.categories["label"][str(outcome["label"])] += 1
            for stage in ("clicked", "applied", "offer_accepted", "issued"):
                self.funnel[stage] += outcome[stage]

    def report(self):
        values = self.values
        correlation = (
            float(np.corrcoef(values["request_age"], values["overdue"])[0, 1])
            if (len(values["request_age"]) > 1 and np.std(values["overdue"]) > 0)
            else None
        )
        q = self.queries
        positive = q["positive"] / max(q["nonempty"], 1)
        low, high = self.config["quality"]["positive_query_interval"]
        distributions = {
            key: {"median": float(np.median(v)), "histogram": histogram(v)}
            for key, v in values.items()
            if v
        }
        gates = {
            "positive_query_fraction": {
                "value": positive,
                "target": [low, high],
                "passed": low <= positive <= high,
            },
            "grade_intervals": "pending agreement"
            if self.config["quality"]["grade_intervals"] is None
            else "configured",
            "outcome_intervals": "pending agreement"
            if self.config["quality"]["outcome_intervals"] is None
            else "configured",
            "funnel_intervals": "pending agreement"
            if self.config["quality"]["funnel_intervals"] is None
            else "configured",
            "deployment": "offline only; rollout criteria pending",
        }
        # Optional agreed proportions are enforced, without modifying the generated data.
        for name, counts in (
            ("grade_intervals", self.categories["grade"]),
            ("outcome_intervals", self.categories["decision"]),
            ("funnel_intervals", self.funnel),
        ):
            bounds = self.config["quality"][name]
            if bounds is not None:
                denominator = (
                    self.funnel["shown"] if name == "funnel_intervals" else sum(counts.values())
                )
                gates[name] = {
                    key: {
                        "value": counts[key] / max(denominator, 1),
                        "target": interval,
                        "passed": interval[0] <= counts[key] / max(denominator, 1) <= interval[1],
                    }
                    for key, interval in bounds.items()
                }
        return {
            "queries": dict(q),
            "funnel": dict(self.funnel),
            "categories": {
                key: dict(sorted(value.items())) for key, value in self.categories.items()
            },
            "distributions": distributions,
            "age_overdue_correlation": correlation,
            "gates": gates,
        }


def data_card(report, manifest):
    lines = [
        "# Synthetic data run",
        "",
        "Все записи синтетические. Это офлайн-эксперимент, не кредитная модель.",
        "",
        f"- Generator: {manifest['generator_version']}",
        f"- Seed: {manifest['seed']}",
        f"- Config SHA: {manifest['config_hash']}",
        f"- Rules: {manifest['rules_version']}",
        "- Допущения и ограничения: `ml/DATA_CARD.md` в репозитории.",
        "",
        "## Таблицы",
        "",
        "| Таблица | Строк |",
        "|---|---:|",
    ]
    lines += [f"| {name} | {count} |" for name, count in sorted(manifest["row_counts"].items())]
    lines += ["", "## Запросы и воронка", ""]
    lines += [f"- {key}: {value}" for key, value in report["queries"].items()]
    lines += [f"- {key}: {value}" for key, value in report["funnel"].items()]
    lines += [
        "",
        "## Проверки",
        "",
        f"- Позитивы среди непустых запросов: {report['gates']['positive_query_fraction']}",
        f"- Корреляция возраста и просрочек: {report['age_overdue_correlation']}",
        "- Коридоры грейдов/исходов/воронки и порог внедрения требуют согласования.",
        "- Полные значения проверок, включая неуспешные: `quality.json`.",
    ]
    for key, distribution in report["distributions"].items():
        lines += [
            "",
            f"## {key}",
            "",
            f"Медиана: {distribution['median']:.4f}",
            "",
            "| Интервал | Число | Гистограмма |",
            "|---|---:|---|",
        ]
        hist = distribution["histogram"]
        maximum = max(hist["counts"], default=1)
        for lo, hi, count in zip(
            hist["edges"][:-1], hist["edges"][1:], hist["counts"], strict=True
        ):
            bars = "█" * round(30 * count / max(maximum, 1))
            lines.append(f"| {lo:.3g} … {hi:.3g} | {count} | {bars} |")
    return "\n".join(lines) + "\n"
