"""
config.py - Konfigurasi terpusat pipeline ETL.

Ganti database cukup lewat environment variable HR_DB_URL, contoh:
  SQLite (default) : sqlite:///data/warehouse/hr_dwh.db
  PostgreSQL       : postgresql+psycopg2://user:pass@localhost:5432/hr_dwh
  SQL Server       : mssql+pyodbc://user:pass@localhost/hr_dwh?driver=ODBC+Driver+17+for+SQL+Server
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
WAREHOUSE_DIR = ROOT / "data" / "warehouse"
EXPORT_DIR = WAREHOUSE_DIR / "csv"          # salinan CSV tiap tabel DWH (opsi koneksi Power BI tanpa driver)
LOG_DIR = ROOT / "logs"
SQL_DIR = ROOT / "sql"

for d in (WAREHOUSE_DIR, EXPORT_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

#DB_URL = os.getenv("HR_DB_URL", f"sqlite:///{(WAREHOUSE_DIR / 'hr_dwh.db').as_posix()}")
DB_URL = os.getenv("HR_DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5434/hr_dwh")

# Periode analisis (dim_date dibuat mencakup rentang ini)
DATE_START = "2022-01-01"      # dim_date mulai 2022: ada lowongan dibuka akhir 2022
ANALYSIS_START = "2023-01-01"  # awal periode analisis (event hire/termination)
DATE_END = "2026-12-31"
SNAPSHOT_START = "2022-12-31"   # snapshot pertama = posisi awal 2023 (untuk retention rate)
SNAPSHOT_END = "2025-12-31"     # snapshot terakhir (tanggal cut-off data)
AS_OF_DATE = "2025-12-31"       # tanggal acuan hitung umur & masa kerja karyawan aktif

EXPORT_CSV = os.getenv("HR_EXPORT_CSV", "1") == "1"

# Nama file sumber
SOURCES = {
    "employees": "employees.csv",
    "departments": "departments.xlsx",
    "positions": "positions.csv",
    "locations": "locations.csv",
    "attendance": "attendance.csv",
    "payroll": "payroll.csv",
    "performance": "performance_reviews.csv",
    "engagement": "engagement_survey.csv",
    "training": "training_records.json",
    "recruitment": "recruitment.xlsx",
    "kpi_targets": "kpi_targets.csv",
    "holidays": "public_holidays.csv",
}
