-- =====================================================================
-- views.sql - View analitik (dipakai untuk validasi angka & analisis SQL)
-- Portabel: SQLite / PostgreSQL / SQL Server 2016+
-- =====================================================================
DROP VIEW IF EXISTS vw_headcount_monthly;
DROP VIEW IF EXISTS vw_turnover_yearly;
DROP VIEW IF EXISTS vw_attendance_monthly;
DROP VIEW IF EXISTS vw_payroll_monthly;
DROP VIEW IF EXISTS vw_recruitment_source;
DROP VIEW IF EXISTS vw_employee_360;

-- Headcount akhir bulan per departemen
CREATE VIEW vw_headcount_monthly AS
SELECT d.year, d.month, d.year_month, dp.department_name, COUNT(*) AS headcount,
       AVG(1.0 * h.monthly_base_salary) AS avg_base_salary
FROM fact_headcount_monthly h
JOIN dim_date d        ON d.date_key = h.date_key
JOIN dim_department dp ON dp.department_key = h.department_key
GROUP BY d.year, d.month, d.year_month, dp.department_name;

-- Turnover tahunan per departemen = terminasi / rata-rata headcount bulanan
CREATE VIEW vw_turnover_yearly AS
WITH hc AS (
    SELECT h.date_key / 10000 AS year, h.department_key, h.date_key, COUNT(*) AS headcount
    FROM fact_headcount_monthly h
    GROUP BY h.date_key / 10000, h.department_key, h.date_key
), avg_hc AS (
    SELECT year, department_key, AVG(1.0 * headcount) AS avg_headcount FROM hc GROUP BY year, department_key
), term AS (
    SELECT m.date_key / 10000 AS year, m.department_key, COUNT(*) AS terminations,
           SUM(m.is_voluntary) AS voluntary_terminations, SUM(m.is_regrettable) AS regrettable_terminations
    FROM fact_employee_movement m
    WHERE m.movement_type = 'Termination'
    GROUP BY m.date_key / 10000, m.department_key
)
SELECT a.year, dp.department_name, ROUND(a.avg_headcount, 1) AS avg_headcount,
       COALESCE(t.terminations, 0) AS terminations,
       COALESCE(t.voluntary_terminations, 0) AS voluntary_terminations,
       COALESCE(t.regrettable_terminations, 0) AS regrettable_terminations,
       ROUND(COALESCE(t.terminations, 0) / a.avg_headcount, 4) AS turnover_rate
FROM avg_hc a
JOIN dim_department dp ON dp.department_key = a.department_key
LEFT JOIN term t ON t.year = a.year AND t.department_key = a.department_key;

-- Kehadiran bulanan per departemen
CREATE VIEW vw_attendance_monthly AS
SELECT d.year, d.year_month, dp.department_name,
       COUNT(*) AS scheduled_days,
       SUM(a.is_absent_unplanned) AS unplanned_absence_days,
       SUM(a.is_late) AS late_days,
       SUM(a.overtime_hours) AS overtime_hours,
       ROUND(1.0 * SUM(a.is_absent_unplanned) / COUNT(*), 4) AS absenteeism_rate,
       ROUND(1.0 * SUM(a.is_late) / NULLIF(SUM(a.is_present), 0), 4) AS late_rate
FROM fact_attendance a
JOIN dim_date d        ON d.date_key = a.date_key
JOIN dim_department dp ON dp.department_key = a.department_key
GROUP BY d.year, d.year_month, dp.department_name;

-- Biaya tenaga kerja bulanan
CREATE VIEW vw_payroll_monthly AS
SELECT d.year, d.year_month, dp.department_name,
       COUNT(*) AS paid_employees,
       SUM(p.gross_pay) AS gross_pay, SUM(p.overtime_pay) AS overtime_pay,
       SUM(p.bpjs_company) AS bpjs_company, SUM(p.total_labor_cost) AS total_labor_cost
FROM fact_payroll p
JOIN dim_date d        ON d.date_key = p.date_key
JOIN dim_department dp ON dp.department_key = p.department_key
GROUP BY d.year, d.year_month, dp.department_name;

-- Efektivitas sumber rekrutmen
CREATE VIEW vw_recruitment_source AS
SELECT source,
       COUNT(*) AS requisitions,
       SUM(is_filled) AS hires,
       ROUND(AVG(CASE WHEN is_filled = 1 THEN 1.0 * time_to_fill_days END), 1) AS avg_time_to_fill,
       ROUND(SUM(CASE WHEN is_filled = 1 THEN recruitment_cost ELSE 0 END) / NULLIF(SUM(is_filled), 0), 0) AS cost_per_hire,
       ROUND(1.0 * SUM(offers_accepted) / NULLIF(SUM(offers_made), 0), 3) AS offer_acceptance_rate,
       SUM(applicants) AS applicants
FROM fact_recruitment
GROUP BY source;

-- Profil 360 karyawan (rating & engagement terakhir) - ROW_NUMBER portabel di 3 DB
CREATE VIEW vw_employee_360 AS
WITH lp AS (
    SELECT employee_key, rating,
           ROW_NUMBER() OVER (PARTITION BY employee_key ORDER BY review_year DESC) AS rn
    FROM fact_performance
), le AS (
    SELECT employee_key, engagement_score, enps_score,
           ROW_NUMBER() OVER (PARTITION BY employee_key ORDER BY survey_year DESC) AS rn
    FROM fact_engagement
)
SELECT e.employee_id, e.full_name, e.gender, e.age, e.current_department, e.current_position,
       e.current_location, e.employee_status, e.tenure_years, e.monthly_salary,
       lp.rating AS last_rating, le.engagement_score AS last_engagement, le.enps_score AS last_enps
FROM dim_employee e
LEFT JOIN lp ON lp.employee_key = e.employee_key AND lp.rn = 1
LEFT JOIN le ON le.employee_key = e.employee_key AND le.rn = 1;
