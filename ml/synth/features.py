"""The same ordered 20 features for training and inference; no labels or IDs."""

import math
from datetime import UTC, date, datetime

ACTION_STATUSES = {"INFO_REQUESTED", "APPROVED", "COUNTER_OFFER", "SIGNING"}
FEATURES = [
    "m_okved",
    "m_status",
    "m_product",
    "m_segment",
    "m_general",
    "topic_product",
    "topic_industry",
    "topic_step",
    "topic_support",
    "fresh_7d",
    "micro",
    "young",
    "no_apps",
    "action_needed",
    "product_known",
    "growth",
    "step_x_action",
    "support_x_small_or_young",
    "product_topic_x_no_apps",
    "equipment_x_growth",
]
FEATURE_VERSION = "feed-features-1"


def as_datetime(value: str | datetime) -> datetime:
    result = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    # Backend schemas also accept naive datetimes; interpret those consistently as UTC.
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)


def revenue_growth(revenue: dict[str, int]) -> float:
    years = sorted(revenue, key=int)
    if len(years) < 2 or revenue[years[-2]] <= 0:
        return 0.0
    return max(-1.0, min(1.0, revenue[years[-1]] / revenue[years[-2]] - 1))


def features(profile: dict, candidate: dict, now: str | datetime) -> list[float]:
    now = as_datetime(now)
    registered = profile["registered_at"]
    if isinstance(registered, datetime):
        registered = registered.date()
    elif not isinstance(registered, date):
        registered = date.fromisoformat(registered)
    days = max(0.0, (now - as_datetime(candidate["published_at"])).total_seconds() / 86400)
    matched = set(candidate["matched"])
    topic = candidate["topic"]
    apps = profile["applications"]
    micro = profile["segment"] == "micro"
    young = (now.date() - registered).days / 365 < 2
    no_apps = not apps
    action = any(a["status"] in ACTION_STATUSES for a in apps)
    products = candidate["tags"].get("product", [])
    known = bool(set(products) & {a["product_code"] for a in apps})
    growth = revenue_growth(profile["revenue"])
    values = {
        "m_okved": "okved" in matched,
        "m_status": "status" in matched,
        "m_product": "product" in matched,
        "m_segment": "segment" in matched,
        "m_general": "general" in matched,
        "topic_product": topic == "product",
        "topic_industry": topic == "industry",
        "topic_step": topic == "step",
        "topic_support": topic == "support",
        "fresh_7d": math.exp(-days / 7),
        "micro": micro,
        "young": young,
        "no_apps": no_apps,
        "action_needed": action,
        "product_known": known,
        "growth": growth,
        "step_x_action": topic == "step" and action,
        "support_x_small_or_young": topic == "support" and (micro or young),
        "product_topic_x_no_apps": topic == "product" and no_apps,
        "equipment_x_growth": ("EQUIPMENT" in products) * max(0.0, growth),
    }
    return [float(values[name]) for name in FEATURES]
