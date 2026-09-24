"""
generate_data.py
================
Membuat dataset HR mentah (sintetis, realistis, dan SENGAJA "KOTOR") untuk
latihan ETL + Power BI.

Perusahaan fiktif : PT Nusantara Digital Solusi
Periode           : 1 Jan 2023 - 31 Des 2025
Output            : data/raw/  (10 file: CSV, Excel, JSON)

Pola bisnis yang ditanam (supaya dashboard punya insight):
- Turnover lebih tinggi di Customer Service & Sales, dan pada karyawan < 1 tahun.
- Karyawan dengan engagement rendah / gaji di bawah median band lebih sering resign.
- Absensi naik pada 60 hari terakhir sebelum karyawan resign (early-warning signal).
- Ada gap gaji gender kecil (+/- 3%) untuk dianalisis.
- Sumber rekrutmen berbeda-beda dalam biaya, kecepatan, dan jumlah pelamar.

Jalankan:  python scripts/generate_data.py
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)
random.seed(SEED)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

START = pd.Timestamp("2023-01-01")
END = pd.Timestamp("2025-12-31")
COMPANY = "PT Nusantara Digital Solusi"

# --------------------------------------------------------------------------
# 1. MASTER DATA
# --------------------------------------------------------------------------
# code, name, division, share, turnover_mult, salary_mult, ot_prob, wfh_ok, head
DEPARTMENTS = [
    ("SLS", "Sales", "Commercial", 0.17, 1.35, 1.00, 0.15, False, "Rudi Hartono"),
    ("MKT", "Marketing", "Commercial", 0.08, 1.00, 1.05, 0.10, True, "Maya Sari"),
    ("ITD", "Information Technology", "Technology", 0.16, 1.15, 1.25, 0.25, True, "Andi Wijaya"),
    ("PRD", "Product", "Technology", 0.06, 0.95, 1.20, 0.15, True, "Dewi Lestari"),
    ("FIN", "Finance", "Corporate", 0.07, 0.75, 1.10, 0.12, False, "Hendra Gunawan"),
    ("HRD", "Human Capital", "Corporate", 0.05, 0.70, 1.00, 0.08, False, "Sri Wahyuni"),
    ("OPS", "Operations", "Operations", 0.21, 0.95, 0.90, 0.30, False, "Bambang Susilo"),
    ("CSV", "Customer Service", "Operations", 0.20, 1.60, 0.85, 0.20, False, "Rina Kartika"),
]
DEPT = {d[0]: d for d in DEPARTMENTS}

# level code, level name, share (new hire / initial), salary band (juta IDR)
LEVELS = [
    ("L1", "Staff", 0.55, (6.0, 9.0), 1_200_000),
    ("L2", "Senior Staff", 0.25, (9.0, 14.0), 1_500_000),
    ("L3", "Supervisor", 0.10, (14.0, 20.0), 2_000_000),
    ("L4", "Manager", 0.07, (22.0, 35.0), 3_000_000),
    ("L5", "Senior Manager", 0.03, (38.0, 55.0), 4_000_000),
]
LEVEL = {lv[0]: lv for lv in LEVELS}

TITLES = {
    "SLS": ["Sales Executive", "Senior Sales Executive", "Sales Supervisor", "Sales Manager", "Head of Sales"],
    "MKT": ["Marketing Specialist", "Senior Marketing Specialist", "Marketing Supervisor", "Marketing Manager", "Head of Marketing"],
    "ITD": ["Software Engineer", "Senior Software Engineer", "Tech Lead", "IT Manager", "Head of Technology"],
    "PRD": ["Product Analyst", "Senior Product Analyst", "Product Lead", "Product Manager", "Head of Product"],
    "FIN": ["Accountant", "Senior Accountant", "Finance Supervisor", "Finance Manager", "Head of Finance"],
    "HRD": ["HR Officer", "Senior HR Officer", "HR Supervisor", "HR Manager", "Head of Human Capital"],
    "OPS": ["Operations Staff", "Senior Operations Staff", "Operations Supervisor", "Operations Manager", "Head of Operations"],
    "CSV": ["Customer Service Agent", "Senior CS Agent", "CS Team Leader", "CS Manager", "Head of Customer Experience"],
}

# code, city, province, region, share, office type
LOCATIONS = [
    ("JKT", "Jakarta", "DKI Jakarta", "Jawa", 0.48, "Head Office"),
    ("SBY", "Surabaya", "Jawa Timur", "Jawa", 0.15, "Branch Office"),
    ("BDG", "Bandung", "Jawa Barat", "Jawa", 0.12, "Branch Office"),
    ("YGY", "Yogyakarta", "DI Yogyakarta", "Jawa", 0.08, "Branch Office"),
    ("MDN", "Medan", "Sumatera Utara", "Sumatera", 0.09, "Branch Office"),
    ("MKS", "Makassar", "Sulawesi Selatan", "Sulawesi", 0.08, "Branch Office"),
]
LOC_DIRTY = {  # variasi penulisan lokasi di HRIS (untuk dibersihkan di ETL)
    "JKT": ["Jakarta", "JKT", "DKI Jakarta", "jakarta ", "Jakarta Selatan"],
    "SBY": ["Surabaya", "SBY", "surabaya"],
    "BDG": ["Bandung", "BDG", "bandung "],
    "YGY": ["Yogyakarta", "Jogja", "YOGYAKARTA", "Yogya"],
    "MDN": ["Medan", "MDN", "medan"],
    "MKS": ["Makassar", "MKS", "Makasar"],
}

MALE = ["Agus", "Budi", "Dedi", "Eko", "Fajar", "Gilang", "Hadi", "Irfan", "Joko", "Kurniawan", "Lukman",
        "Muhammad", "Nanda", "Oki", "Putra", "Rizki", "Satria", "Taufik", "Wahyu", "Yoga", "Arif", "Bayu",
        "Dimas", "Fikri", "Hendra", "Ilham", "Reza", "Rian", "Aditya", "Galih", "Teguh", "Yusuf", "Adi", "Rangga"]
FEMALE = ["Ayu", "Bunga", "Citra", "Dewi", "Eka", "Fitri", "Gita", "Indah", "Kartika", "Lestari", "Maya",
          "Nadia", "Putri", "Rina", "Sari", "Tiara", "Wulan", "Yuni", "Anisa", "Dian", "Intan", "Mega",
          "Nurul", "Ratna", "Siti", "Vina", "Amelia", "Laras", "Novi", "Rahma", "Salsabila", "Tari"]
LAST = ["Pratama", "Saputra", "Wijaya", "Santoso", "Hidayat", "Nugroho", "Kusuma", "Setiawan", "Siregar",
        "Nasution", "Lubis", "Simanjuntak", "Harahap", "Wibowo", "Rahman", "Hakim", "Syahputra", "Utami",
        "Permata", "Anggraini", "Purnomo", "Halim", "Tanjung", "Sinaga", "Pangaribuan", "Situmorang",
        "Daeng", "Mappasessu", "Suryadi", "Firmansyah", "Ramadhan", "Maharani", "Susanti", "Hasibuan"]

# Hari libur nasional utama (pendekatan) - dipakai untuk kalender kerja
HOLIDAYS = pd.to_datetime([
    "2023-01-01", "2023-01-22", "2023-02-18", "2023-03-22", "2023-04-07", "2023-04-21", "2023-04-22",
    "2023-04-24", "2023-04-25", "2023-05-01", "2023-05-18", "2023-06-01", "2023-06-04", "2023-06-29",
    "2023-07-19", "2023-08-17", "2023-09-28", "2023-12-25",
    "2024-01-01", "2024-02-08", "2024-02-10", "2024-03-11", "2024-03-29", "2024-04-10", "2024-04-11",
    "2024-04-12", "2024-04-15", "2024-05-01", "2024-05-09", "2024-05-23", "2024-06-01", "2024-06-17",
    "2024-07-07", "2024-08-17", "2024-09-16", "2024-12-25",
    "2025-01-01", "2025-01-27", "2025-01-29", "2025-03-28", "2025-03-31", "2025-04-01", "2025-04-02",
    "2025-04-18", "2025-05-01", "2025-05-12", "2025-05-29", "2025-06-01", "2025-06-06", "2025-06-27",
    "2025-08-17", "2025-09-05", "2025-12-25",
])
ALL_DAYS = pd.date_range(START, END, freq="D")
WORK_DAYS = ALL_DAYS[(ALL_DAYS.dayofweek < 5) & (~ALL_DAYS.isin(HOLIDAYS))]
THR_MONTH = {2023: 4, 2024: 3, 2025: 3}  # bulan pembayaran THR (sebelum Idul Fitri)


# --------------------------------------------------------------------------
# 2. SIMULASI KARYAWAN (hire, attrition, retirement)
# --------------------------------------------------------------------------
def pick(options, probs=None):
    return options[rng.choice(len(options), p=probs)]


def dept_probs():
    p = np.array([d[3] for d in DEPARTMENTS])
    return p / p.sum()


def loc_for_level(level: str) -> str:
    if level in ("L4", "L5") and rng.random() < 0.7:
        return "JKT"
    p = np.array([l[4] for l in LOCATIONS])
    return pick([l[0] for l in LOCATIONS], p / p.sum())


def salary_for(dept: str, level: str, u: float, gender: str) -> int:
    lo, hi = LEVEL[level][3]
    base = (lo + (hi - lo) * u) * DEPT[dept][5] * 1_000_000
    if gender == "F":
        base *= 0.97  # gap gaji gender kecil yang disengaja
    return int(round(base, -4))


employees: list[dict] = []
_next_id = 1


def new_employee(hire_date: pd.Timestamp, dept: str | None = None, level: str | None = None,
                 initial: bool = False) -> dict:
    global _next_id
    dept = dept or pick([d[0] for d in DEPARTMENTS], dept_probs())
    if level is None:
        lv_p = [0.55, 0.25, 0.10, 0.07, 0.03] if initial else [0.72, 0.19, 0.06, 0.025, 0.005]
        level = pick([lv[0] for lv in LEVELS], lv_p)
    gender = "F" if rng.random() < (0.55 if dept in ("HRD", "CSV", "MKT", "FIN") else 0.38) else "M"
    first = pick(FEMALE if gender == "F" else MALE)
    name = f"{first} {pick(LAST)}"
    lvl_idx = int(level[1])
    age_at_hire = float(np.clip(21 + lvl_idx * 3.2 + rng.normal(0, 3.5), 20, 50))
    birth = hire_date - pd.Timedelta(days=int(age_at_hire * 365.25 + rng.integers(0, 365)))
    edu_p = {"L1": [0.15, 0.25, 0.57, 0.03], "L2": [0.05, 0.15, 0.70, 0.10], "L3": [0.02, 0.10, 0.70, 0.18],
             "L4": [0, 0.03, 0.60, 0.37], "L5": [0, 0, 0.45, 0.55]}[level]
    u = float(rng.beta(2, 2))  # posisi gaji dalam band
    perf = float(rng.normal(0, 1))
    eng = 0.35 * perf + 0.5 * (u - 0.5) + float(rng.normal(0, 0.9)) - (0.25 if dept in ("CSV", "SLS") else 0)
    emp = dict(
        employee_id=f"EMP{_next_id:05d}", full_name=name, gender=gender, birth_date=birth,
        marital_status=pick(["Single", "Married", "Divorced"], [0.45, 0.50, 0.05] if age_at_hire < 30 else [0.15, 0.78, 0.07]),
        education=pick(["SMA/SMK", "D3", "S1", "S2"], edu_p),
        hire_date=hire_date, department=dept, level=level, position_code=f"{dept}-{level}",
        location=loc_for_level(level),
        employment_type=pick(["Permanent", "Contract"], [0.8, 0.2] if not initial else [0.9, 0.1]),
        u=u, perf=perf, eng=eng, salary=salary_for(dept, level, u, gender),
        termination_date=pd.NaT, termination_type=None, termination_reason=None,
    )
    _next_id += 1
    employees.append(emp)
    return emp


# populasi awal per 1 Jan 2023
for _ in range(460):
    tenure_years = min(float(rng.exponential(3.8)), 12.9)
    hd = START - pd.Timedelta(days=int(tenure_years * 365) + 1)
    lvl = pick([lv[0] for lv in LEVELS], [0.55, 0.25, 0.10, 0.07, 0.03])
    e = new_employee(hd, level=lvl, initial=True)
    # sedikit karyawan senior yang mendekati usia pensiun (56)
    if rng.random() < 0.03:
        e["birth_date"] = pd.Timestamp(f"{int(rng.integers(1967, 1970))}-{int(rng.integers(1, 13)):02d}-15")

VOL_REASONS = (["Better Compensation", "Career Growth", "Work-Life Balance", "Relocation",
                "Further Study", "Personal / Family", "Management Issues"],
               [0.30, 0.25, 0.14, 0.08, 0.06, 0.09, 0.08])
INVOL_REASONS = (["Poor Performance", "Misconduct", "Restructuring", "Contract End"],
                 [0.45, 0.15, 0.15, 0.25])
YEAR_FACTOR = {2023: 1.00, 2024: 1.12, 2025: 0.82}

months = pd.date_range(START, END, freq="MS")
n0, n_end = 460, 575
requisitions: list[dict] = []
for i, m in enumerate(months):
    m_end = m + pd.offsets.MonthEnd(0)
    active = [e for e in employees if e["hire_date"] <= m_end and pd.isna(e["termination_date"])]
    for e in active:
        if e["hire_date"] > m:  # baru masuk bulan ini
            continue
        age = (m - e["birth_date"]).days / 365.25
        if age >= 56:  # pensiun
            e["termination_date"] = e["birth_date"] + pd.DateOffset(years=56)
            if e["termination_date"] < m:
                e["termination_date"] = m_end
            e["termination_type"], e["termination_reason"] = "Retirement", "Retirement"
            continue
        tenure_m = (m - e["hire_date"]).days / 30.4
        h = 0.0082 * DEPT[e["department"]][4] * YEAR_FACTOR[m.year]
        h *= 1.7 if tenure_m < 12 else (1.2 if tenure_m < 24 else 0.85)
        h *= float(np.exp(-0.45 * e["eng"]))
        h *= 1.5 if e["perf"] < -1 else 1.0
        h *= 1.3 if e["u"] < 0.3 else 1.0
        h *= 1.25 if e["employment_type"] == "Contract" else 1.0
        h *= 0.6 if e["level"] in ("L4", "L5") else 1.0
        if rng.random() < h:
            day = int(rng.integers(0, m_end.day))
            e["termination_date"] = m + pd.Timedelta(days=day)
            p_inv = 0.18 + (0.35 if e["perf"] < -1 else 0) + (0.15 if e["employment_type"] == "Contract" else 0)
            if rng.random() < p_inv:
                e["termination_type"] = "Involuntary"
                reasons, probs = INVOL_REASONS
                if e["employment_type"] != "Contract":
                    probs = [0.6, 0.2, 0.2, 0.0]
                e["termination_reason"] = pick(reasons, probs)
            else:
                e["termination_type"] = "Voluntary"
                reasons, probs = VOL_REASONS
                if e["u"] < 0.3:
                    probs = [0.45, 0.2, 0.1, 0.06, 0.05, 0.07, 0.07]
                e["termination_reason"] = pick(reasons, probs)

    # rekrutmen: kejar target headcount (tumbuh ~ 460 -> 575)
    target = n0 + (n_end - n0) * (i + 1) / len(months)
    still = sum(1 for e in employees if e["hire_date"] <= m_end and
                (pd.isna(e["termination_date"]) or e["termination_date"] > m_end))
    n_hire = max(0, int(round(target - still + rng.normal(0, 2))))
    leavers = [e["department"] for e in active if not pd.isna(e["termination_date"]) and e["termination_date"] >= m]
    for k in range(n_hire):
        dept = leavers[k] if k < len(leavers) and rng.random() < 0.8 else None
        hire_day = m + pd.Timedelta(days=int(rng.integers(0, m_end.day)))
        new_employee(hire_day, dept=dept)

# kenaikan gaji tahunan (Januari) berbasis rating tahun sebelumnya -> disimpan per tahun
def rating_for(e, year):
    r = 3 + 0.9 * e["perf"] + rng.normal(0, 0.6) + (0.1 if year == 2025 else 0)
    return int(np.clip(round(r), 1, 5))

ratings: dict[tuple[str, int], int] = {}
perf_rows = []
for year in (2022, 2023, 2024, 2025):   # 2022 = review terakhir sebelum periode analisis
    ye = pd.Timestamp(f"{year}-12-31")
    for e in employees:
        active_ye = e["hire_date"] <= pd.Timestamp(f"{year}-06-30") and (
            pd.isna(e["termination_date"]) or e["termination_date"] > ye)
        if not active_ye:
            continue
        r = rating_for(e, year)
        ratings[(e["employee_id"], year)] = r
        perf_rows.append(dict(
            review_id=f"PR{year}-{len(perf_rows) + 1:05d}", employee_id=e["employee_id"], review_year=year,
            review_date=(ye - pd.Timedelta(days=int(rng.integers(5, 25)))).strftime("%Y-%m-%d"),
            rating=r, goal_achievement_pct=round(float(np.clip(58 + r * 9 + rng.normal(0, 6), 30, 130)), 1),
            competency_score=round(float(np.clip(2.2 + 0.55 * r + rng.normal(0, 0.3), 1, 5)), 2),
            reviewer=DEPT[e["department"]][8], calibrated=pick(["Yes", "No"], [0.85, 0.15]),
        ))

RAISE = {5: 0.10, 4: 0.07, 3: 0.05, 2: 0.02, 1: 0.0}


def salary_in_year(e, year):
    """Gaji pokok penuh pada tahun tertentu: naik tiap Januari sesuai rating tahun sebelumnya."""
    s = e["salary"]
    for y in range(2024, year + 1):
        if e["hire_date"] < pd.Timestamp(f"{y}-01-01") - pd.Timedelta(days=90):
            s *= 1 + RAISE[ratings.get((e["employee_id"], y - 1), 3)]
    return int(round(s, -4))


# --------------------------------------------------------------------------
# 3. ATTENDANCE (harian) + agregat lembur per bulan
# --------------------------------------------------------------------------
STATUS_LABELS = {  # kode internal -> variasi label dari mesin absensi
    "P": ["Present", "Hadir", "present", "HADIR"],
    "L": ["Late", "Terlambat", "late"],
    "S": ["Sick", "Sakit", "SAKIT"],
    "A": ["Absent", "Alpha", "Mangkir"],
    "C": ["Leave", "Cuti", "Annual Leave"],
    "W": ["WFH", "Work From Home", "wfh"],
}
att_parts = []
ot_monthly: dict[tuple[str, str], float] = {}
wd = WORK_DAYS.values
for e in employees:
    s = max(e["hire_date"], START)
    t = e["termination_date"] if not pd.isna(e["termination_date"]) else END
    days = WORK_DAYS[(WORK_DAYS >= s) & (WORK_DAYS <= t)]
    n = len(days)
    if n == 0:
        continue
    d = DEPT[e["department"]]
    neg = max(0.0, -e["eng"])
    near_exit = np.zeros(n, dtype=bool)
    if not pd.isna(e["termination_date"]) and e["termination_type"] == "Voluntary":
        near_exit = np.asarray(days >= e["termination_date"] - pd.Timedelta(days=60))
    mult = np.where(near_exit, 2.2, 1.0)
    p_sick = 0.017 * mult
    p_abs = 0.003 * (1 + 1.5 * neg) * mult
    p_leave = 0.047 * np.where(near_exit, 1.6, 1.0)
    p_wfh = np.full(n, 0.14 if d[7] else 0.0)
    r = rng.random(n)
    status = np.full(n, "P", dtype=object)
    c1 = p_sick; c2 = c1 + p_abs; c3 = c2 + p_leave; c4 = c3 + p_wfh
    status[r < c1] = "S"
    status[(r >= c1) & (r < c2)] = "A"
    status[(r >= c2) & (r < c3)] = "C"
    status[(r >= c3) & (r < c4)] = "W"
    p_late = 0.045 + 0.05 * neg + (0.02 if e["department"] in ("CSV", "OPS") else 0)
    late = (status == "P") & (rng.random(n) < p_late)
    status[late] = "L"
    works = np.isin(status, ["P", "L", "W"])
    cin = np.where(late, rng.uniform(8 * 60 + 16, 9 * 60 + 40, n), rng.normal(7 * 60 + 50, 9, n))
    ot = np.where(works & (rng.random(n) < d[6]), np.round(rng.uniform(1, 4, n) * 2) / 2, 0.0)
    cout = rng.normal(17 * 60 + 8, 8, n) + ot * 60
    cin_s = np.where(works, [f"{int(x // 60):02d}:{int(x % 60):02d}" for x in cin], "")
    cout_s = np.where(works, [f"{int(x // 60) % 24:02d}:{int(x % 60):02d}" for x in cout], "")
    part = pd.DataFrame({
        "employee_id": e["employee_id"], "work_date": days.strftime("%Y-%m-%d"), "status_code": status,
        "check_in": cin_s, "check_out": cout_s, "overtime_hours": ot,
    })
    att_parts.append(part)
    ym = days.strftime("%Y-%m")
    for k, v in pd.Series(ot).groupby(ym).sum().items():
        ot_monthly[(e["employee_id"], k)] = float(v)

att = pd.concat(att_parts, ignore_index=True)
att["status"] = [random.choice(STATUS_LABELS[c]) for c in att["status_code"]]
att = att.drop(columns="status_code")
# --- kotoran data attendance
idx = att.sample(frac=0.05, random_state=1).index          # format tanggal dd/mm/yyyy
att.loc[idx, "work_date"] = pd.to_datetime(att.loc[idx, "work_date"]).dt.strftime("%d/%m/%Y")
idx = att.sample(frac=0.01, random_state=2).index          # id huruf kecil
att.loc[idx, "employee_id"] = att.loc[idx, "employee_id"].str.lower()
idx = att[att["check_in"] != ""].sample(frac=0.002, random_state=3).index  # check-in/out tertukar
att.loc[idx, ["check_in", "check_out"]] = att.loc[idx, ["check_out", "check_in"]].values
idx = att.sample(frac=0.0005, random_state=4).index        # lembur negatif (salah input)
att.loc[idx, "overtime_hours"] = -1
orph = att.sample(n=300, random_state=5).copy()            # ID yatim (tidak ada di master)
orph["employee_id"] = [f"EMP9{int(x):04d}" for x in rng.integers(0, 9999, len(orph))]
dups = att.sample(frac=0.004, random_state=6)               # duplikat baris
att = pd.concat([att, orph, dups], ignore_index=True).sample(frac=1, random_state=7).reset_index(drop=True)
att.to_csv(RAW / "attendance.csv", index=False)
print(f"attendance.csv          {len(att):>8,} rows")

# --------------------------------------------------------------------------
# 4. PAYROLL (bulanan)
# --------------------------------------------------------------------------
def pph21(gross):
    if gross <= 5_400_000: return 0.0
    if gross <= 10_000_000: return gross * 0.02
    if gross <= 20_000_000: return gross * 0.05
    if gross <= 40_000_000: return gross * 0.10
    return gross * 0.15

pay_rows = []
for e in employees:
    for m in months:
        m_end = m + pd.offsets.MonthEnd(0)
        t = e["termination_date"]
        if e["hire_date"] > m_end or (not pd.isna(t) and t < m):
            continue
        wd_month = WORK_DAYS[(WORK_DAYS >= m) & (WORK_DAYS <= m_end)]
        s = max(e["hire_date"], m); en = min(t, m_end) if not pd.isna(t) else m_end
        worked = ((wd_month >= s) & (wd_month <= en)).sum()
        frac = worked / max(len(wd_month), 1)
        if worked == 0:
            continue
        base_full = salary_in_year(e, m.year)
        base = base_full * frac
        allow = LEVEL[e["level"]][4] * frac
        ot_h = ot_monthly.get((e["employee_id"], m.strftime("%Y-%m")), 0.0)
        ot_pay = ot_h * base_full / 173 * 1.5 if e["level"] in ("L1", "L2", "L3") else 0.0
        bonus = 0.0
        if m.month == 3 and (e["employee_id"], m.year - 1) in ratings:
            bonus = base_full * {5: 3, 4: 2, 3: 1, 2: 0.5, 1: 0}[ratings[(e["employee_id"], m.year - 1)]]
        thr = 0.0
        if m.month == THR_MONTH[m.year]:
            ten_m = (m_end - e["hire_date"]).days / 30.4
            if ten_m >= 1:
                thr = base_full * min(1.0, ten_m / 12)
        gross = base + allow + ot_pay + bonus + thr
        bpjs_emp = base * 0.04
        bpjs_co = base * 0.1024
        tax = pph21(gross)
        pay_rows.append(dict(
            payroll_id=f"PY{m.strftime('%Y%m')}-{e['employee_id'][3:]}", employee_id=e["employee_id"],
            period=m.strftime("%Y-%m"), base_salary=round(base), allowance=round(allow),
            overtime_hours=ot_h, overtime_pay=round(ot_pay), bonus=round(bonus), thr=round(thr),
            gross_pay=round(gross), bpjs_employee=round(bpjs_emp), bpjs_company=round(bpjs_co),
            pph21=round(tax), net_pay=round(gross - bpjs_emp - tax), payment_date=(m_end - pd.Timedelta(days=3)).strftime("%Y-%m-%d"),
        ))
pay = pd.DataFrame(pay_rows)
# --- kotoran data payroll
pay["base_salary"] = pay["base_salary"].astype(object)
pay["period"] = pay["period"].astype(object)
idx = pay.sample(frac=0.04, random_state=11).index
pay.loc[idx, "base_salary"] = ["Rp " + f"{int(v):,}".replace(",", ".") for v in pay.loc[idx, "base_salary"]]
idx = pay.sample(frac=0.06, random_state=12).index
pay.loc[idx, "period"] = pd.to_datetime(pay.loc[idx, "period"]).dt.strftime("%b-%Y")
idx = pay.sample(frac=0.04, random_state=13).index
pay.loc[idx, "period"] = pd.to_datetime(pay.loc[idx, "period"], format="mixed").dt.strftime("%m/%Y")
idx = pay.sample(frac=0.01, random_state=14).index
pay["allowance"] = pay["allowance"].astype(float)
pay.loc[idx, "allowance"] = np.nan
pay = pd.concat([pay, pay.sample(frac=0.003, random_state=15)], ignore_index=True)
pay.to_csv(RAW / "payroll.csv", index=False)
print(f"payroll.csv             {len(pay):>8,} rows")

# --------------------------------------------------------------------------
# 5. PERFORMANCE REVIEWS
# --------------------------------------------------------------------------
perf = pd.DataFrame(perf_rows)
perf["rating"] = perf["rating"].astype(object)
idx = perf.sample(frac=0.02, random_state=21).index
perf.loc[idx, "rating"] = perf.loc[idx, "rating"].map({1: "1 - Poor", 2: "2 - Below", 3: "3 - Meets", 4: "4 - Exceeds", 5: "5 - Outstanding"})
idx = perf.sample(frac=0.005, random_state=22).index
perf.loc[idx, "rating"] = None
perf.to_csv(RAW / "performance_reviews.csv", index=False)
print(f"performance_reviews.csv {len(perf):>8,} rows")

# --------------------------------------------------------------------------
# 6. ENGAGEMENT SURVEY (tahunan, Oktober)
# --------------------------------------------------------------------------
eng_rows = []
for year in (2023, 2024, 2025):
    sd = pd.Timestamp(f"{year}-10-15")
    for e in employees:
        if e["hire_date"] > sd - pd.Timedelta(days=30):
            continue
        if not pd.isna(e["termination_date"]) and e["termination_date"] < sd:
            continue
        if rng.random() > 0.82:  # response rate
            continue
        base = 3.55 + 0.55 * e["eng"] + (0.08 if year == 2025 else (-0.05 if year == 2024 else 0))
        sc = lambda adj=0.0: round(float(np.clip(base + adj + rng.normal(0, 0.4), 1, 5)), 1)
        eng_rows.append(dict(
            response_id=f"ENG{year}-{len(eng_rows) + 1:05d}", employee_id=e["employee_id"], survey_year=year,
            survey_date=(sd + pd.Timedelta(days=int(rng.integers(0, 14)))).strftime("%Y-%m-%d"),
            engagement_score=sc(), work_life_balance=sc(-0.2 if e["department"] in ("OPS", "CSV") else 0.1),
            compensation_satisfaction=sc(-0.4 + 0.6 * (e["u"] - 0.5)), manager_support=sc(0.1),
            career_growth=sc(-0.25), enps_score=int(np.clip(round(7.95 + 1.9 * e["eng"] + rng.normal(0, 1.3)), 0, 10)),
        ))
eng = pd.DataFrame(eng_rows)
idx = eng.sample(frac=0.01, random_state=31).index
eng["enps_score"] = eng["enps_score"].astype(object)
eng.loc[idx, "enps_score"] = 11  # nilai di luar skala 0-10
eng.to_csv(RAW / "engagement_survey.csv", index=False)
print(f"engagement_survey.csv   {len(eng):>8,} rows")

# --------------------------------------------------------------------------
# 7. TRAINING (JSON bersarang dari LMS)
# --------------------------------------------------------------------------
COURSES = [
    ("TRN-C01", "Kode Etik & Anti-Korupsi", "Compliance", "Internal", 4, 0),
    ("TRN-C02", "K3 & Keselamatan Kerja", "Compliance", "Internal", 4, 0),
    ("TRN-C03", "Perlindungan Data Pribadi (UU PDP)", "Compliance", "Internal", 3, 0),
    ("TRN-T01", "Python for Data Analysis", "Technical", "Dicoding", 24, 1_500_000),
    ("TRN-T02", "Cloud Fundamentals (AWS)", "Technical", "AWS Training", 16, 3_500_000),
    ("TRN-T03", "Advanced Excel", "Technical", "Internal", 8, 250_000),
    ("TRN-T04", "Power BI Dashboarding", "Technical", "Microsoft Learn", 16, 2_000_000),
    ("TRN-T05", "Secure Coding Practices", "Technical", "External Vendor", 12, 4_000_000),
    ("TRN-S01", "Effective Communication", "Soft Skills", "Internal", 8, 300_000),
    ("TRN-S02", "Customer Service Excellence", "Soft Skills", "External Vendor", 12, 1_800_000),
    ("TRN-S03", "Negotiation Skills", "Soft Skills", "External Vendor", 12, 2_500_000),
    ("TRN-S04", "Time Management", "Soft Skills", "Internal", 6, 200_000),
    ("TRN-L01", "First-Time Manager Program", "Leadership", "PPM Manajemen", 32, 7_500_000),
    ("TRN-L02", "Coaching & Feedback", "Leadership", "Internal", 8, 500_000),
    ("TRN-L03", "Strategic Leadership", "Leadership", "Prasetiya Mulya", 40, 15_000_000),
    ("TRN-P01", "Product Knowledge Batch", "Product Knowledge", "Internal", 6, 0),
    ("TRN-D01", "Digital Marketing Fundamentals", "Digital", "Google Skillshop", 16, 1_200_000),
    ("TRN-D02", "Agile & Scrum", "Digital", "External Vendor", 16, 3_000_000),
]
FIT = {"ITD": ["TRN-T01", "TRN-T02", "TRN-T05", "TRN-D02"], "PRD": ["TRN-T01", "TRN-T04", "TRN-D02"],
       "MKT": ["TRN-D01", "TRN-T04", "TRN-S03"], "SLS": ["TRN-S03", "TRN-S01", "TRN-P01"],
       "FIN": ["TRN-T03", "TRN-T04"], "HRD": ["TRN-T03", "TRN-S01", "TRN-T04"],
       "OPS": ["TRN-T03", "TRN-S04", "TRN-P01"], "CSV": ["TRN-S02", "TRN-S01", "TRN-P01"]}
CMAP = {c[0]: c for c in COURSES}
tr_records = []
for year in (2023, 2024, 2025):
    for e in employees:
        ys, ye = pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year}-12-31")
        a = max(e["hire_date"], ys); b = min(e["termination_date"], ye) if not pd.isna(e["termination_date"]) else ye
        if a > b:
            continue
        picks = [pick(["TRN-C01", "TRN-C02", "TRN-C03"])]
        picks += list(rng.choice(FIT[e["department"]], size=min(int(rng.poisson(1.1)), len(FIT[e["department"]])), replace=False))
        if e["level"] in ("L3", "L4") and rng.random() < 0.5:
            picks.append(pick(["TRN-L01", "TRN-L02"]))
        if e["level"] == "L5" and rng.random() < 0.4:
            picks.append("TRN-L03")
        if rng.random() < 0.3:
            picks.append(pick(["TRN-S01", "TRN-S04", "TRN-T03", "TRN-D02"]))
        for c in dict.fromkeys(picks):
            span = (b - a).days
            sd = a + pd.Timedelta(days=int(rng.integers(0, max(span, 1))))
            code, cname, cat, prov, hrs, cost = CMAP[c]
            ed = sd + pd.Timedelta(days=int(max(0, hrs // 8 - 1)))
            status = pick(["Completed", "Not Completed"], [0.9, 0.1])
            if ed > END - pd.Timedelta(days=20) and rng.random() < 0.5:
                status = "In Progress"
            tr_records.append({
                "training_id": f"TR{len(tr_records) + 1:06d}",
                "employee": {"id": e["employee_id"], "name": e["full_name"]},
                "course": {"code": code, "name": cname, "category": cat, "provider": prov},
                "schedule": {"start_date": sd.strftime("%Y-%m-%d"), "end_date": ed.strftime("%Y-%m-%d")},
                "duration_hours": f"{hrs} jam" if rng.random() < 0.05 else hrs,
                "cost_idr": None if (cost == 0 and rng.random() < 0.5) else cost,
                "status": status if rng.random() > 0.05 else status.upper(),
                "post_test_score": int(np.clip(rng.normal(82, 8), 55, 100)) if status == "Completed" else None,
            })
with open(RAW / "training_records.json", "w", encoding="utf-8") as f:
    json.dump({"source": "LMS Export", "company": COMPANY, "exported_at": "2026-01-05T08:00:00",
               "total_records": len(tr_records), "records": tr_records}, f, ensure_ascii=False, indent=1)
print(f"training_records.json   {len(tr_records):>8,} rows")

# --------------------------------------------------------------------------
# 8. RECRUITMENT (Excel dengan judul laporan di atas header)
# --------------------------------------------------------------------------
SOURCES = {  # source: (prob, ttf_mult, applicants_mean, cost_fixed, offer_accept)
    "LinkedIn": (0.22, 1.00, 70, 2_500_000, 0.80), "Jobstreet": (0.20, 0.95, 110, 1_800_000, 0.82),
    "Referral": (0.16, 0.75, 12, 3_000_000, 0.92), "Glints": (0.12, 0.90, 85, 1_500_000, 0.80),
    "Kalibrr": (0.08, 0.95, 60, 1_200_000, 0.78), "Campus Hiring": (0.08, 1.10, 150, 4_000_000, 0.85),
    "Headhunter/Agency": (0.07, 0.80, 8, 0, 0.88), "Company Website": (0.07, 1.20, 40, 300_000, 0.75),
}
TTF = {"SLS": 32, "MKT": 38, "ITD": 52, "PRD": 48, "FIN": 40, "HRD": 35, "OPS": 28, "CSV": 22}
src_names = list(SOURCES); src_p = np.array([SOURCES[s][0] for s in src_names]); src_p /= src_p.sum()
req_rows = []
hires = [e for e in employees if e["hire_date"] >= START]


def req_row(dept, level, loc, open_d, fill_d, status, emp_id, salary):
    src = pick(src_names, src_p) if level in ("L1", "L2", "L3") else pick(["LinkedIn", "Headhunter/Agency", "Referral"], [0.35, 0.45, 0.2])
    _, _, app_mean, fixed, acc = SOURCES[src]
    applicants = max(1, int(rng.poisson(app_mean * (0.5 if level in ("L4", "L5") else 1))))
    screened = max(1, int(applicants * rng.uniform(0.2, 0.4)))
    interviewed = max(1, min(screened, int(rng.integers(3, 12))))
    offers_acc = 1 if status == "Filled" else 0
    offers = offers_acc + int(rng.binomial(2, 1 - acc)) if status == "Filled" else int(rng.binomial(1, 0.3))
    cost = fixed + (salary * 2 if src == "Headhunter/Agency" else 0) + int(rng.integers(2, 12)) * 150_000
    return {"Req ID": f"REQ-{len(req_rows) + 1:05d}", "Department": DEPT[dept][1], "Position Code": f"{dept}-{level}",
            "Location": loc, "Open Date": open_d, "Filled Date": fill_d, "Status": status, "Source": src,
            "Applicants": applicants, "Screened": screened, "Interviewed": interviewed, "Offers Made": max(offers, offers_acc),
            "Offers Accepted": offers_acc, "Recruitment Cost (IDR)": int(round(cost, -3)), "Hired Employee ID": emp_id}


for e in sorted(hires, key=lambda x: x["hire_date"]):
    notice = int(rng.integers(7, 31))
    fill = e["hire_date"] - pd.Timedelta(days=notice)
    ttf = max(7, int(rng.gamma(4, TTF[e["department"]] / 4) * (1.5 if e["level"] in ("L4", "L5") else 1)))
    row = req_row(e["department"], e["level"], e["location"], (fill - pd.Timedelta(days=ttf)).date(), fill.date(), "Filled", e["employee_id"], e["salary"])
    row["Location"] = [l[1] for l in LOCATIONS if l[0] == e["location"]][0]
    req_rows.append(row)
for _ in range(45):  # dibatalkan
    dept = pick([d[0] for d in DEPARTMENTS], dept_probs())
    od = START + pd.Timedelta(days=int(rng.integers(0, 1000)))
    req_rows.append(req_row(dept, "L1", "Jakarta", od.date(), None, "Cancelled", None, 7_000_000))
for _ in range(28):  # masih terbuka per akhir 2025
    dept = pick([d[0] for d in DEPARTMENTS], dept_probs())
    od = END - pd.Timedelta(days=int(rng.integers(5, 80)))
    req_rows.append(req_row(dept, pick(["L1", "L2", "L3"]), pick(["Jakarta", "Surabaya", "Bandung"]), od.date(), None, "Open", None, 8_000_000))
req = pd.DataFrame(req_rows).sort_values("Open Date").reset_index(drop=True)
req["Req ID"] = [f"REQ-{i + 1:05d}" for i in range(len(req))]
idx = req.sample(frac=0.05, random_state=41).index
req.loc[idx, "Status"] = req.loc[idx, "Status"].str.lower()
idx = req.sample(frac=0.03, random_state=42).index
req.loc[idx, "Department"] = req.loc[idx, "Department"].str.upper()
with pd.ExcelWriter(RAW / "recruitment.xlsx", engine="openpyxl") as xw:
    pd.DataFrame([[f"Laporan Rekrutmen - {COMPANY}"], ["Periode: Jan 2023 - Des 2025"]]).to_excel(
        xw, sheet_name="Requisitions", header=False, index=False)
    req.to_excel(xw, sheet_name="Requisitions", startrow=3, index=False)
print(f"recruitment.xlsx        {len(req):>8,} rows")

# --------------------------------------------------------------------------
# 9. EMPLOYEES (export HRIS per 31 Des 2025) - paling kotor
# --------------------------------------------------------------------------
GENDER_DIRTY = {"M": ["M", "Male", "L", "Laki-laki", "male", "Pria"], "F": ["F", "Female", "P", "Perempuan", "female", "Wanita"]}
DATE_FMT = ["%Y-%m-%d", "%Y-%m-%d", "%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y"]
emp_rows = []
for e in employees:
    fmt = pick(DATE_FMT)
    name = e["full_name"]
    r = rng.random()
    if r < 0.05: name = name.upper()
    elif r < 0.10: name = "  " + name.lower() + " "
    dept_val = pick([e["department"], e["department"].lower(), DEPT[e["department"]][1]], [0.7, 0.1, 0.2])
    sal = salary_in_year(e, 2025 if pd.isna(e["termination_date"]) else e["termination_date"].year)
    sal_val = pick([str(sal), f"Rp {sal:,}".replace(",", "."), f"{sal:,}.00"], [0.8, 0.12, 0.08])
    email = f"{name.strip().lower().replace(' ', '.')}{e['employee_id'][-3:]}@nusantaradigital.co.id"
    emp_rows.append({
        "employee_id": e["employee_id"], "full_name": name, "gender": pick(GENDER_DIRTY[e["gender"]]),
        "birth_date": e["birth_date"].strftime(fmt), "marital_status": pick([e["marital_status"], e["marital_status"].upper()], [0.9, 0.1]),
        "education": e["education"], "email": email if rng.random() > 0.03 else None,
        "phone": f"+62 8{int(rng.integers(11, 99))}-{int(rng.integers(1000, 9999))}-{int(rng.integers(1000, 9999))}",
        "department": dept_val, "position_code": e["position_code"], "location": pick(LOC_DIRTY[e["location"]]),
        "employment_type": e["employment_type"], "hire_date": e["hire_date"].strftime(fmt),
        "termination_date": "" if pd.isna(e["termination_date"]) else e["termination_date"].strftime(fmt),
        "termination_type": e["termination_type"] or "", "termination_reason": e["termination_reason"] or "",
        "monthly_salary": sal_val,
    })
emp = pd.DataFrame(emp_rows)
# kotoran tambahan: tanggal lahir tidak valid, duplikat
idx = emp.sample(n=6, random_state=51).index
emp.loc[idx, "birth_date"] = ["1900-01-01", "2030-05-12", "", "1900-01-01", "", "31/02/1990"]
emp = pd.concat([emp, emp.sample(n=12, random_state=52)], ignore_index=True)
emp.to_csv(RAW / "employees.csv", index=False)
print(f"employees.csv           {len(emp):>8,} rows  ({len(employees)} karyawan unik)")

# --------------------------------------------------------------------------
# 10. MASTER KECIL: departments.xlsx, positions.csv, locations.csv, kpi_targets.csv
# --------------------------------------------------------------------------
pd.DataFrame([{"Dept Code": d[0], "Department Name": d[1], "Division": d[2], "Head of Department": d[8],
               "Cost Center": f"CC-{100 + i * 10}"} for i, d in enumerate(DEPARTMENTS)]).to_excel(
    RAW / "departments.xlsx", index=False, sheet_name="Departments")
pos_rows = []
for d in DEPARTMENTS:
    for j, lv in enumerate(LEVELS):
        lo, hi = lv[3]
        pos_rows.append({"position_code": f"{d[0]}-{lv[0]}", "position_title": TITLES[d[0]][j], "job_family": d[1],
                         "job_level": lv[0], "level_name": lv[1], "grade": 8 + j * 2,
                         "salary_min": int(lo * d[5] * 1e6), "salary_max": int(hi * d[5] * 1e6)})
pd.DataFrame(pos_rows).to_csv(RAW / "positions.csv", index=False)
pd.DataFrame([{"location_code": l[0], "city": l[1], "province": l[2], "region": l[3], "office_type": l[5]}
              for l in LOCATIONS]).to_csv(RAW / "locations.csv", index=False)
targets = []
for y in (2023, 2024, 2025):
    for code, name, val, direction, unit in [
        ("TURNOVER", "Annual Turnover Rate", 0.15, "lower", "%"), ("VOL_TURNOVER", "Voluntary Turnover Rate", 0.11, "lower", "%"),
        ("ABSENT", "Absenteeism Rate", 0.025, "lower", "%"), ("LATE", "Late Arrival Rate", 0.05, "lower", "%"),
        ("TTF", "Avg Time to Fill (days)", 40, "lower", "days"), ("CPH", "Cost per Hire (IDR)", 4_500_000, "lower", "IDR"),
        ("ENPS", "eNPS", 10 if y == 2023 else 18, "higher", "score"), ("ENGAGE", "Engagement Score", 3.6, "higher", "score"),
        ("TRAIN_HRS", "Training Hours per Employee", 20, "higher", "hours"), ("HEADCOUNT", "Headcount (End of Year)", {2023: 500, 2024: 540, 2025: 580}[y], "higher", "people"),
        ("OFFER_ACC", "Offer Acceptance Rate", 0.80, "higher", "%"), ("HIGH_PERF", "% High Performer (rating 4-5)", 0.30, "higher", "%"),
    ]:
        targets.append({"kpi_code": code, "kpi_name": name, "year": y, "target_value": val, "direction": direction, "unit": unit})
pd.DataFrame(targets).to_csv(RAW / "kpi_targets.csv", index=False)
pd.DataFrame({"holiday_date": HOLIDAYS.strftime("%Y-%m-%d")}).to_csv(RAW / "public_holidays.csv", index=False)
print("departments.xlsx, positions.csv, locations.csv, kpi_targets.csv, public_holidays.csv  OK")
print("Selesai ->", RAW)
