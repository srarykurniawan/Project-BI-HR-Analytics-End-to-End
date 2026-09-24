"""
data_quality.py - TAHAP 2b: DATA QUALITY GATE
Menjalankan aturan kualitas data pada tabel hasil transform SEBELUM di-load.
Aturan 'CRITICAL' yang gagal akan menghentikan pipeline (data jelek tidak masuk DWH).
Hasil semua cek disimpan ke tabel etl_dq_results.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger("etl.dq")


class DQ:
    def __init__(self, tables: dict[str, pd.DataFrame]):
        self.t = tables
        self.results: list[dict] = []

    def _rec(self, rule, table, severity, failed, total, note=""):
        status = "PASS" if failed == 0 else ("FAIL" if severity == "CRITICAL" else "WARN")
        self.results.append(dict(rule=rule, table_name=table, severity=severity, failed_rows=int(failed),
                                 total_rows=int(total), status=status, note=note))
        lvl = logging.INFO if status == "PASS" else (logging.ERROR if status == "FAIL" else logging.WARNING)
        log.log(lvl, "  [%s] %-28s %-24s gagal=%d/%d %s", status, rule, table, failed, total, note)

    # --- jenis aturan ---
    def not_empty(self, table):
        self._rec("NOT_EMPTY", table, "CRITICAL", int(len(self.t[table]) == 0), 1)

    def unique(self, table, cols):
        df = self.t[table]
        self._rec(f"UNIQUE({','.join(cols)})", table, "CRITICAL", int(df.duplicated(cols).sum()), len(df))

    def not_null(self, table, col, severity="CRITICAL"):
        df = self.t[table]
        self._rec(f"NOT_NULL({col})", table, severity, int(df[col].isna().sum()), len(df))

    def fk(self, table, col, dim, dim_col, nullable=False):
        df = self.t[table]
        vals = df[col].dropna() if nullable else df[col]
        bad = ~vals.isin(set(self.t[dim][dim_col]))
        self._rec(f"FK({col}->{dim})", table, "CRITICAL", int(bad.sum()), len(df))

    def in_range(self, table, col, lo, hi, severity="WARNING"):
        s = self.t[table][col].dropna()
        self._rec(f"RANGE({col} {lo}..{hi})", table, severity, int((~s.between(lo, hi)).sum()), len(s))

    def custom(self, rule, table, severity, failed_mask, note=""):
        self._rec(rule, table, severity, int(np.asarray(failed_mask).sum()), len(failed_mask), note)

    def frame(self):
        return pd.DataFrame(self.results)

    @property
    def critical_failed(self):
        return any(r["status"] == "FAIL" for r in self.results)


def run_checks(t: dict[str, pd.DataFrame]) -> DQ:
    dq = DQ(t)
    for name in t:
        dq.not_empty(name)

    # Primary key unik
    for table, cols in {
        "dim_date": ["date_key"], "dim_department": ["department_key"], "dim_position": ["position_key"],
        "dim_location": ["location_key"], "dim_employee": ["employee_key"], "dim_course": ["course_key"],
        "fact_headcount_monthly": ["date_key", "employee_key"], "fact_employee_movement": ["movement_key"],
        "fact_attendance": ["attendance_key"], "fact_payroll": ["payroll_key"], "fact_performance": ["performance_key"],
        "fact_engagement": ["engagement_key"], "fact_training": ["training_key"], "fact_recruitment": ["requisition_key"],
        "kpi_target": ["kpi_code", "year"],
    }.items():
        dq.unique(table, cols)
    # Business key unik
    dq.unique("dim_employee", ["employee_id"])
    dq.unique("fact_attendance", ["employee_key", "date_key"])
    dq.unique("fact_payroll", ["employee_key", "date_key"])
    dq.unique("fact_performance", ["employee_key", "review_year"])

    # Integritas referensial (FK)
    facts = ["fact_headcount_monthly", "fact_employee_movement", "fact_attendance", "fact_payroll",
             "fact_performance", "fact_engagement", "fact_training"]
    for f in facts:
        dq.fk(f, "date_key", "dim_date", "date_key")
        dq.fk(f, "employee_key", "dim_employee", "employee_key")
        dq.fk(f, "department_key", "dim_department", "department_key")
    dq.fk("fact_recruitment", "open_date_key", "dim_date", "date_key")
    dq.fk("fact_recruitment", "filled_date_key", "dim_date", "date_key", nullable=True)
    dq.fk("fact_training", "course_key", "dim_course", "course_key")

    # Kelengkapan
    dq.not_null("dim_employee", "hire_date")
    dq.not_null("dim_employee", "birth_date", severity="WARNING")
    dq.not_null("dim_employee", "email", severity="WARNING")
    dq.custom("UNKNOWN_DEPARTMENT", "dim_employee", "WARNING", t["dim_employee"]["current_department"].isna())
    dq.custom("UNKNOWN_LOCATION", "dim_employee", "WARNING", t["dim_employee"]["current_location"].isna())

    # Validitas & logika bisnis
    e = t["dim_employee"]
    dq.custom("TERM_BEFORE_HIRE", "dim_employee", "CRITICAL",
              pd.to_datetime(e["termination_date"]) < pd.to_datetime(e["hire_date"]))
    dq.in_range("dim_employee", "age", 17, 70)
    dq.in_range("fact_performance", "rating", 1, 5, "CRITICAL")
    dq.in_range("fact_engagement", "enps_score", 0, 10, "CRITICAL")
    dq.in_range("fact_attendance", "overtime_hours", 0, 8)
    dq.in_range("fact_attendance", "work_hours", 0, 16)
    p = t["fact_payroll"]
    recon = (p["base_salary"] + p["allowance"] + p["overtime_pay"] + p["bonus"] + p["thr"] - p["gross_pay"]).abs() > 5
    dq.custom("RECON(gross=komponen)", "fact_payroll", "CRITICAL", recon, "toleransi pembulatan Rp5")
    net = (p["gross_pay"] - p["bpjs_employee"] - p["pph21"] - p["net_pay"]).abs() > 5
    dq.custom("RECON(net=gross-potongan)", "fact_payroll", "CRITICAL", net)
    dq.in_range("fact_payroll", "base_salary", 1_000_000, 100_000_000)
    r = t["fact_recruitment"]
    dq.custom("FILLED_WITHOUT_DATE", "fact_recruitment", "WARNING", (r["is_filled"] == 1) & r["filled_date_key"].isna())
    dq.custom("OFFERS_ACCEPTED>OFFERS", "fact_recruitment", "WARNING", r["offers_accepted"] > r["offers_made"])

    # Rekonsiliasi antar tabel: headcount akhir 2025 = karyawan aktif di dim_employee
    hc_end = t["fact_headcount_monthly"].query("date_key == 20251231")["employee_key"].nunique()
    active = (e["employee_status"] == "Active").sum()
    dq.custom("RECON(headcount=active)", "fact_headcount_monthly", "CRITICAL", [hc_end != active],
              f"snapshot={hc_end}, active={active}")
    return dq
