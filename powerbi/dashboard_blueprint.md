# Dashboard Blueprint — HR Analytics (6 halaman)

Kanvas: 1280 × 720 (16:9). Grid 8 px. Semua halaman memakai header & slicer yang sama.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [Title Page measure]                         Data per 31 Des 2025        │  header 56px
│ Slicer: Tahun | Departemen | Lokasi | Level        (sync semua halaman)  │  48px
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────────────┤
│  KPI 1   │  KPI 2   │  KPI 3   │  KPI 4   │  KPI 5   │  KPI 6           │  kartu 96px
├──────────┴──────────┴──────────┼──────────┴──────────┴──────────────────┤
│  Visual utama (tren)            │  Visual pendukung (breakdown)          │
├─────────────────────────────────┼────────────────────────────────────────┤
│  Visual pendukung               │  Tabel detail / insight                │
└─────────────────────────────────┴────────────────────────────────────────┘
```

## 1. Executive Summary
| Area | Visual | Field / Measure |
| --- | --- | --- |
| Kartu | Card (new) ×6 | Headcount (+Headcount YoY %), Turnover Rate (+Turnover Status), Absenteeism Rate, Total Labor Cost, eNPS (+eNPS Status), Avg Time to Fill |
| Tren | Line chart | X: dim_date[year_month_label] (sort by year_month) · Y: Headcount, Turnover Rate R12M di visual terpisah |
| Breakdown | Clustered bar | Y: dim_department[department_name] · X: Turnover Rate, conditional color = Color Turnover |
| Peta | Map / Filled map | Location: dim_location[city] · Size: Headcount |
| Insight | Smart narrative / Text box | 3 kalimat insight utama |

## 2. Workforce & Demografi
Kartu: Headcount, New Hires, Terminations, Net Headcount Change, Female %, Avg Age, Avg Tenure (Years), Manager Ratio.
Visual: waterfall headcount (awal → +hire → −terminasi → akhir), piramida usia (bar: age_band × gender),
donut generation, stacked column headcount per departemen × job_level, treemap lokasi.

## 3. Turnover & Retention
Kartu: Turnover Rate vs Target, Voluntary Turnover Rate, Retention Rate, Regrettable Turnover %, Early Turnover %.
Visual: line Turnover Rate R12M + garis target (constant line), bar alasan keluar (termination_reason),
matrix departemen × tenure_band (heatmap Terminations), scatter per departemen (X Avg Engagement Score,
Y Turnover Rate, size Headcount), key influencers (analyze: movement_type = Termination).

## 4. Kompensasi & Kehadiran
Kartu: Total Labor Cost, Labor Cost per Employee, Overtime % of Payroll, Gender Pay Gap %, Absenteeism Rate, Late Arrival Rate.
Visual: column stacked labor cost per bulan (base, allowance, overtime, bonus, THR), bar Compa-Ratio per level,
matrix Gender Pay Gap % per job_level, line Absenteeism & Late rate per bulan (2 visual kecil),
heatmap hari (day_name × month) untuk keterlambatan.

## 5. Performance, Engagement & Learning
Kartu: Avg Performance Rating, High Performer %, eNPS, Avg Engagement Score, Training Hours per Employee, Training Completion Rate.
Visual: distribusi rating (column rating_label), 100% stacked eNPS category per departemen,
bar sub-skor engagement (WLB, kompensasi, manager, karier), bar Training Hours per kategori kursus,
scatter Training Hours vs Avg Performance Rating per departemen.

## 6. Recruitment
Kartu: Requisitions Opened, Hires Filled, Avg Time to Fill (Days), Cost per Hire, Offer Acceptance Rate, Open Requisitions.
Visual: funnel (Funnel Applicants → Screened → Interviewed → Offers → Hired), tabel sumber rekrutmen
(source, Hires Filled, Avg Time to Fill, Cost per Hire, Offer Acceptance Rate dengan data bars),
line time to fill per bulan + target, bar time to fill per departemen.

## Interaksi
- Sync slicers (View > Sync slicers) untuk Tahun, Departemen, Lokasi.
- Drill-through ke halaman **Employee Detail** (tabel dim_employee + riwayat rating, engagement, absensi).
- Tooltip page kecil untuk bar departemen: Headcount, Turnover, Avg Engagement, Absenteeism.
- Bookmarks + tombol navigasi di sisi kiri; tombol "Reset filter".
