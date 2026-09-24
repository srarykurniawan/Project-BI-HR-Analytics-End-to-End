-- =====================================================================
-- validation_queries.sql
-- Jalankan query ini di database hasil ETL lalu BANDINGKAN dengan angka
-- di kartu KPI Power BI (filter Tahun = 2025). Jika sama -> DAX benar.
-- Angka "Expected" di bawah berasal dari dataset bawaan (seed 42).
-- =====================================================================

-- 1. Headcount akhir tahun            Expected 2023: 501 | 2024: 536 | 2025: 576
SELECT date_key / 10000 AS year, COUNT(*) AS headcount
FROM fact_headcount_monthly
WHERE date_key IN (20231231, 20241231, 20251231)
GROUP BY date_key / 10000;

-- 2. Hires & terminations             Expected 2025: 120 hires, 80 terminations
SELECT date_key / 10000 AS year, movement_type, COUNT(*) AS n
FROM fact_employee_movement
GROUP BY date_key / 10000, movement_type
ORDER BY 1, 2;

-- 3. Turnover rate perusahaan         Expected 2023: 18.67% | 2024: 22.73% | 2025: 14.35%
SELECT year,
       SUM(avg_headcount) AS avg_headcount,
       SUM(terminations) AS terminations,
       ROUND(SUM(terminations) / SUM(avg_headcount), 4) AS turnover_rate,
       ROUND(SUM(voluntary_terminations) / SUM(avg_headcount), 4) AS voluntary_turnover_rate
FROM vw_turnover_yearly
GROUP BY year
ORDER BY year;

-- 4. Absenteeism & late rate          Expected 2025: 2.15% & 6.93%
SELECT date_key / 10000 AS year,
       ROUND(1.0 * SUM(is_absent_unplanned) / COUNT(*), 4) AS absenteeism_rate,
       ROUND(1.0 * SUM(is_late) / SUM(is_present), 4) AS late_rate
FROM fact_attendance
GROUP BY date_key / 10000;

-- 5. Total labor cost (miliar Rp)     Expected 2025: 119.34
SELECT date_key / 10000 AS year, ROUND(SUM(total_labor_cost) / 1e9, 2) AS labor_cost_bn
FROM fact_payroll
GROUP BY date_key / 10000;

-- 6. eNPS & engagement                Expected 2025: eNPS 19.3, engagement 3.69
SELECT survey_year,
       ROUND(AVG(engagement_score), 2) AS engagement,
       ROUND(100.0 * (SUM(CASE WHEN enps_category = 'Promoter'  THEN 1 ELSE 0 END)
                    - SUM(CASE WHEN enps_category = 'Detractor' THEN 1 ELSE 0 END))
             / SUM(CASE WHEN enps_category <> 'Invalid' THEN 1 ELSE 0 END), 1) AS enps
FROM fact_engagement
GROUP BY survey_year;

-- 7. Rekrutmen per tanggal terisi     Expected 2025: 113 hires, TTF 33.9 hari, CPH Rp5.017.079
SELECT filled_date_key / 10000 AS year, COUNT(*) AS hires,
       ROUND(AVG(1.0 * time_to_fill_days), 1) AS avg_time_to_fill,
       ROUND(SUM(recruitment_cost) / COUNT(*), 0) AS cost_per_hire
FROM fact_recruitment
WHERE is_filled = 1
GROUP BY filled_date_key / 10000;

-- 8. Kinerja                           Expected 2025: rating 3.14, high performer 36.2%
SELECT review_year, ROUND(AVG(1.0 * rating), 2) AS avg_rating,
       ROUND(AVG(1.0 * is_high_performer), 4) AS high_performer_pct
FROM fact_performance
GROUP BY review_year;

-- 9. Audit ETL: hasil data quality & baris yang ditolak
SELECT status, COUNT(*) FROM etl_dq_results GROUP BY status;
SELECT source_table, reason, COUNT(*) FROM etl_rejected_rows GROUP BY source_table, reason;
SELECT * FROM etl_run_log ORDER BY started_at DESC;
