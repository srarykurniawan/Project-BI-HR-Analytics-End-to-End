-- =====================================================================
-- schema.sql  -  Star schema Data Warehouse HR Analytics
-- Kompatibel: SQLite, PostgreSQL, SQL Server 2016+ (ANSI SQL sederhana)
-- Dijalankan otomatis oleh etl/load.py (full refresh: DROP lalu CREATE)
-- =====================================================================

-- ---------- DROP view dulu (PostgreSQL/SQL Server menolak DROP TABLE yang masih dipakai view) ----------
DROP VIEW IF EXISTS vw_headcount_monthly;
DROP VIEW IF EXISTS vw_turnover_yearly;
DROP VIEW IF EXISTS vw_attendance_monthly;
DROP VIEW IF EXISTS vw_payroll_monthly;
DROP VIEW IF EXISTS vw_recruitment_source;
DROP VIEW IF EXISTS vw_employee_360;

-- ---------- DROP (fakta dulu, lalu dimensi) ----------
DROP TABLE IF EXISTS fact_attendance;
DROP TABLE IF EXISTS fact_payroll;
DROP TABLE IF EXISTS fact_performance;
DROP TABLE IF EXISTS fact_engagement;
DROP TABLE IF EXISTS fact_training;
DROP TABLE IF EXISTS fact_recruitment;
DROP TABLE IF EXISTS fact_headcount_monthly;
DROP TABLE IF EXISTS fact_employee_movement;
DROP TABLE IF EXISTS kpi_target;
DROP TABLE IF EXISTS dim_employee;
DROP TABLE IF EXISTS dim_course;
DROP TABLE IF EXISTS dim_department;
DROP TABLE IF EXISTS dim_position;
DROP TABLE IF EXISTS dim_location;
DROP TABLE IF EXISTS dim_date;

-- ---------- DIMENSI ----------
CREATE TABLE dim_date (
    date_key          INTEGER      NOT NULL PRIMARY KEY,   -- YYYYMMDD
    date              DATE         NOT NULL,
    year              INTEGER      NOT NULL,
    quarter           INTEGER      NOT NULL,
    quarter_label     VARCHAR(2)   NOT NULL,
    month             INTEGER      NOT NULL,
    month_name        VARCHAR(12)  NOT NULL,
    month_short       VARCHAR(3)   NOT NULL,
    year_month        INTEGER      NOT NULL,               -- YYYYMM (kolom sort)
    year_month_label  VARCHAR(8)   NOT NULL,               -- 'Jan 2024'
    week_of_year      INTEGER      NOT NULL,
    day_of_month      INTEGER      NOT NULL,
    day_of_week       INTEGER      NOT NULL,               -- 1 = Senin
    day_name          VARCHAR(10)  NOT NULL,
    is_weekend        SMALLINT     NOT NULL,
    is_holiday        SMALLINT     NOT NULL,
    is_working_day    SMALLINT     NOT NULL,
    is_month_end      SMALLINT     NOT NULL
);

CREATE TABLE dim_department (
    department_key      INTEGER      NOT NULL PRIMARY KEY,
    department_code     VARCHAR(10)   NOT NULL,
    department_name     VARCHAR(50),
    division            VARCHAR(50),
    head_of_department  VARCHAR(100),
    cost_center         VARCHAR(20)
);

CREATE TABLE dim_position (
    position_key    INTEGER       NOT NULL PRIMARY KEY,
    position_code   VARCHAR(10)   NOT NULL,
    position_title  VARCHAR(100),
    job_family      VARCHAR(50),
    job_level       VARCHAR(10),
    level_name      VARCHAR(30),
    grade           INTEGER,
    salary_min      DECIMAL(18,2),
    salary_max      DECIMAL(18,2),
    salary_mid      DECIMAL(18,2)
);

CREATE TABLE dim_location (
    location_key   INTEGER      NOT NULL PRIMARY KEY,
    location_code  VARCHAR(10)   NOT NULL,
    city           VARCHAR(50),
    province       VARCHAR(50),
    region         VARCHAR(30),
    office_type    VARCHAR(30)
);

CREATE TABLE dim_course (
    course_key      INTEGER       NOT NULL PRIMARY KEY,
    course_code     VARCHAR(10)   NOT NULL,
    course_name     VARCHAR(100),
    category        VARCHAR(50),
    provider        VARCHAR(100),
    standard_hours  DECIMAL(6,1)
);

CREATE TABLE dim_employee (
    employee_key        INTEGER       NOT NULL PRIMARY KEY,
    employee_id         VARCHAR(10)   NOT NULL,
    full_name           VARCHAR(100),
    gender              VARCHAR(10),
    birth_date          DATE,
    age                 INTEGER,
    age_band            VARCHAR(10),
    generation          VARCHAR(15),
    marital_status      VARCHAR(15),
    education           VARCHAR(10),
    email               VARCHAR(150),
    employment_type     VARCHAR(15),
    hire_date           DATE,
    hire_year           INTEGER,
    termination_date    DATE,
    termination_type    VARCHAR(15),
    termination_reason  VARCHAR(50),
    employee_status     VARCHAR(12),
    tenure_years        DECIMAL(6,2),
    tenure_band         VARCHAR(15),
    current_department  VARCHAR(50),
    current_position    VARCHAR(100),
    job_level           VARCHAR(10),
    current_location    VARCHAR(50),
    monthly_salary      DECIMAL(18,2),
    dq_flag             VARCHAR(30)
);

-- ---------- FAKTA ----------
-- Grain: 1 karyawan aktif x 1 akhir bulan (periodic snapshot)
CREATE TABLE fact_headcount_monthly (
    date_key             INTEGER  NOT NULL REFERENCES dim_date(date_key),
    employee_key         INTEGER  NOT NULL REFERENCES dim_employee(employee_key),
    department_key       INTEGER  NOT NULL REFERENCES dim_department(department_key),
    position_key         INTEGER  NOT NULL REFERENCES dim_position(position_key),
    location_key         INTEGER  NOT NULL REFERENCES dim_location(location_key),
    age                  INTEGER,
    tenure_months        DECIMAL(6,1),
    monthly_base_salary  DECIMAL(18,2),
    is_new_hire          SMALLINT,
    PRIMARY KEY (date_key, employee_key)
);

-- Grain: 1 event (Hire / Termination)
CREATE TABLE fact_employee_movement (
    movement_key            INTEGER  NOT NULL PRIMARY KEY,
    date_key                INTEGER  NOT NULL REFERENCES dim_date(date_key),
    employee_key            INTEGER  NOT NULL REFERENCES dim_employee(employee_key),
    department_key          INTEGER  NOT NULL REFERENCES dim_department(department_key),
    position_key            INTEGER  NOT NULL REFERENCES dim_position(position_key),
    location_key            INTEGER  NOT NULL REFERENCES dim_location(location_key),
    movement_type           VARCHAR(15) NOT NULL,
    termination_type        VARCHAR(15),
    termination_reason      VARCHAR(50),
    tenure_months_at_event  DECIMAL(6,1),
    is_voluntary            SMALLINT,
    is_early_turnover       SMALLINT,
    is_regrettable          SMALLINT,
    last_rating             INTEGER
);

-- Grain: 1 karyawan x 1 hari kerja
CREATE TABLE fact_attendance (
    attendance_key       INTEGER  NOT NULL PRIMARY KEY,
    date_key             INTEGER  NOT NULL REFERENCES dim_date(date_key),
    employee_key         INTEGER  NOT NULL REFERENCES dim_employee(employee_key),
    department_key       INTEGER  NOT NULL REFERENCES dim_department(department_key),
    location_key         INTEGER  NOT NULL REFERENCES dim_location(location_key),
    status               VARCHAR(10) NOT NULL,
    check_in             VARCHAR(5),
    check_out            VARCHAR(5),
    work_hours           DECIMAL(5,2),
    late_minutes         DECIMAL(6,1),
    overtime_hours       DECIMAL(5,2),
    is_present           SMALLINT,
    is_late              SMALLINT,
    is_sick              SMALLINT,
    is_absent_unplanned  SMALLINT,
    is_leave             SMALLINT,
    is_wfh               SMALLINT
);

-- Grain: 1 karyawan x 1 bulan penggajian
CREATE TABLE fact_payroll (
    payroll_key       INTEGER  NOT NULL PRIMARY KEY,
    payroll_id        VARCHAR(20) NOT NULL,
    date_key          INTEGER  NOT NULL REFERENCES dim_date(date_key),  -- akhir bulan periode
    employee_key      INTEGER  NOT NULL REFERENCES dim_employee(employee_key),
    department_key    INTEGER  NOT NULL REFERENCES dim_department(department_key),
    position_key      INTEGER  NOT NULL REFERENCES dim_position(position_key),
    location_key      INTEGER  NOT NULL REFERENCES dim_location(location_key),
    base_salary       DECIMAL(18,2),
    allowance         DECIMAL(18,2),
    overtime_hours    DECIMAL(6,2),
    overtime_pay      DECIMAL(18,2),
    bonus             DECIMAL(18,2),
    thr               DECIMAL(18,2),
    gross_pay         DECIMAL(18,2),
    bpjs_employee     DECIMAL(18,2),
    bpjs_company      DECIMAL(18,2),
    pph21             DECIMAL(18,2),
    net_pay           DECIMAL(18,2),
    total_labor_cost  DECIMAL(18,2)
);

-- Grain: 1 karyawan x 1 tahun review
CREATE TABLE fact_performance (
    performance_key       INTEGER  NOT NULL PRIMARY KEY,
    review_id             VARCHAR(20) NOT NULL,
    date_key              INTEGER  NOT NULL REFERENCES dim_date(date_key),
    employee_key          INTEGER  NOT NULL REFERENCES dim_employee(employee_key),
    department_key        INTEGER  NOT NULL REFERENCES dim_department(department_key),
    position_key          INTEGER  NOT NULL REFERENCES dim_position(position_key),
    location_key          INTEGER  NOT NULL REFERENCES dim_location(location_key),
    review_year           INTEGER,
    rating                INTEGER,
    rating_label          VARCHAR(30),
    goal_achievement_pct  DECIMAL(6,1),
    competency_score      DECIMAL(4,2),
    is_high_performer     SMALLINT,
    is_low_performer      SMALLINT,
    calibrated            VARCHAR(3)
);

-- Grain: 1 respon survei
CREATE TABLE fact_engagement (
    engagement_key             INTEGER  NOT NULL PRIMARY KEY,
    response_id                VARCHAR(20) NOT NULL,
    date_key                   INTEGER  NOT NULL REFERENCES dim_date(date_key),
    employee_key               INTEGER  NOT NULL REFERENCES dim_employee(employee_key),
    department_key             INTEGER  NOT NULL REFERENCES dim_department(department_key),
    location_key               INTEGER  NOT NULL REFERENCES dim_location(location_key),
    survey_year                INTEGER,
    engagement_score           DECIMAL(3,1),
    work_life_balance          DECIMAL(3,1),
    compensation_satisfaction  DECIMAL(3,1),
    manager_support            DECIMAL(3,1),
    career_growth              DECIMAL(3,1),
    enps_score                 INTEGER,
    enps_category              VARCHAR(10)
);

-- Grain: 1 karyawan x 1 sesi training
CREATE TABLE fact_training (
    training_key     INTEGER  NOT NULL PRIMARY KEY,
    training_id      VARCHAR(10) NOT NULL,
    date_key         INTEGER  NOT NULL REFERENCES dim_date(date_key),
    end_date_key     INTEGER,
    employee_key     INTEGER  NOT NULL REFERENCES dim_employee(employee_key),
    department_key   INTEGER  NOT NULL REFERENCES dim_department(department_key),
    location_key     INTEGER  NOT NULL REFERENCES dim_location(location_key),
    course_key       INTEGER  NOT NULL REFERENCES dim_course(course_key),
    duration_hours   DECIMAL(6,1),
    completed_hours  DECIMAL(6,1),
    cost_idr         DECIMAL(18,2),
    status           VARCHAR(15),
    is_completed     SMALLINT,
    post_test_score  INTEGER
);

-- Grain: 1 requisition (lowongan)
CREATE TABLE fact_recruitment (
    requisition_key    INTEGER  NOT NULL PRIMARY KEY,
    requisition_id     VARCHAR(12) NOT NULL,
    open_date_key      INTEGER  NOT NULL REFERENCES dim_date(date_key),
    filled_date_key    INTEGER  REFERENCES dim_date(date_key),              -- relasi INAKTIF di Power BI
    department_key     INTEGER  NOT NULL REFERENCES dim_department(department_key),
    position_key       INTEGER  NOT NULL REFERENCES dim_position(position_key),
    location_key       INTEGER  NOT NULL REFERENCES dim_location(location_key),
    status             VARCHAR(12),
    source             VARCHAR(30),
    applicants         INTEGER,
    screened           INTEGER,
    interviewed        INTEGER,
    offers_made        INTEGER,
    offers_accepted    INTEGER,
    recruitment_cost   DECIMAL(18,2),
    time_to_fill_days  INTEGER,
    is_filled          SMALLINT,
    hired_employee_id  VARCHAR(10)
);

-- Tabel target KPI (disconnected table di Power BI)
CREATE TABLE kpi_target (
    kpi_code      VARCHAR(20)  NOT NULL,
    kpi_name      VARCHAR(60),
    year          INTEGER      NOT NULL,
    target_value  DECIMAL(18,4),
    direction     VARCHAR(10),
    unit          VARCHAR(10),
    PRIMARY KEY (kpi_code, year)
);

-- ---------- INDEX (percepat query & refresh) ----------
CREATE INDEX ix_att_date   ON fact_attendance (date_key);
CREATE INDEX ix_att_emp    ON fact_attendance (employee_key);
CREATE INDEX ix_pay_date   ON fact_payroll (date_key);
CREATE INDEX ix_mov_date   ON fact_employee_movement (date_key);
CREATE INDEX ix_hc_date    ON fact_headcount_monthly (date_key);
