"""
transform.py - TAHAP 2: TRANSFORM
Membersihkan data staging dan membentuk tabel star schema (dimensi + fakta).

Aturan pembersihan utama (lihat juga panduan):
  T01 Trim spasi & rapikan kapitalisasi teks (nama, status, kota)
  T02 Standarisasi kategori (gender, status absensi, lokasi, departemen)
  T03 Parsing tanggal multi-format (YYYY-MM-DD, DD/MM/YYYY, DD-Mon-YYYY, Mon-YYYY, MM/YYYY)
  T04 Parsing uang ("Rp 7.500.000", "7,500,000.00") -> angka
  T05 Hapus duplikat berdasarkan business key
  T06 Validasi rentang nilai (tanggal lahir, eNPS 0-10, lembur >= 0)
  T07 Perbaikan logis (check-in/out tertukar, allowance kosong diturunkan dari gross)
  T08 Record yatim (ID tidak ada di master) -> ditolak & dicatat di etl_rejected_rows
  T09 Surrogate key + anggota "Unknown" (-1) di dimensi
  T10 Kolom turunan (umur, masa kerja, band, flag KPI)
"""
from __future__ import annotations

import logging
import re

import numpy as np
import pandas as pd

from config import ANALYSIS_START, AS_OF_DATE, DATE_END, DATE_START, SNAPSHOT_END, SNAPSHOT_START

log = logging.getLogger("etl.transform")
AS_OF = pd.Timestamp(AS_OF_DATE)


# ==========================================================================
# Helper umum
# ==========================================================================
class RejectLog:
    """Menampung baris yang ditolak supaya bisa diaudit (tidak hilang diam-diam)."""

    def __init__(self):
        self.rows: list[pd.DataFrame] = []

    def add(self, source: str, reason: str, df: pd.DataFrame) -> None:
        if df.empty:
            return
        cols = [c for c in df.columns if not c.startswith("_")]
        out = pd.DataFrame({
            "source_table": source,
            "reason": reason,
            "record": df[cols].astype(str).apply(lambda r: "|".join(f"{k}={v}" for k, v in r.items()), axis=1),
        })
        self.rows.append(out)
        log.warning("  [REJECT] %-12s %-35s %6d baris", source, reason, len(df))

    def frame(self) -> pd.DataFrame:
        if not self.rows:
            return pd.DataFrame(columns=["source_table", "reason", "record"])
        return pd.concat(self.rows, ignore_index=True)


def clean_text(s: pd.Series) -> pd.Series:
    """T01: trim & rapikan spasi ganda."""
    return s.astype("object").where(s.notna(), None).map(
        lambda v: re.sub(r"\s+", " ", str(v)).strip() if v is not None else None)


def parse_date(s: pd.Series, formats=("%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y")) -> pd.Series:
    """T03: coba beberapa format secara berurutan; yang gagal semua -> NaT."""
    s = clean_text(s)
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for fmt in formats:
        mask = out.isna() & s.notna()
        if not mask.any():
            break
        out.loc[mask] = pd.to_datetime(s[mask], format=fmt, errors="coerce")
    return out


def parse_money(s: pd.Series) -> pd.Series:
    """T04: 'Rp 7.500.000' | '7,500,000.00' | '7500000' -> 7500000.0"""
    def _one(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return np.nan
        v = str(v).strip()
        if v.upper().startswith("RP"):                 # format Indonesia: titik = ribuan
            v = v[2:].strip().replace(".", "").replace(",", ".")
        else:                                          # format US: koma = ribuan
            v = v.replace(",", "")
        try:
            return float(v)
        except ValueError:
            return np.nan
    return s.map(_one).astype(float)


def to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def date_key(s: pd.Series) -> pd.Series:
    """Tanggal -> integer YYYYMMDD (kunci relasi ke dim_date)."""
    return (s.dt.year * 10000 + s.dt.month * 100 + s.dt.day).astype("Int64")


def add_unknown(df: pd.DataFrame, key: str, code_col: str) -> pd.DataFrame:
    """T09: anggota -1 'Unknown' agar fakta tidak pernah kehilangan relasi."""
    row = {c: None for c in df.columns}
    row[key] = -1
    row[code_col] = "UNK"
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]) and c not in (key, code_col):
            row[c] = "Unknown"
    return pd.concat([pd.DataFrame([row]), df], ignore_index=True)


# ==========================================================================
# DIMENSI
# ==========================================================================
def build_dim_date(holidays: pd.DataFrame) -> pd.DataFrame:
    hol = set(parse_date(holidays["holiday_date"]).dropna())
    d = pd.DataFrame({"date": pd.date_range(DATE_START, DATE_END, freq="D")})
    d["date_key"] = date_key(d["date"])
    d["year"] = d["date"].dt.year
    d["quarter"] = d["date"].dt.quarter
    d["quarter_label"] = "Q" + d["quarter"].astype(str)
    d["month"] = d["date"].dt.month
    bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
             "September", "Oktober", "November", "Desember"]
    d["month_name"] = d["month"].map(lambda m: bulan[m - 1])
    d["month_short"] = d["date"].dt.strftime("%b")
    d["year_month"] = d["year"] * 100 + d["month"]
    d["year_month_label"] = d["date"].dt.strftime("%b %Y")
    d["week_of_year"] = d["date"].dt.isocalendar().week.astype(int)
    d["day_of_month"] = d["date"].dt.day
    d["day_of_week"] = d["date"].dt.dayofweek + 1               # 1 = Senin
    hari = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    d["day_name"] = d["day_of_week"].map(lambda x: hari[x - 1])
    d["is_weekend"] = (d["day_of_week"] >= 6).astype(int)
    d["is_holiday"] = d["date"].isin(hol).astype(int)
    d["is_working_day"] = ((d["is_weekend"] == 0) & (d["is_holiday"] == 0)).astype(int)
    d["is_month_end"] = d["date"].dt.is_month_end.astype(int)
    d["date"] = d["date"].dt.date
    return d[["date_key"] + [c for c in d.columns if c != "date_key"]]


def build_dim_department(raw: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame({
        "department_code": clean_text(raw["Dept Code"]).str.upper(),
        "department_name": clean_text(raw["Department Name"]),
        "division": clean_text(raw["Division"]),
        "head_of_department": clean_text(raw["Head of Department"]),
        "cost_center": clean_text(raw["Cost Center"]),
    }).drop_duplicates("department_code").reset_index(drop=True)
    df.insert(0, "department_key", range(1, len(df) + 1))
    return add_unknown(df, "department_key", "department_code")


def build_dim_position(raw: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame({
        "position_code": clean_text(raw["position_code"]).str.upper(),
        "position_title": clean_text(raw["position_title"]),
        "job_family": clean_text(raw["job_family"]),
        "job_level": clean_text(raw["job_level"]),
        "level_name": clean_text(raw["level_name"]),
        "grade": to_num(raw["grade"]).astype("Int64"),
        "salary_min": to_num(raw["salary_min"]),
        "salary_max": to_num(raw["salary_max"]),
    }).drop_duplicates("position_code").reset_index(drop=True)
    df["salary_mid"] = (df["salary_min"] + df["salary_max"]) / 2
    df.insert(0, "position_key", range(1, len(df) + 1))
    return add_unknown(df, "position_key", "position_code")


def build_dim_location(raw: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame({
        "location_code": clean_text(raw["location_code"]).str.upper(),
        "city": clean_text(raw["city"]),
        "province": clean_text(raw["province"]),
        "region": clean_text(raw["region"]),
        "office_type": clean_text(raw["office_type"]),
    }).drop_duplicates("location_code").reset_index(drop=True)
    df.insert(0, "location_key", range(1, len(df) + 1))
    return add_unknown(df, "location_key", "location_code")


GENDER_MAP = {"m": "Male", "male": "Male", "l": "Male", "laki-laki": "Male", "pria": "Male",
              "f": "Female", "female": "Female", "p": "Female", "perempuan": "Female", "wanita": "Female"}
LOCATION_ALIAS = {"dki jakarta": "JKT", "jakarta selatan": "JKT", "jogja": "YGY", "yogya": "YGY", "makasar": "MKS"}


def _age_band(a):
    if pd.isna(a): return "Unknown"
    if a < 25: return "< 25"
    if a < 35: return "25-34"
    if a < 45: return "35-44"
    if a < 55: return "45-54"
    return "55+"


def _generation(y):
    if pd.isna(y): return "Unknown"
    if y >= 1997: return "Gen Z"
    if y >= 1981: return "Millennial"
    if y >= 1965: return "Gen X"
    return "Baby Boomer"


def _tenure_band(t):
    if pd.isna(t): return "Unknown"
    if t < 1: return "< 1 tahun"
    if t < 3: return "1-2 tahun"
    if t < 6: return "3-5 tahun"
    if t < 11: return "6-10 tahun"
    return "> 10 tahun"


def build_dim_employee(raw: pd.DataFrame, dept: pd.DataFrame, pos: pd.DataFrame, loc: pd.DataFrame):
    e = pd.DataFrame({
        "employee_id": clean_text(raw["employee_id"]).str.upper(),
        "full_name": clean_text(raw["full_name"]).str.title(),
        "gender": clean_text(raw["gender"]).str.lower().map(GENDER_MAP).fillna("Unknown"),
        "birth_date": parse_date(raw["birth_date"]),
        "marital_status": clean_text(raw["marital_status"]).str.title(),
        "education": clean_text(raw["education"]),
        "email": clean_text(raw["email"]).str.lower(),
        "department_raw": clean_text(raw["department"]),
        "position_code": clean_text(raw["position_code"]).str.upper(),
        "location_raw": clean_text(raw["location"]),
        "employment_type": clean_text(raw["employment_type"]).str.title(),
        "hire_date": parse_date(raw["hire_date"]),
        "termination_date": parse_date(raw["termination_date"]),
        "termination_type": clean_text(raw["termination_type"]),
        "termination_reason": clean_text(raw["termination_reason"]),
        "monthly_salary": parse_money(raw["monthly_salary"]),
    })
    # T05 duplikat
    n0 = len(e)
    e = e.drop_duplicates("employee_id", keep="last").reset_index(drop=True)
    log.info("  employees: %d duplikat dihapus", n0 - len(e))

    # T02 departemen: bisa berupa kode ('ITD', 'itd') atau nama ('Information Technology')
    name2code = {n.lower(): c for c, n in zip(dept["department_code"], dept["department_name"])}
    codes = set(dept["department_code"])
    e["department_code"] = e["department_raw"].map(
        lambda v: v.upper() if v and v.upper() in codes else name2code.get(str(v).lower(), "UNK"))
    # T02 lokasi: variasi penulisan -> kode lokasi
    city2code = {c.lower(): k for k, c in zip(loc["location_code"], loc["city"])}
    city2code.update({k.lower(): k for k in loc["location_code"]})
    city2code.update(LOCATION_ALIAS)
    e["location_code"] = e["location_raw"].str.lower().map(city2code).fillna("UNK")

    # T06 validasi tanggal lahir (umur saat masuk harus 17-65 tahun)
    age_hire = (e["hire_date"] - e["birth_date"]).dt.days / 365.25
    bad_birth = e["birth_date"].notna() & ~age_hire.between(17, 65)
    e["dq_flag"] = np.where(e["birth_date"].isna() | bad_birth, "INVALID_BIRTH_DATE", None)
    e.loc[bad_birth, "birth_date"] = pd.NaT
    log.info("  employees: %d tanggal lahir tidak valid -> NULL + dq_flag", int(e["dq_flag"].notna().sum()))

    # T10 kolom turunan
    ref = e["termination_date"].fillna(AS_OF).clip(upper=AS_OF)
    e["employee_status"] = np.where(e["termination_date"].notna() & (e["termination_date"] <= AS_OF), "Terminated", "Active")
    e["age"] = np.floor((ref - e["birth_date"]).dt.days / 365.25).astype("Int64")
    e["age_band"] = e["age"].map(_age_band)
    e["generation"] = e["birth_date"].dt.year.map(_generation)
    e["tenure_years"] = ((ref - e["hire_date"]).dt.days / 365.25).round(2)
    e["tenure_band"] = e["tenure_years"].map(_tenure_band)
    e["hire_year"] = e["hire_date"].dt.year.astype("Int64")
    e["termination_type"] = e["termination_type"].replace({"": None})
    e["termination_reason"] = e["termination_reason"].replace({"": None})

    # label atribut saat ini (untuk tabel detail karyawan)
    e = e.merge(dept[["department_code", "department_key", "department_name"]], on="department_code", how="left")
    e = e.merge(pos[["position_code", "position_key", "position_title", "job_level"]], on="position_code", how="left")
    e = e.merge(loc[["location_code", "location_key", "city"]], on="location_code", how="left")
    for k in ("department_key", "position_key", "location_key"):
        e[k] = e[k].fillna(-1).astype(int)

    e = e.sort_values("employee_id").reset_index(drop=True)
    e.insert(0, "employee_key", range(1, len(e) + 1))

    lookup = e[["employee_id", "employee_key", "department_key", "position_key", "location_key",
                "hire_date", "termination_date", "birth_date", "monthly_salary", "termination_type",
                "termination_reason"]].copy()
    dim = e.rename(columns={"department_name": "current_department", "position_title": "current_position",
                            "city": "current_location"})[[
        "employee_key", "employee_id", "full_name", "gender", "birth_date", "age", "age_band", "generation",
        "marital_status", "education", "email", "employment_type", "hire_date", "hire_year",
        "termination_date", "termination_type", "termination_reason", "employee_status", "tenure_years",
        "tenure_band", "current_department", "current_position", "job_level", "current_location",
        "monthly_salary", "dq_flag"]].copy()
    for c in ("birth_date", "hire_date", "termination_date"):
        dim[c] = dim[c].dt.date
    return dim, lookup


def build_dim_course(tr: pd.DataFrame) -> pd.DataFrame:
    c = tr.groupby("course_code").agg(
        course_name=("course_name", "first"), category=("course_category", "first"),
        provider=("course_provider", "first"),
        standard_hours=("duration_hours", lambda s: s.mode().iloc[0] if not s.mode().empty else np.nan),
    ).reset_index()
    c.insert(0, "course_key", range(1, len(c) + 1))
    return add_unknown(c, "course_key", "course_code")


# ==========================================================================
# Helper fakta
# ==========================================================================
def attach_employee(df: pd.DataFrame, lookup: pd.DataFrame, source: str, rej: RejectLog,
                    cols=("employee_key", "department_key", "position_key", "location_key")) -> pd.DataFrame:
    """T08: gabungkan ke dim_employee; ID yang tidak dikenal ditolak."""
    df = df.merge(lookup[["employee_id", *cols]], on="employee_id", how="left")
    orphan = df["employee_key"].isna()
    rej.add(source, "ORPHAN_EMPLOYEE_ID", df[orphan])
    df = df[~orphan].copy()
    for c in cols:
        df[c] = df[c].astype(int)
    return df


# ==========================================================================
# FAKTA
# ==========================================================================
ATT_STATUS = {"present": "Present", "hadir": "Present", "late": "Late", "terlambat": "Late",
              "sick": "Sick", "sakit": "Sick", "absent": "Absent", "alpha": "Absent", "mangkir": "Absent",
              "leave": "Leave", "cuti": "Leave", "annual leave": "Leave",
              "wfh": "WFH", "work from home": "WFH"}


def _hhmm_to_min(s: pd.Series) -> pd.Series:
    parts = s.fillna("").str.extract(r"^(\d{1,2}):(\d{2})")
    return to_num(parts[0]) * 60 + to_num(parts[1])


def build_fact_attendance(raw: pd.DataFrame, lookup: pd.DataFrame, rej: RejectLog) -> pd.DataFrame:
    a = pd.DataFrame({
        "employee_id": clean_text(raw["employee_id"]).str.upper(),
        "work_date": parse_date(raw["work_date"], ("%Y-%m-%d", "%d/%m/%Y")),
        "status": clean_text(raw["status"]).str.lower().map(ATT_STATUS),
        "cin": _hhmm_to_min(raw["check_in"]),
        "cout": _hhmm_to_min(raw["check_out"]),
        "overtime_hours": to_num(raw["overtime_hours"]).fillna(0),
    })
    rej.add("attendance", "UNPARSEABLE_DATE_OR_STATUS", raw[a["work_date"].isna() | a["status"].isna()])
    a = a[a["work_date"].notna() & a["status"].notna()]
    n0 = len(a)
    a = a.drop_duplicates(["employee_id", "work_date"], keep="first")
    log.info("  attendance: %d duplikat (employee_id + tanggal) dihapus", n0 - len(a))
    a = attach_employee(a, lookup, "attendance", rej, ("employee_key", "department_key", "location_key"))

    swap = a["cin"].notna() & a["cout"].notna() & (a["cout"] < a["cin"])        # T07
    a.loc[swap, ["cin", "cout"]] = a.loc[swap, ["cout", "cin"]].values
    log.info("  attendance: %d check-in/out tertukar diperbaiki", int(swap.sum()))
    neg = a["overtime_hours"] < 0                                                # T06
    a.loc[neg, "overtime_hours"] = 0
    log.info("  attendance: %d lembur negatif di-set 0", int(neg.sum()))

    a["date_key"] = date_key(a["work_date"])
    a["is_present"] = a["status"].isin(["Present", "Late", "WFH"]).astype(int)
    a["is_late"] = (a["status"] == "Late").astype(int)
    a["is_sick"] = (a["status"] == "Sick").astype(int)
    a["is_absent_unplanned"] = a["status"].isin(["Sick", "Absent"]).astype(int)
    a["is_leave"] = (a["status"] == "Leave").astype(int)
    a["is_wfh"] = (a["status"] == "WFH").astype(int)
    a["late_minutes"] = np.where(a["is_late"] == 1, (a["cin"] - 8 * 60).clip(lower=0), 0)
    a["work_hours"] = np.where(a["is_present"] == 1, ((a["cout"] - a["cin"]) / 60 - 1).clip(lower=0).round(2), 0)
    fmt = lambda m: m.map(lambda x: None if pd.isna(x) else f"{int(x // 60):02d}:{int(x % 60):02d}")
    a["check_in"], a["check_out"] = fmt(a["cin"]), fmt(a["cout"])
    a = a.sort_values(["work_date", "employee_key"]).reset_index(drop=True)
    a.insert(0, "attendance_key", range(1, len(a) + 1))
    return a[["attendance_key", "date_key", "employee_key", "department_key", "location_key", "status",
              "check_in", "check_out", "work_hours", "late_minutes", "overtime_hours", "is_present",
              "is_late", "is_sick", "is_absent_unplanned", "is_leave", "is_wfh"]]


def build_fact_payroll(raw: pd.DataFrame, lookup: pd.DataFrame, rej: RejectLog) -> pd.DataFrame:
    p = pd.DataFrame({
        "payroll_id": clean_text(raw["payroll_id"]),
        "employee_id": clean_text(raw["employee_id"]).str.upper(),
        "period": parse_date(raw["period"], ("%Y-%m", "%b-%Y", "%m/%Y")),
        "base_salary": parse_money(raw["base_salary"]),
    })
    for c in ("allowance", "overtime_hours", "overtime_pay", "bonus", "thr", "gross_pay",
              "bpjs_employee", "bpjs_company", "pph21", "net_pay"):
        p[c] = to_num(raw[c])
    n0 = len(p)
    p = p.drop_duplicates("payroll_id")
    log.info("  payroll: %d duplikat payroll_id dihapus", n0 - len(p))
    miss = p["allowance"].isna()                                                  # T07
    p.loc[miss, "allowance"] = p["gross_pay"] - p["base_salary"] - p["overtime_pay"] - p["bonus"] - p["thr"]
    log.info("  payroll: %d allowance kosong diturunkan dari gross_pay", int(miss.sum()))
    rej.add("payroll", "UNPARSEABLE_PERIOD", p[p["period"].isna()])
    p = p[p["period"].notna()]
    p = attach_employee(p, lookup, "payroll", rej)
    p["period_end"] = p["period"] + pd.offsets.MonthEnd(0)
    p["date_key"] = date_key(p["period_end"])
    p["total_labor_cost"] = p["gross_pay"] + p["bpjs_company"]
    p = p.sort_values(["date_key", "employee_key"]).reset_index(drop=True)
    p.insert(0, "payroll_key", range(1, len(p) + 1))
    return p[["payroll_key", "payroll_id", "date_key", "employee_key", "department_key", "position_key",
              "location_key", "base_salary", "allowance", "overtime_hours", "overtime_pay", "bonus", "thr",
              "gross_pay", "bpjs_employee", "bpjs_company", "pph21", "net_pay", "total_labor_cost"]]


RATING_LABEL = {1: "1 - Poor", 2: "2 - Below Expectation", 3: "3 - Meets Expectation",
                4: "4 - Exceeds Expectation", 5: "5 - Outstanding"}


def build_fact_performance(raw: pd.DataFrame, lookup: pd.DataFrame, rej: RejectLog) -> pd.DataFrame:
    p = pd.DataFrame({
        "review_id": clean_text(raw["review_id"]),
        "employee_id": clean_text(raw["employee_id"]).str.upper(),
        "review_year": to_num(raw["review_year"]).astype("Int64"),
        "review_date": parse_date(raw["review_date"]),
        "rating": to_num(clean_text(raw["rating"]).str.extract(r"^(\d)")[0]),   # '4 - Exceeds' -> 4
        "goal_achievement_pct": to_num(raw["goal_achievement_pct"]),
        "competency_score": to_num(raw["competency_score"]),
        "calibrated": clean_text(raw["calibrated"]),
    }).drop_duplicates("review_id")
    rej.add("performance", "MISSING_RATING", p[p["rating"].isna() | ~p["rating"].between(1, 5)])
    p = p[p["rating"].between(1, 5)].copy()
    p["rating"] = p["rating"].astype(int)
    p = attach_employee(p, lookup, "performance", rej)
    p["rating_label"] = p["rating"].map(RATING_LABEL)
    p["is_high_performer"] = (p["rating"] >= 4).astype(int)
    p["is_low_performer"] = (p["rating"] <= 2).astype(int)
    p["date_key"] = date_key(p["review_date"])
    p = p.sort_values(["review_year", "employee_key"]).reset_index(drop=True)
    p.insert(0, "performance_key", range(1, len(p) + 1))
    return p[["performance_key", "review_id", "date_key", "employee_key", "department_key", "position_key",
              "location_key", "review_year", "rating", "rating_label", "goal_achievement_pct",
              "competency_score", "is_high_performer", "is_low_performer", "calibrated"]]


def build_fact_engagement(raw: pd.DataFrame, lookup: pd.DataFrame, rej: RejectLog) -> pd.DataFrame:
    g = pd.DataFrame({
        "response_id": clean_text(raw["response_id"]),
        "employee_id": clean_text(raw["employee_id"]).str.upper(),
        "survey_year": to_num(raw["survey_year"]).astype("Int64"),
        "survey_date": parse_date(raw["survey_date"]),
        "enps_score": to_num(raw["enps_score"]),
    })
    for c in ("engagement_score", "work_life_balance", "compensation_satisfaction", "manager_support", "career_growth"):
        g[c] = to_num(raw[c]).where(lambda s: s.between(1, 5))
    g = g.drop_duplicates("response_id")
    bad = ~g["enps_score"].between(0, 10)                                          # T06
    g.loc[bad, "enps_score"] = np.nan
    log.info("  engagement: %d skor eNPS di luar 0-10 -> NULL", int(bad.sum()))
    g = attach_employee(g, lookup, "engagement", rej)
    g["enps_category"] = pd.cut(g["enps_score"], [-1, 6, 8, 10], labels=["Detractor", "Passive", "Promoter"]).astype(object)
    g["enps_category"] = g["enps_category"].fillna("Invalid")
    g["date_key"] = date_key(g["survey_date"])
    g = g.sort_values(["survey_year", "employee_key"]).reset_index(drop=True)
    g.insert(0, "engagement_key", range(1, len(g) + 1))
    return g[["engagement_key", "response_id", "date_key", "employee_key", "department_key", "location_key",
              "survey_year", "engagement_score", "work_life_balance", "compensation_satisfaction",
              "manager_support", "career_growth", "enps_score", "enps_category"]]


def prep_training(raw: pd.DataFrame) -> pd.DataFrame:
    t = pd.DataFrame({
        "training_id": clean_text(raw["training_id"]),
        "employee_id": clean_text(raw["employee_id"]).str.upper(),
        "course_code": clean_text(raw["course_code"]).str.upper(),
        "course_name": clean_text(raw["course_name"]),
        "course_category": clean_text(raw["course_category"]),
        "course_provider": clean_text(raw["course_provider"]),
        "start_date": parse_date(raw["schedule_start_date"]),
        "end_date": parse_date(raw["schedule_end_date"]),
        "duration_hours": to_num(clean_text(raw["duration_hours"]).str.extract(r"(\d+\.?\d*)")[0]),  # '8 jam' -> 8
        "cost_idr": to_num(raw["cost_idr"]).fillna(0),                                # training internal -> 0
        "status": clean_text(raw["status"]).str.title(),
        "post_test_score": to_num(raw["post_test_score"]),
    })
    return t.drop_duplicates("training_id")


def build_fact_training(t: pd.DataFrame, course: pd.DataFrame, lookup: pd.DataFrame, rej: RejectLog) -> pd.DataFrame:
    t = attach_employee(t, lookup, "training", rej, ("employee_key", "department_key", "location_key"))
    t = t.merge(course[["course_code", "course_key"]], on="course_code", how="left")
    t["course_key"] = t["course_key"].fillna(-1).astype(int)
    t["is_completed"] = (t["status"] == "Completed").astype(int)
    t["completed_hours"] = np.where(t["is_completed"] == 1, t["duration_hours"], 0)
    t["date_key"] = date_key(t["start_date"])
    t["end_date_key"] = date_key(t["end_date"])
    t = t.sort_values(["date_key", "employee_key"]).reset_index(drop=True)
    t.insert(0, "training_key", range(1, len(t) + 1))
    return t[["training_key", "training_id", "date_key", "end_date_key", "employee_key", "department_key",
              "location_key", "course_key", "duration_hours", "completed_hours", "cost_idr", "status",
              "is_completed", "post_test_score"]]


def build_fact_recruitment(raw: pd.DataFrame, dept: pd.DataFrame, pos: pd.DataFrame, loc: pd.DataFrame) -> pd.DataFrame:
    r = raw.rename(columns=lambda c: re.sub(r"[^a-z0-9]+", "_", str(c).lower()).strip("_"))
    r = pd.DataFrame({
        "requisition_id": clean_text(r["req_id"]),
        "department_name": clean_text(r["department"]).str.lower(),
        "position_code": clean_text(r["position_code"]).str.upper(),
        "city": clean_text(r["location"]).str.lower(),
        "open_date": pd.to_datetime(clean_text(r["open_date"]), errors="coerce"),
        "filled_date": pd.to_datetime(clean_text(r["filled_date"]), errors="coerce"),
        "status": clean_text(r["status"]).str.title(),
        "source": clean_text(r["source"]),
        "applicants": to_num(r["applicants"]).fillna(0).astype(int),
        "screened": to_num(r["screened"]).fillna(0).astype(int),
        "interviewed": to_num(r["interviewed"]).fillna(0).astype(int),
        "offers_made": to_num(r["offers_made"]).fillna(0).astype(int),
        "offers_accepted": to_num(r["offers_accepted"]).fillna(0).astype(int),
        "recruitment_cost": to_num(r["recruitment_cost_idr"]).fillna(0),
        "hired_employee_id": clean_text(r["hired_employee_id"]),
    }).drop_duplicates("requisition_id")
    d = dept.assign(department_name=dept["department_name"].str.lower())
    r = r.merge(d[["department_name", "department_key"]], on="department_name", how="left")
    r = r.merge(pos[["position_code", "position_key"]], on="position_code", how="left")
    l = loc.assign(city=loc["city"].str.lower())
    r = r.merge(l[["city", "location_key"]], on="city", how="left")
    for k in ("department_key", "position_key", "location_key"):
        r[k] = r[k].fillna(-1).astype(int)
    r["open_date_key"] = date_key(r["open_date"])
    r["filled_date_key"] = date_key(r["filled_date"])
    r["time_to_fill_days"] = (r["filled_date"] - r["open_date"]).dt.days.astype("Int64")
    r["is_filled"] = (r["status"] == "Filled").astype(int)
    r = r.sort_values("open_date").reset_index(drop=True)
    r.insert(0, "requisition_key", range(1, len(r) + 1))
    return r[["requisition_key", "requisition_id", "open_date_key", "filled_date_key", "department_key",
              "position_key", "location_key", "status", "source", "applicants", "screened", "interviewed",
              "offers_made", "offers_accepted", "recruitment_cost", "time_to_fill_days", "is_filled",
              "hired_employee_id"]]


def build_fact_headcount(lookup: pd.DataFrame, pay: pd.DataFrame) -> pd.DataFrame:
    """Snapshot akhir bulan: 1 baris = 1 karyawan AKTIF pada tanggal akhir bulan."""
    months = pd.date_range(SNAPSHOT_START, SNAPSHOT_END, freq="ME")
    snap = lookup.merge(pd.DataFrame({"snapshot_date": months}), how="cross")
    active = (snap["hire_date"] <= snap["snapshot_date"]) & (
        snap["termination_date"].isna() | (snap["termination_date"] > snap["snapshot_date"]))
    snap = snap[active].copy()
    snap["year"] = snap["snapshot_date"].dt.year
    # gaji pokok penuh per tahun = base_salary tertinggi bulan itu di payroll (bulan penuh)
    rate = pay.assign(year=pay["date_key"] // 10000).groupby(["employee_key", "year"])["base_salary"].max().rename("monthly_base_salary")
    snap = snap.merge(rate.reset_index(), on=["employee_key", "year"], how="left")
    snap["monthly_base_salary"] = snap["monthly_base_salary"].fillna(snap["monthly_salary"])
    snap["date_key"] = date_key(snap["snapshot_date"])
    snap["age"] = np.floor((snap["snapshot_date"] - snap["birth_date"]).dt.days / 365.25).astype("Int64")
    snap["tenure_months"] = ((snap["snapshot_date"] - snap["hire_date"]).dt.days / 30.4375).round(1)
    snap["is_new_hire"] = (snap["hire_date"] > snap["snapshot_date"] - pd.offsets.MonthBegin(1) - pd.Timedelta(days=1)).astype(int)
    snap = snap.sort_values(["date_key", "employee_key"]).reset_index(drop=True)
    return snap[["date_key", "employee_key", "department_key", "position_key", "location_key", "age",
                 "tenure_months", "monthly_base_salary", "is_new_hire"]]


def build_fact_movement(lookup: pd.DataFrame, perf: pd.DataFrame) -> pd.DataFrame:
    """Event Hire & Termination dalam periode analisis (flow, bukan snapshot)."""
    start, end = pd.Timestamp(ANALYSIS_START), pd.Timestamp(SNAPSHOT_END)
    base = ["employee_key", "department_key", "position_key", "location_key", "hire_date"]
    h = lookup[lookup["hire_date"].between(start, end)][base].assign(
        movement_type="Hire", event_date=lambda x: x["hire_date"], termination_type=None, termination_reason=None)
    t = lookup[lookup["termination_date"].between(start, end)][base + ["termination_date", "termination_type", "termination_reason"]]
    t = t.assign(movement_type="Termination", event_date=t["termination_date"]).drop(columns="termination_date")
    m = pd.concat([h, t], ignore_index=True)
    m["tenure_months_at_event"] = ((m["event_date"] - m["hire_date"]).dt.days / 30.4375).round(1)
    m["is_voluntary"] = (m["termination_type"] == "Voluntary").astype(int)
    m["is_early_turnover"] = ((m["movement_type"] == "Termination") & (m["tenure_months_at_event"] < 12)).astype(int)
    # regrettable = resign sukarela & rating terakhir >= 4 (kehilangan talenta bagus)
    last_rating = perf.sort_values("review_year").groupby("employee_key")["rating"].last()
    m["last_rating"] = m["employee_key"].map(last_rating)
    m["is_regrettable"] = ((m["is_voluntary"] == 1) & (m["last_rating"] >= 4)).astype(int)
    m.loc[m["movement_type"] == "Hire", "last_rating"] = np.nan
    m["date_key"] = date_key(m["event_date"])
    m = m.sort_values(["date_key", "movement_type"]).reset_index(drop=True)
    m.insert(0, "movement_key", range(1, len(m) + 1))
    return m[["movement_key", "date_key", "employee_key", "department_key", "position_key", "location_key",
              "movement_type", "termination_type", "termination_reason", "tenure_months_at_event",
              "is_voluntary", "is_early_turnover", "is_regrettable", "last_rating"]]


def build_kpi_target(raw: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "kpi_code": clean_text(raw["kpi_code"]), "kpi_name": clean_text(raw["kpi_name"]),
        "year": to_num(raw["year"]).astype(int), "target_value": to_num(raw["target_value"]),
        "direction": clean_text(raw["direction"]), "unit": clean_text(raw["unit"]),
    })


# ==========================================================================
# Orkestrasi transform
# ==========================================================================
def transform_all(raw: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    rej = RejectLog()
    t: dict[str, pd.DataFrame] = {}
    t["dim_date"] = build_dim_date(raw["holidays"])
    t["dim_department"] = build_dim_department(raw["departments"])
    t["dim_position"] = build_dim_position(raw["positions"])
    t["dim_location"] = build_dim_location(raw["locations"])
    t["dim_employee"], lookup = build_dim_employee(raw["employees"], t["dim_department"], t["dim_position"], t["dim_location"])
    tr = prep_training(raw["training"])
    t["dim_course"] = build_dim_course(tr)

    t["fact_payroll"] = build_fact_payroll(raw["payroll"], lookup, rej)
    t["fact_attendance"] = build_fact_attendance(raw["attendance"], lookup, rej)
    t["fact_performance"] = build_fact_performance(raw["performance"], lookup, rej)
    t["fact_engagement"] = build_fact_engagement(raw["engagement"], lookup, rej)
    t["fact_training"] = build_fact_training(tr, t["dim_course"], lookup, rej)
    t["fact_recruitment"] = build_fact_recruitment(raw["recruitment"], t["dim_department"], t["dim_position"], t["dim_location"])
    t["fact_headcount_monthly"] = build_fact_headcount(lookup, t["fact_payroll"])
    t["fact_employee_movement"] = build_fact_movement(lookup, t["fact_performance"])
    t["kpi_target"] = build_kpi_target(raw["kpi_targets"])
    for k, v in t.items():
        log.info("  transform %-24s %8d baris", k, len(v))
    return t, rej.frame()
