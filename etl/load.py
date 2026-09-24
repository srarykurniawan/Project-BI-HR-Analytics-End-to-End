"""
load.py - TAHAP 3: LOAD
Membuat ulang skema star (sql/schema.sql) lalu memasukkan dimensi, kemudian fakta.
Strategi: FULL REFRESH (idempotent - aman dijalankan berkali-kali, hasil selalu sama).
"""
from __future__ import annotations

import logging
import re

import pandas as pd
from sqlalchemy import text

from config import EXPORT_CSV, EXPORT_DIR, SQL_DIR

log = logging.getLogger("etl.load")

LOAD_ORDER = [  # dimensi dulu, baru fakta (menghormati foreign key)
    "dim_date", "dim_department", "dim_position", "dim_location", "dim_course", "dim_employee",
    "fact_headcount_monthly", "fact_employee_movement", "fact_attendance", "fact_payroll",
    "fact_performance", "fact_engagement", "fact_training", "fact_recruitment", "kpi_target",
]


def run_sql_file(engine, path) -> None:
    sql = path.read_text(encoding="utf-8")
    sql = re.sub(r"--[^\n]*", "", sql)                         # buang komentar
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def load_all(tables: dict[str, pd.DataFrame], engine) -> dict[str, int]:
    run_sql_file(engine, SQL_DIR / "schema.sql")
    log.info("  skema dibuat ulang dari sql/schema.sql")
    counts = {}
    for name in LOAD_ORDER:
        df = tables[name]
        df.to_sql(name, engine, if_exists="append", index=False, chunksize=10_000)
        counts[name] = len(df)
        log.info("  load %-24s %8d baris", name, len(df))
        if EXPORT_CSV:
            df.to_csv(EXPORT_DIR / f"{name}.csv", index=False)
    if EXPORT_CSV:
        log.info("  salinan CSV ditulis ke %s", EXPORT_DIR)
    return counts


def load_audit(engine, name: str, df: pd.DataFrame, if_exists="replace") -> None:
    """Tabel audit ETL: etl_dq_results, etl_rejected_rows, etl_run_log."""
    df.to_sql(name, engine, if_exists=if_exists, index=False, chunksize=10_000)


def create_views(engine) -> None:
    run_sql_file(engine, SQL_DIR / "views.sql")
    log.info("  view analitik dibuat dari sql/views.sql")
