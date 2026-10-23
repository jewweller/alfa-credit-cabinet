"""Bounded-memory deterministic Parquet journals with explicit empty-table schemas."""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .features import CATEGORICAL, FEATURES


def schemas(config: dict) -> dict[str, pa.Schema]:
    s, i, f, b = pa.string(), pa.int64(), pa.float64(), pa.bool_()
    ids = [("request_id", s), ("company_id", s), ("as_of", s)]
    loan = pa.struct(
        [
            ("type", s),
            ("balance", s),
            ("monthly_payment", s),
            ("max_overdue_days_24m", i),
            ("current_overdue_days", i),
        ]
    )
    offer = pa.struct(
        [
            ("product_code", s),
            ("amount", s),
            ("term_months", i),
            ("rate", s),
            ("monthly_payment", s),
        ]
    )
    start = int(config["simulation"]["start_date"][:4])
    end = int(config["simulation"]["end_date"][:4])
    revenue = pa.struct([(str(year), s) for year in range(start - 2, end)])
    features = [
        (name, pa.dictionary(pa.int32(), s) if name in CATEGORICAL else pa.float32())
        for name in FEATURES
    ]
    training = [("qid", s), ("label", i), *features]
    result = {
        "companies": [
            ("company_id", s),
            ("inn", s),
            ("kind", s),
            ("status", s),
            ("registered_at", s),
            ("okved_main", s),
            ("okved_extra", pa.list_(s)),
            ("region", s),
            ("segment", s),
            ("employees", i),
            ("name", s),
            ("director_fio", s),
            ("address", s),
        ],
        "fns_profiles": [
            *ids,
            ("revenue", revenue),
            ("tax_debt_rub", s),
            ("msp_category", s),
            ("employees", i),
            (
                "flags",
                pa.struct(
                    [
                        (key, b)
                        for key in ("mass_address", "unreliable_address", "unreliable_director")
                    ]
                ),
            ),
            ("available", b),
        ],
        "bki_reports": [
            *ids,
            ("report_id", s),
            ("has_history", b),
            ("bankruptcy", b),
            ("loans", pa.list_(loan)),
            ("max_overdue_days_24m", i),
            ("current_overdue_days", i),
            ("inquiries_30d", i),
            ("available", b),
        ],
        "requests": [
            ("request_id", s),
            ("company_id", s),
            ("created_at", s),
            ("purpose", s),
            ("amount_requested", s),
            ("term_requested", i),
            ("revenue_12m", s),
            ("existing_payments_monthly", s),
            ("bki_consent", b),
            ("company_split", s),
            ("split", s),
            ("exclusion_reason", s),
            ("empty_reason", s),
            ("candidate_count", i),
            ("shown_count", i),
            ("random_policy", b),
            ("positive", b),
        ],
        "candidates": [
            ("request_id", s),
            ("candidate_id", s),
            ("product_code", s),
            ("amount", s),
            ("term_months", i),
            ("rate", s),
            ("monthly_payment", s),
            ("shown_position", i),
        ],
        "outcomes": [
            ("request_id", s),
            ("candidate_id", s),
            ("clicked", b),
            ("applied", b),
            ("decision_outcome", s),
            ("rule", s),
            ("reason_code", s),
            ("final_outcome", s),
            ("final_reason_code", s),
            ("offer", offer),
            ("offer_accepted", b),
            ("issued", b),
            ("label", i),
        ],
        "latent_truth": [
            ("request_id", s),
            ("company_id", s),
            ("candidate_id", s),
            *[
                (key, f)
                for key in (
                    "latent_risk",
                    "price_sensitivity",
                    "urgency",
                    "amount_flexibility",
                    "term_preference",
                    "approval_probability",
                    "acceptance_probability",
                    "client_utility",
                    "ideal_relevance",
                )
            ],
        ],
        "evaluation": [
            ("qid", s),
            ("candidate_id", s),
            ("company_id", s),
            ("created_at", s),
            ("split", s),
            ("shown_position", i),
            ("random_policy", b),
            ("training_eligible", b),
            ("label", i),
            *features,
        ],
        "train": training,
        "validation": training,
        "test": training,
    }
    return {
        name: pa.schema(fields, metadata={b"synthetic": b"true", b"schema_version": b"1"})
        for name, fields in result.items()
    }


class Journals:
    def __init__(self, directory: Path, config: dict):
        self.directory = directory
        self.schemas = schemas(config)
        self.batch_size = config["simulation"]["parquet_batch_rows"]
        self.buffers = {name: [] for name in self.schemas}
        self.counts = dict.fromkeys(self.schemas, 0)
        self.writers = {
            name: pq.ParquetWriter(
                directory / f"{name}.parquet",
                schema,
                compression="zstd",
                compression_level=3,
                version="2.6",
                write_statistics=True,
            )
            for name, schema in self.schemas.items()
        }

    def append(self, name: str, row: dict) -> None:
        self.buffers[name].append(row)
        self.counts[name] += 1
        if len(self.buffers[name]) >= self.batch_size:
            self.flush(name)

    def flush(self, name):
        if self.buffers[name]:
            table = pa.Table.from_pylist(self.buffers[name], schema=self.schemas[name])
            self.writers[name].write_table(table, row_group_size=self.batch_size)
            self.buffers[name].clear()

    def close(self):
        for name, writer in self.writers.items():
            self.flush(name)
            writer.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def read_rows(directory: Path, table: str) -> list[dict]:
    return pq.read_table(directory / f"{table}.parquet").to_pylist()
