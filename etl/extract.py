"""
extract.py - TAHAP 1: EXTRACT
Membaca semua file sumber APA ADANYA (semua kolom sebagai teks) lalu menyimpan
salinannya ke tabel staging `stg_<nama>` + kolom audit `_source_file` & `_loaded_at`.

Prinsip: tahap extract TIDAK mengubah isi data. Semua pembersihan di transform.py,
sehingga data mentah selalu bisa ditelusuri (audit trail).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

import pandas as pd

from config import RAW_DIR, SOURCES

log = logging.getLogger("etl.extract")


def _read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(RAW_DIR / SOURCES[name], dtype=str, keep_default_na=False, na_values=[""])


def _read_excel(name: str, **kw) -> pd.DataFrame:
    return pd.read_excel(RAW_DIR / SOURCES[name], dtype=str, **kw)


def _read_training() -> pd.DataFrame:
    """JSON dari LMS berbentuk bersarang -> diratakan (flatten) dengan json_normalize."""
    with open(RAW_DIR / SOURCES["training"], encoding="utf-8") as f:
        payload = json.load(f)
    df = pd.json_normalize(payload["records"], sep="_")
    log.info("  training: header JSON total_records=%s", payload.get("total_records"))
    # samakan dengan sumber lain: semua nilai jadi teks, kosong jadi None
    return df.apply(lambda col: col.map(lambda v: None if pd.isna(v) else str(v)))


def extract_all() -> dict[str, pd.DataFrame]:
    readers = {
        "employees": lambda: _read_csv("employees"),
        "departments": lambda: _read_excel("departments", sheet_name="Departments"),
        "positions": lambda: _read_csv("positions"),
        "locations": lambda: _read_csv("locations"),
        "attendance": lambda: _read_csv("attendance"),
        "payroll": lambda: _read_csv("payroll"),
        "performance": lambda: _read_csv("performance"),
        "engagement": lambda: _read_csv("engagement"),
        "training": _read_training,
        # 3 baris teratas file Excel berisi judul laporan -> header ada di baris ke-4
        "recruitment": lambda: _read_excel("recruitment", sheet_name="Requisitions", header=3),
        "kpi_targets": lambda: _read_csv("kpi_targets"),
        "holidays": lambda: _read_csv("holidays"),
    }
    loaded_at = datetime.now().isoformat(timespec="seconds")
    raw: dict[str, pd.DataFrame] = {}
    for name, reader in readers.items():
        df = reader()
        df = df.dropna(how="all")                      # buang baris kosong total
        df["_source_file"] = SOURCES[name]
        df["_loaded_at"] = loaded_at
        raw[name] = df
        log.info("  extract %-12s %8d baris, %2d kolom", name, len(df), df.shape[1] - 2)
    return raw


def save_staging(raw: dict[str, pd.DataFrame], engine) -> None:
    """Simpan data mentah ke tabel stg_* (full refresh)."""
    for name, df in raw.items():
        df.to_sql(f"stg_{name}", engine, if_exists="replace", index=False, chunksize=5000)
    log.info("  %d tabel staging tersimpan", len(raw))
