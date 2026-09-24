# HR Analytics BI Project — PT Nusantara Digital Solusi

Project Business Intelligence end-to-end: **10+ sumber data kotor → ETL Python → Data Warehouse (star schema) → Dashboard Power BI**.
Periode data: Jan 2023 – Des 2025 · ±860 karyawan (576 aktif per 31 Des 2025) · 8 departemen · 6 kota.

## Quick start

```bash
# 1. Siapkan environment
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt

# 2. (Opsional) buat ulang dataset mentah — data/raw sudah tersedia
python scripts/generate_data.py

# 3. Jalankan pipeline ETL
python etl/pipeline.py
```

Hasil:

| Output | Lokasi |
| --- | --- |
| Database warehouse (SQLite) | `data/warehouse/hr_dwh.db` |
| Salinan CSV tiap tabel DWH | `data/warehouse/csv/` |
| Log ETL | `logs/etl_*.log` |
| Audit (DQ, reject, run log) | tabel `etl_dq_results`, `etl_rejected_rows`, `etl_run_log` |

Pakai PostgreSQL / SQL Server: set environment variable `HR_DB_URL` (contoh ada di `etl/config.py`).

## Struktur folder

```
hr-analytics-bi/
├── data/raw/              # 12 file sumber (CSV, XLSX, JSON) — sengaja kotor
├── data/warehouse/        # hasil ETL (dibuat otomatis)
├── scripts/generate_data.py
├── etl/
│   ├── config.py          # path, koneksi DB, periode
│   ├── extract.py         # [1] baca sumber -> staging (stg_*)
│   ├── transform.py       # [2] cleaning + bentuk dimensi & fakta
│   ├── data_quality.py    # [2b] 75 aturan kualitas data (quality gate)
│   ├── load.py            # [3] buat skema + load DWH + export CSV
│   └── pipeline.py        # orkestrator + logging
├── sql/
│   ├── schema.sql         # DDL star schema
│   ├── views.sql          # view analitik
│   └── validation_queries.sql  # angka acuan untuk cek DAX
└── powerbi/
    ├── DAX_measures.dax   # 90 measure siap pakai
    ├── hr_theme.json      # tema warna dashboard
    └── dashboard_blueprint.md
```

## Star schema

- **Dimensi:** `dim_date`, `dim_employee`, `dim_department`, `dim_position`, `dim_location`, `dim_course`
- **Fakta:** `fact_headcount_monthly` (snapshot), `fact_employee_movement`, `fact_attendance`, `fact_payroll`,
  `fact_performance`, `fact_engagement`, `fact_training`, `fact_recruitment`
- **Target:** `kpi_target` (disconnected table)

Panduan lengkap langkah demi langkah ada di dokumen panduan project.
