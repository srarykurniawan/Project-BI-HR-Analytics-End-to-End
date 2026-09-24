"""
pipeline.py - ORKESTRATOR ETL
Menjalankan Extract -> Staging -> Transform -> Data Quality Gate -> Load -> Views,
mencatat log ke file (logs/etl_YYYYMMDD_HHMMSS.log) dan ke tabel etl_run_log.

Cara pakai (dari folder root project):
    python etl/pipeline.py
"""
from __future__ import annotations

import logging
import sys
import time
import uuid
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine

from config import DB_URL, LOG_DIR
from data_quality import run_checks
from extract import extract_all, save_staging
from load import create_views, load_all, load_audit
from transform import transform_all


def setup_logging() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logfile = LOG_DIR / f"etl_{ts}.log"
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)-13s | %(message)s",
        handlers=[logging.FileHandler(logfile, encoding="utf-8"), logging.StreamHandler(sys.stdout)])
    return str(logfile)


def main() -> int:
    logfile = setup_logging()
    log = logging.getLogger("etl.pipeline")
    run_id, started = uuid.uuid4().hex[:12], datetime.now()
    log.info("=" * 70)
    log.info("HR ANALYTICS ETL  | run_id=%s | db=%s", run_id, DB_URL.split("@")[-1])
    log.info("=" * 70)
    engine = create_engine(DB_URL)
    status, counts, t0 = "SUCCESS", {}, time.time()
    try:
        log.info("[1/5] EXTRACT")
        raw = extract_all()
        save_staging(raw, engine)

        log.info("[2/5] TRANSFORM")
        tables, rejects = transform_all(raw)

        log.info("[3/5] DATA QUALITY GATE")
        dq = run_checks(tables)
        dq_df = dq.frame().assign(run_id=run_id)
        load_audit(engine, "etl_dq_results", dq_df)
        load_audit(engine, "etl_rejected_rows", rejects.assign(run_id=run_id))
        if dq.critical_failed:
            raise RuntimeError("Ada aturan CRITICAL yang gagal - load dibatalkan. Cek tabel etl_dq_results.")
        log.info("  %d cek: %d PASS, %d WARN, %d FAIL | %d baris ditolak",
                 len(dq_df), (dq_df.status == "PASS").sum(), (dq_df.status == "WARN").sum(),
                 (dq_df.status == "FAIL").sum(), len(rejects))

        log.info("[4/5] LOAD")
        counts = load_all(tables, engine)

        log.info("[5/5] VIEWS")
        create_views(engine)
    except Exception as exc:  # noqa: BLE001
        status = "FAILED"
        log.exception("Pipeline gagal: %s", exc)
    finally:
        run = pd.DataFrame([dict(run_id=run_id, started_at=started.isoformat(timespec="seconds"),
                                 finished_at=datetime.now().isoformat(timespec="seconds"),
                                 duration_sec=round(time.time() - t0, 1), status=status,
                                 total_rows_loaded=sum(counts.values()), log_file=logfile)])
        load_audit(engine, "etl_run_log", run, if_exists="append")
        log.info("SELESAI: %s dalam %.1f detik | log: %s", status, time.time() - t0, logfile)
    return 0 if status == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
